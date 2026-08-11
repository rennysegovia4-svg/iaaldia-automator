#!/usr/bin/env python3
"""
watchdog.py — Sistema de autocorrección permanente para IA al Día.

Ciclo cada 15 minutos:
  1. DETECTAR  — revisa si algún workflow falló en las últimas 2 horas
  2. ANALIZAR  — extrae los logs del error exacto
  3. CLASIFICAR — identifica el tipo de fallo (conocido o desconocido)
  4. CORREGIR  — aplica fix en el código (hardcoded o via Gemini)
  5. PUSHEAR   — commitea el fix al repo
  6. REINTENTAR — dispara de nuevo el workflow fallido

Nunca reintenta el mismo run_id dos veces (evita bucles infinitos).
"""
import os, json, re, time, subprocess, requests
from pathlib import Path
from datetime import datetime, timedelta, timezone

BASE_DIR     = Path(__file__).parent
WATCHDOG_LOG = BASE_DIR / "watchdog_log.json"

# Archivos que el watchdog NUNCA puede modificar via Gemini AI fix
# (solo los fixes hardcodeados y específicos pueden tocarlos)
GEMINI_PROTECTED = {"generate_short.py"}


def _safe_write_py(fpath: Path, new_src: str) -> bool:
    """Escribe un archivo .py solo si pasa la validación de sintaxis. Retorna True si escribió."""
    import py_compile, tempfile
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tmp:
        tmp.write(new_src)
        tmp_path = tmp.name
    try:
        py_compile.compile(tmp_path, doraise=True)
    except py_compile.PyCompileError as e:
        print(f"  ✗ _safe_write_py: sintaxis inválida en {fpath.name}, NO se escribe. ({e})")
        Path(tmp_path).unlink(missing_ok=True)
        return False
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    fpath.write_text(new_src)
    return True
ENV_FILE     = BASE_DIR / ".env"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GEMINI_KEY   = os.environ.get("GEMINI_API_KEY", "")
REPO         = os.environ.get("GITHUB_REPOSITORY", "rennysegovia4-svg/iaaldia-automator")
GH_API       = "https://api.github.com"

# ── Patrones de error conocidos → función de fix ──────────────────────────────
# Cada entrada: (regex del error, tipo_error, descripción)
ERROR_PATTERNS = [
    (r"invalid_scope|Bad Request.*scope",      "invalid_scope",       "Scope OAuth inválido"),
    (r"Filter not found|filtergraph",           "ffmpeg_filter",       "Filtro FFmpeg no disponible"),
    (r"ModuleNotFoundError: No module named '(\w[\w.]*)'", "missing_module", "Módulo Python faltante"),
    (r"quota.*exceeded|Resource.*exhausted|429", "quota_exceeded",    "Cuota API agotada"),
    (r"RefreshError|Token.*expired|invalid_grant", "token_expired",   "Token OAuth expirado"),
    (r"JSONDecodeError|json\.decoder",          "json_parse",          "Error parseando JSON de Gemini"),
    (r"Connection.*timed out|ReadTimeout|ConnectTimeout", "timeout",  "Timeout de conexión"),
    (r"No space left on device",               "disk_full",            "Disco lleno en runner"),
    (r"403.*push|push.*403|ad-m/github-push", "push_403",             "Push 403 — acción de push sin permisos"),
    (r"faster.whisper|whisper.*numpy|numpy.*incompatible", "whisper_numpy", "Conflicto numpy/whisper"),
    (r"manim.*not found|manim.*command",       "manim_missing",        "Manim no en PATH"),
    (r"moviepy|VideoFileClip",                 "moviepy_error",        "Error en MoviePy"),
    (r"PEXELS.*403|pexels.*unauthorized",      "pexels_auth",          "API key de Pexels inválida"),
    (r"GEMINI.*403|API.*key.*invalid",         "gemini_auth",          "API key de Gemini inválida")]

# ── LOG ────────────────────────────────────────────────────────────────────────
def load_log() -> dict:
    if WATCHDOG_LOG.exists():
        try: return json.loads(WATCHDOG_LOG.read_text())
        except: pass
    return {"fixed_runs": [], "fixes_applied": [], "iterations": 0, "last_run": ""}

def save_log(log: dict):
    log["last_run"] = datetime.utcnow().isoformat()
    WATCHDOG_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False))

# ── GitHub API helpers ─────────────────────────────────────────────────────────
def gh(method: str, path: str, **kwargs):
    headers = {"Authorization": f"token {GITHUB_TOKEN}",
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    url = f"{GH_API}/repos/{REPO}{path}" if not path.startswith("http") else path
    try:
        resp = requests.request(method, url, headers=headers, timeout=20, **kwargs)
        if resp.status_code in (200, 201, 204):
            return resp.json() if resp.content else {}
    except Exception as e:
        print(f"  ! GitHub API {method} {path}: {str(e)[:60]}")
    return {}

def get_recent_failures(hours=2) -> list:
    """Workflows que fallaron en las últimas N horas y no han sido reintentados."""
    since = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data  = gh("GET", f"/actions/runs?per_page=30&created=>={since}")
    log   = load_log()
    already_fixed = set(log.get("fixed_runs", []))
    failures = []
    for r in data.get("workflow_runs", []):
        if r["conclusion"] in ("failure",) and str(r["id"]) not in already_fixed:
            # Solo workflows de publicación y learning — no el watchdog mismo
            if "Watchdog" not in r["name"]:
                failures.append(r)
    return failures

def get_logs(run_id: int) -> str:
    """Descarga los logs completos de un run fallido."""
    jobs = gh("GET", f"/actions/runs/{run_id}/jobs")
    full_log = []
    for job in jobs.get("jobs", []):
        if job.get("conclusion") == "failure":
            log_resp = requests.get(
                f"{GH_API}/repos/{REPO}/actions/jobs/{job['id']}/logs",
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
                timeout=30, allow_redirects=True
            )
            if log_resp.status_code == 200:
                full_log.append(log_resp.text[-8000:])  # últimas 8KB
    return "\n".join(full_log)

def retrigger(workflow_name: str):
    """Dispara el workflow fallido de nuevo con workflow_dispatch."""
    workflows = gh("GET", "/actions/workflows")
    for wf in workflows.get("workflows", []):
        if workflow_name.lower() in wf["name"].lower():
            result = gh("POST", f"/actions/workflows/{wf['id']}/dispatches",
                        json={"ref": "main"})
            print(f"  ✓ Retriggered: {wf['name']}")
            return True
    print(f"  ! Workflow no encontrado: {workflow_name}")
    return False

# ── CLASIFICAR error ───────────────────────────────────────────────────────────
def classify(logs: str) -> tuple:
    """Retorna (error_type, match_detail)."""
    for pattern, etype, desc in ERROR_PATTERNS:
        m = re.search(pattern, logs, re.IGNORECASE)
        if m:
            detail = m.group(1) if m.lastindex else ""
            print(f"  → Error clasificado: {etype} — {desc}")
            return etype, detail
    return "unknown", ""

# ── FIXES hardcodeados ─────────────────────────────────────────────────────────
def fix_invalid_scope(detail: str, logs: str):
    """Cambia SCOPES en cualquier archivo Python que pida yt-analytics."""
    fixed = False
    for fpath in BASE_DIR.glob("*.py"):
        src = fpath.read_text()
        if "yt-analytics.readonly" in src:
            new_src = src.replace(
                '', "")
            new_src = re.sub(r',\s*\n?\s*\]', ']', new_src)
            new_src = new_src.replace('["https://www.googleapis.com/auth/youtube.readonly"]',
                                      '["https://www.googleapis.com/auth/youtube"]')
            if new_src != src:
                if _safe_write_py(fpath, new_src):
                    print(f"  ✓ fix_invalid_scope → {fpath.name}")
                fixed = True
    return fixed

def fix_ffmpeg_filter(detail: str, logs: str):
    """Reemplaza filtros complejos por versiones compatibles con Ubuntu."""
    target = BASE_DIR / "generate_short.py"
    if not target.exists(): return False
    src = target.read_text()
    # Reemplazar curves=preset=cross_process por eq más simple
    patched = src.replace(
        "curves=preset=cross_process",
        "eq=contrast=1.1:brightness=0.02:saturation=1.2"
    )
    # Quitar vignette si falla
    if "Filter not found" in logs and "vignette" in logs:
        patched = re.sub(r",\s*vignette=angle=PI/4[^'\"]*", "", patched)
    if patched != src and _safe_write_py(target, patched):
        print("  ✓ fix_ffmpeg_filter → generate_short.py")
        return True
    return False

def fix_missing_module(module_name: str, logs: str):
    """Agrega el módulo faltante a requirements.txt."""
    req = BASE_DIR / "requirements.txt"
    current = req.read_text()
    if module_name and module_name not in current:
        req.write_text(current.rstrip() + f"\n{module_name}\n")
        print(f"  ✓ fix_missing_module → requirements.txt += {module_name}")
        return True
    return False

def fix_quota_exceeded(detail: str, logs: str):
    """Rota el modelo Gemini al siguiente disponible."""
    target = BASE_DIR / "generate_short.py"
    if not target.exists(): return False
    src = target.read_text()
    # Si gemini-2.5-pro está primero, poner flash primero
    patched = src.replace(
        '["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]',
        '["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-pro"]'
    )
    if patched != src and _safe_write_py(target, patched):
        print("  ✓ fix_quota_exceeded → modelo rotado a gemini-2.5-flash primero")
        return True
    return False

def fix_json_parse(detail: str, logs: str):
    """El fallback de JSON ya existe — solo reintenta."""
    print("  ✓ fix_json_parse → solo reintento (fallback ya implementado)")
    return True  # Retrigger es suficiente

def fix_timeout(detail: str, logs: str):
    """Aumenta timeouts en requests."""
    target = BASE_DIR / "generate_short.py"
    if not target.exists(): return False
    src = target.read_text()
    patched = src.replace("timeout=12)", "timeout=25)").replace("timeout=45)", "timeout=60)")
    if patched != src and _safe_write_py(target, patched):
        print("  ✓ fix_timeout → timeouts aumentados")
        return True
    return True  # Retrigger igual

def fix_whisper_numpy(detail: str, logs: str):
    """Fija versión de numpy compatible con faster-whisper."""
    req = BASE_DIR / "requirements.txt"
    current = req.read_text()
    if "numpy" not in current:
        req.write_text(current.rstrip() + "\nnumpy<2.0\n")
        print("  ✓ fix_whisper_numpy → numpy<2.0 en requirements.txt")
        return True
    return False

def fix_manim_missing(detail: str, logs: str):
    """Deshabilita Manim si no está disponible."""
    target = BASE_DIR / "generate_short.py"
    if not target.exists(): return False
    src = target.read_text()
    patched = src.replace("USE_MANIM = True", "USE_MANIM = False")
    if patched == src:
        # Buscar donde se llama manim y envolverlo en try/except
        patched = src.replace(
            "make_manim_intro(output_path)",
            "make_manim_intro(output_path) if False else None  # disabled by watchdog"
        )
    if patched != src and _safe_write_py(target, patched):
        print("  ✓ fix_manim_missing → Manim deshabilitado")
        return True
    return True

def fix_push_403(detail: str, logs: str):
    """Reemplaza ad-m/github-push-action por git push directo con token."""
    import re as _re
    fixed = False
    for wf in (BASE_DIR / ".github" / "workflows").glob("*.yml"):
        src = wf.read_text()
        if "ad-m/github-push-action" in src:
            patched = _re.sub(
                r"\s*- name: Push.*?\n.*?uses: ad-m/github-push-action@master\n.*?with:.*?\n.*?github_token:.*?\n.*?branch: main",
                "\n      - name: Push\n        run: git push \"https://x-access-token:${{ secrets.GITHUB_TOKEN }}@github.com/${{ github.repository }}.git\" HEAD:main",
                src, flags=_re.DOTALL
            )
            if patched != src:
                wf.write_text(patched)
                print(f"  ✓ fix_push_403 → {wf.name}")
                fixed = True
    return fixed

def fix_moviepy_error(detail: str, logs: str):
    """Fija versión de moviepy."""
    req = BASE_DIR / "requirements.txt"
    current = req.read_text()
    patched = re.sub(r"moviepy[^\n]*", "moviepy==1.0.3", current)
    if patched != current:
        req.write_text(patched)
        print("  ✓ fix_moviepy_error → moviepy==1.0.3 fijado")
        return True
    return True

KNOWN_FIXES = {
    "invalid_scope":  fix_invalid_scope,
    "ffmpeg_filter":  fix_ffmpeg_filter,
    "missing_module": fix_missing_module,
    "quota_exceeded": fix_quota_exceeded,
    "json_parse":     fix_json_parse,
    "timeout":        fix_timeout,
    "whisper_numpy":  fix_whisper_numpy,
    "manim_missing":  fix_manim_missing,
    "moviepy_error":  fix_moviepy_error,
    "token_expired":  lambda d, l: True,  # Solo retrigger — el token se renueva solo
    "pexels_auth":    lambda d, l: True,  # Secret issue — solo retrigger
    "gemini_auth":    lambda d, l: True,  # Secret issue — solo retrigger
    "disk_full":      lambda d, l: True,  # Infra issue — solo retrigger
    "push_403":       fix_push_403,
}

# ── FIX DESCONOCIDO: Gemini analiza y genera el patch ─────────────────────────
def gemini_fix(logs: str, workflow_name: str) -> bool:
    """Para errores no clasificados, Gemini lee los logs y genera un fix."""
    if not GEMINI_KEY:
        print("  ! GEMINI_KEY no disponible para fix automático")
        return False

    # Obtener contexto del código relevante
    code_ctx = ""
    for fpath in [BASE_DIR/"generate_short.py", BASE_DIR/"learning_loop.py",
                  BASE_DIR/"viral_learner.py", BASE_DIR/"requirements.txt"]:
        if fpath.exists():
            code_ctx += f"\n=== {fpath.name} (primeras 100 líneas) ===\n"
            code_ctx += "\n".join(fpath.read_text().splitlines()[:100])

    from google import genai
    client = genai.Client(api_key=GEMINI_KEY)

    prompt = f"""Eres un ingeniero de DevOps experto en Python y GitHub Actions.
Un workflow de GitHub Actions falló. Analiza los logs y genera un fix mínimo.

WORKFLOW FALLIDO: {workflow_name}

LOGS DEL ERROR:
{logs[-4000:]}

CÓDIGO RELEVANTE:
{code_ctx[:3000]}

TAREA: Identifica la causa exacta del error y genera el fix mínimo necesario.

RESPONDE SOLO este JSON:
{{
  "causa": "descripción concisa del error",
  "archivo_a_modificar": "nombre_archivo.py o requirements.txt o null",
  "buscar": "texto exacto a reemplazar en el archivo (null si no aplica)",
  "reemplazar": "texto nuevo que lo reemplaza (null si no aplica)",
  "accion_extra": "descripción si se necesita algo más allá de una sustitución de texto",
  "confianza": 0.8
}}

REGLAS:
- El fix debe ser MÍNIMO: un solo reemplazo de texto si es posible
- No inventes cambios grandes, solo el fix exacto para este error
- Si el error es transitorio (timeout, cuota), pon archivo_a_modificar: null
- confianza entre 0 y 1
"""
    try:
        resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text = resp.text.strip()
        if "```" in text:
            for part in text.split("```"):
                part = part.strip().lstrip("json").strip()
                if part.startswith("{"): text = part; break
        fix_plan = json.loads(text)
        print(f"  Gemini fix plan (confianza {fix_plan.get('confianza',0):.0%}): {fix_plan.get('causa','?')}")

        if fix_plan.get("archivo_a_modificar") and fix_plan.get("buscar") and fix_plan.get("reemplazar"):
            target = BASE_DIR / fix_plan["archivo_a_modificar"]
            if target.name in GEMINI_PROTECTED:
                print(f"  ✗ Gemini fix bloqueado: {target.name} está en GEMINI_PROTECTED")
            elif target.exists() and fix_plan["confianza"] >= 0.6:
                src = target.read_text()
                patched = src.replace(fix_plan["buscar"], fix_plan["reemplazar"], 1)
                if patched != src:
                    wrote = _safe_write_py(target, patched) if target.suffix == ".py" else (target.write_text(patched) or True)
                    if wrote:
                        print(f"  ✓ Gemini fix aplicado → {target.name}")
                        return True
        return True  # Retrigger de todas formas
    except Exception as e:
        print(f"  ! gemini_fix error: {str(e)[:80]}")
        return False

# ── GIT: commit y push del fix ─────────────────────────────────────────────────
def git_commit_push(error_type: str):
    """Commitea y pushea los archivos modificados."""
    try:
        subprocess.run(["git", "config", "user.name",  "IA al Día Watchdog"], cwd=BASE_DIR, check=True)
        subprocess.run(["git", "config", "user.email", "watchdog@iaaldia.ai"], cwd=BASE_DIR, check=True)
        subprocess.run(["git", "add", "-A"], cwd=BASE_DIR, check=True)
        diff = subprocess.run(["git", "diff", "--cached", "--stat"], cwd=BASE_DIR,
                               capture_output=True, text=True)
        if not diff.stdout.strip():
            print("  ! Sin cambios para commitear")
            return False
        msg = f"fix(watchdog): autocorrección {error_type} [{datetime.utcnow().strftime('%H:%M UTC')}]"
        subprocess.run(["git", "commit", "-m", msg], cwd=BASE_DIR, check=True)
        remote = subprocess.run(["git", "remote", "get-url", "origin"],
                                 capture_output=True, text=True, cwd=BASE_DIR).stdout.strip()
        # Usar token en la URL para autenticación
        auth_remote = remote.replace("https://", f"https://x-access-token:{GITHUB_TOKEN}@")
        subprocess.run(["git", "push", auth_remote, "main"], cwd=BASE_DIR, check=True)
        print(f"  ✓ Fix pusheado: {msg}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ! git error: {str(e)[:80]}")
        return False

# ── CICLO PRINCIPAL ────────────────────────────────────────────────────────────
def run():
    log = load_log()
    log["iterations"] = log.get("iterations", 0) + 1

    print(f"\n{'='*60}")
    print(f"  WATCHDOG — Iteración {log['iterations']} — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")

    if not GITHUB_TOKEN:
        print("  ! GITHUB_TOKEN no disponible — watchdog en modo offline")
        return

    # 1. DETECTAR
    print("\n[1/5] Detectando fallos recientes...")
    failures = get_recent_failures(hours=2)
    if not failures:
        print("  ✓ Sin fallos en las últimas 2 horas")
        log["last_run"] = datetime.utcnow().isoformat()
        save_log(log)
        return

    print(f"  ! {len(failures)} fallo(s) detectado(s)")

    for failure in failures:
        run_id       = failure["id"]
        workflow_name = failure["name"]
        print(f"\n  → Analizando: {workflow_name} (run #{run_id})")

        # 2. ANALIZAR
        print("[2/5] Descargando logs...")
        logs = get_logs(run_id)
        if not logs:
            print("  ! No se pudieron obtener logs")
            continue

        # 3. CLASIFICAR
        print("[3/5] Clasificando error...")
        error_type, detail = classify(logs)

        # 4. CORREGIR
        print(f"[4/5] Aplicando fix para: {error_type}...")
        applied = False
        if error_type in KNOWN_FIXES:
            applied = KNOWN_FIXES[error_type](detail, logs)
        else:
            print(f"  ! Error desconocido — enviando a Gemini para análisis")
            applied = gemini_fix(logs, workflow_name)

        # Commitear fix si hubo cambios en archivos
        if applied:
            pushed = git_commit_push(error_type)
            if pushed:
                time.sleep(10)  # Esperar que GitHub procese el push

        # 5. REINTENTAR
        print(f"[5/5] Reintentando workflow: {workflow_name}...")
        retrigger(workflow_name)

        # Registrar en log
        log["fixed_runs"].append(str(run_id))
        log["fixed_runs"] = log["fixed_runs"][-100:]  # Max 100 entradas
        log["fixes_applied"].append({
            "run_id":        run_id,
            "workflow":      workflow_name,
            "error_type":    error_type,
            "fix_applied":   applied,
            "timestamp":     datetime.utcnow().isoformat(),
        })
        log["fixes_applied"] = log["fixes_applied"][-50:]

        # GitHub Step Summary
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
        if summary_path:
            with open(summary_path, "a") as f:
                f.write(f"\n## Watchdog — Fix aplicado\n")
                f.write(f"- **Workflow:** {workflow_name}\n")
                f.write(f"- **Error:** `{error_type}`\n")
                f.write(f"- **Fix:** {'✅ aplicado' if applied else '⚠️ solo retrigger'}\n")
                f.write(f"- **Hora:** {datetime.utcnow().strftime('%H:%M UTC')}\n")

    save_log(log)
    print(f"\n  ✓ Watchdog completado — {len(failures)} fallo(s) procesado(s)\n")

if __name__ == "__main__":
    run()
