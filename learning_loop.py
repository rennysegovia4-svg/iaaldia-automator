#!/usr/bin/env python3
"""
learning_loop.py — Red neuronal de mejora continua para IA al Día.

Ciclo:
  1. OBSERVAR  — recolecta métricas reales de cada video publicado
  2. ANALIZAR  — encuentra correlaciones: qué hook/nicho/hora genera más views
  3. APRENDER  — actualiza "pesos" (scores) de cada decisión del canal
  4. ADAPTAR   — reescribe la estrategia para el próximo video
  5. REPETIR   — GitHub Actions lo corre 2x al día, siempre

Salidas:
  memory.json        — memoria de largo plazo (historial + pesos)
  viral_patterns.json — patrones virales (actualizado por viral_learner.py)
  strategy.json      — estrategia actual del canal (nicho, hooks, horario)
"""
import os, json, time, math
from pathlib import Path
from datetime import date, datetime, timedelta

BASE_DIR       = Path(__file__).parent
MEMORY_FILE    = BASE_DIR / "memory.json"
STRATEGY_FILE  = BASE_DIR / "strategy.json"
PATTERNS_FILE  = BASE_DIR / "viral_patterns.json"
ENV_FILE       = BASE_DIR / ".env"

# ── Env ────────────────────────────────────────────────────────────────────────
def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items()
                if k in ["GEMINI_API_KEY", "PEXELS_API_KEY"]})
    return env

ENV = load_env()
GEMINI_API_KEY = ENV.get("GEMINI_API_KEY", "")

# ── Memoria por defecto ────────────────────────────────────────────────────────
DEFAULT_MEMORY = {
    "version": 2,
    "updated": str(date.today()),
    "total_videos": 0,
    "videos": [],
    "niche_scores": {
        "deportes":           {"avg_views": 0, "total": 0, "score": 1.0, "trend": 0.0},
        "ia_noticias":        {"avg_views": 0, "total": 0, "score": 1.0, "trend": 0.0},
        "finanzas":           {"avg_views": 0, "total": 0, "score": 1.0, "trend": 0.0},
        "entretenimiento":    {"avg_views": 0, "total": 0, "score": 1.0, "trend": 0.0},
        "negocios_digitales": {"avg_views": 0, "total": 0, "score": 1.0, "trend": 0.0},
        "cripto_inversiones": {"avg_views": 0, "total": 0, "score": 1.0, "trend": 0.0},
        "productividad_ia":   {"avg_views": 0, "total": 0, "score": 1.0, "trend": 0.0},
        "politica_latam":     {"avg_views": 0, "total": 0, "score": 1.0, "trend": 0.0},
    },
    "hook_scores": {},
    "hora_scores": {"0": {"avg": 0, "n": 0}, "13": {"avg": 0, "n": 0},
                    "14": {"avg": 0, "n": 0}, "15": {"avg": 0, "n": 0},
                    "17": {"avg": 0, "n": 0}, "20": {"avg": 0, "n": 0},
                    "23": {"avg": 0, "n": 0}},
    "duracion_scores": {"55": {"avg": 0, "n": 0}, "58": {"avg": 0, "n": 0},
                        "60": {"avg": 0, "n": 0}, "62": {"avg": 0, "n": 0}},
    "learnings": [],
    "iteracion": 0,
}

DEFAULT_STRATEGY = {
    "updated": str(date.today()),
    "iteracion": 0,
    "niche_weights": {
        "deportes": 0.30,
        "ia_noticias": 0.20,
        "finanzas": 0.15,
        "entretenimiento": 0.10,
        "negocios_digitales": 0.10,
        "productividad_ia": 0.08,
        "cripto_inversiones": 0.05,
        "politica_latam": 0.02,
    },
    "best_hooks": [],
    "avoid_hooks": [],
    "best_hora": 17,
    "duracion_optima": 58,
    "recomendaciones": [],
    "nivel_confianza": 0.0,   # 0-1: sube con más datos
}

# ── IO ─────────────────────────────────────────────────────────────────────────
def load_memory() -> dict:
    if MEMORY_FILE.exists():
        try:
            m = json.loads(MEMORY_FILE.read_text())
            # Asegurar campos nuevos
            for niche in DEFAULT_MEMORY["niche_scores"]:
                m["niche_scores"].setdefault(niche, DEFAULT_MEMORY["niche_scores"][niche].copy())
            return m
        except: pass
    return DEFAULT_MEMORY.copy()

def save_memory(m: dict):
    m["updated"] = str(date.today())
    MEMORY_FILE.write_text(json.dumps(m, indent=2, ensure_ascii=False))

def load_strategy() -> dict:
    if STRATEGY_FILE.exists():
        try: return json.loads(STRATEGY_FILE.read_text())
        except: pass
    return DEFAULT_STRATEGY.copy()

def save_strategy(s: dict):
    s["updated"] = str(date.today())
    STRATEGY_FILE.write_text(json.dumps(s, indent=2, ensure_ascii=False))

# ── CAPA 1: OBSERVAR — recolectar métricas de YouTube ──────────────────────────
def build_youtube_clients():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    token_path   = BASE_DIR / "token.json"
    # Usar solo el scope que tiene el token existente — no pedir analytics por separado
    SCOPES = ["https://www.googleapis.com/auth/youtube"]
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            print(f"  ! Token refresh error: {str(e)[:80]}")
            return None, None
    if not creds or not creds.valid:
        return None, None
    yt  = build("youtube", "v3", credentials=creds)
    try:
        yta = build("youtubeAnalytics", "v2", credentials=creds)
    except Exception:
        yta = None  # Analytics es opcional
    return yt, yta

def get_channel_videos(yt, max_results=50) -> list:
    """Obtiene los últimos videos del canal con sus métricas básicas."""
    try:
        ch = yt.channels().list(part="id,statistics", mine=True).execute()
        if not ch.get("items"): return []
        ch_id = ch["items"][0]["id"]

        resp = yt.search().list(
            part="id,snippet", channelId=ch_id, type="video",
            order="date", maxResults=max_results,
            fields="items(id/videoId,snippet/title,snippet/publishedAt)"
        ).execute()

        video_ids = [i["id"]["videoId"] for i in resp.get("items", [])
                     if "videoId" in i.get("id", {})]
        if not video_ids: return []

        stats_resp = yt.videos().list(
            part="statistics,contentDetails,snippet",
            id=",".join(video_ids),
            fields="items(id,snippet/title,snippet/publishedAt,snippet/description,"
                   "statistics/viewCount,statistics/likeCount,statistics/commentCount,"
                   "contentDetails/duration)"
        ).execute()

        videos = []
        for item in stats_resp.get("items", []):
            stats = item.get("statistics", {})
            pub   = item["snippet"].get("publishedAt", "")
            try:
                hora = datetime.fromisoformat(pub.replace("Z", "+00:00")).hour
            except: hora = 0
            videos.append({
                "id":        item["id"],
                "titulo":    item["snippet"]["title"],
                "published": pub,
                "hora":      hora,
                "views":     int(stats.get("viewCount", 0)),
                "likes":     int(stats.get("likeCount", 0)),
                "comments":  int(stats.get("commentCount", 0)),
                "duracion":  item.get("contentDetails", {}).get("duration", ""),
            })
        return videos
    except Exception as e:
        print(f"  ! get_channel_videos: {str(e)[:60]}")
        return []

def enrich_with_analytics(yta, video_id: str, published: str) -> dict:
    """Obtiene watch time y retention vía YouTube Analytics API."""
    try:
        pub_date = published[:10]
        end_date = str(date.today())
        resp = yta.reports().query(
            ids="channel==MINE",
            startDate=pub_date,
            endDate=end_date,
            metrics="estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
            dimensions="video",
            filters=f"video=={video_id}"
        ).execute()
        rows = resp.get("rows", [])
        if rows:
            return {
                "watch_minutes":  rows[0][1],
                "avg_duration_s": rows[0][2],
                "avg_retention":  rows[0][3],
            }
    except: pass
    return {}

# ── CAPA 2: ANALIZAR — correlaciones y patrones ────────────────────────────────
def _weighted_avg(values: list, decay: float = 0.85) -> float:
    """Promedio ponderado: videos más recientes tienen más peso."""
    if not values: return 0.0
    total_w, total_v = 0.0, 0.0
    for i, v in enumerate(reversed(values)):
        w = decay ** i
        total_v += v * w
        total_w += w
    return total_v / total_w if total_w else 0.0

def analyze_niches(memory: dict) -> dict:
    """Calcula scores por nicho con decaimiento temporal."""
    videos = memory.get("videos", [])
    by_niche: dict = {}
    for v in videos:
        n = v.get("nicho", "ia_noticias")
        by_niche.setdefault(n, []).append(v.get("views", 0))

    scores = memory.get("niche_scores", {}).copy()
    global_avg = _weighted_avg([v.get("views", 0) for v in videos]) or 1

    for niche, view_list in by_niche.items():
        if niche not in scores:
            scores[niche] = {"avg_views": 0, "total": 0, "score": 1.0, "trend": 0.0}
        avg   = _weighted_avg(view_list)
        score = avg / global_avg if global_avg else 1.0
        trend = (view_list[-1] - view_list[0]) / max(view_list[0], 1) if len(view_list) > 1 else 0.0
        scores[niche].update({"avg_views": round(avg), "total": len(view_list),
                               "score": round(score, 3), "trend": round(trend, 3)})
    return scores

def analyze_hooks(memory: dict) -> dict:
    """Calcula scores de hooks basados en views promedio."""
    scores = memory.get("hook_scores", {}).copy()
    for v in memory.get("videos", []):
        hook = v.get("hook_formula", "")
        if not hook: continue
        views = v.get("views", 0)
        if hook not in scores:
            scores[hook] = {"avg": 0, "n": 0, "score": 1.0, "views_history": []}
        scores[hook]["views_history"].append(views)
        scores[hook]["views_history"] = scores[hook]["views_history"][-10:]
        scores[hook]["avg"]   = round(_weighted_avg(scores[hook]["views_history"]))
        scores[hook]["n"]    += 1
    global_avg = max(_weighted_avg([v.get("views", 0) for v in memory.get("videos", [])]), 1)
    for h in scores:
        scores[h]["score"] = round(scores[h]["avg"] / global_avg, 3)
    return scores

def analyze_timing(memory: dict) -> dict:
    """Calcula qué hora de publicación genera más views."""
    hora_data: dict = {}
    for v in memory.get("videos", []):
        h = str(v.get("hora", 0))
        hora_data.setdefault(h, []).append(v.get("views", 0))
    scores = {}
    for h, views in hora_data.items():
        scores[h] = {"avg": round(_weighted_avg(views)), "n": len(views)}
    return scores

# ── CAPA 3: APRENDER — actualizar pesos y extraer insights con Gemini ──────────
def gemini_synthesize(memory: dict, niche_scores: dict, hook_scores: dict) -> dict:
    """Gemini lee todos los datos y genera insights accionables + nueva estrategia."""
    if not GEMINI_API_KEY:
        return {}

    from google import genai

    top_videos = sorted(memory.get("videos", []), key=lambda x: x.get("views", 0), reverse=True)[:10]
    low_videos = sorted(memory.get("videos", []), key=lambda x: x.get("views", 0))[:5]

    top_hooks = sorted(hook_scores.items(), key=lambda x: x[1].get("score", 0), reverse=True)[:5]
    low_hooks = sorted(hook_scores.items(), key=lambda x: x[1].get("score", 0))[:3]

    niche_ranking = sorted(niche_scores.items(), key=lambda x: x[1].get("score", 0), reverse=True)

    prev_learnings = memory.get("learnings", [])[-5:]

    prompt = f"""Eres el estratega de YouTube más analítico del mundo. Tienes acceso a datos reales de un canal de Shorts en español.

ITERACIÓN: {memory.get('iteracion', 0) + 1}
TOTAL VIDEOS ANALIZADOS: {len(memory.get('videos', []))}

TOP 10 VIDEOS (más views):
{json.dumps([{'titulo': v['titulo'], 'views': v['views'], 'nicho': v.get('nicho','?'), 'hora': v.get('hora','?'), 'hook': v.get('hook_formula','?')[:60]} for v in top_videos], ensure_ascii=False, indent=2)}

5 VIDEOS MÁS BAJOS (para evitar sus patrones):
{json.dumps([{'titulo': v['titulo'], 'views': v['views'], 'nicho': v.get('nicho','?'), 'hook': v.get('hook_formula','?')[:60]} for v in low_videos], ensure_ascii=False, indent=2)}

RANKING DE NICHOS POR PERFORMANCE:
{json.dumps([{'nicho': k, 'avg_views': v['avg_views'], 'score': v['score'], 'trend': v.get('trend',0)} for k,v in niche_ranking], ensure_ascii=False, indent=2)}

HOOKS MÁS EFECTIVOS:
{json.dumps([{'hook': h[:80], 'avg_views': s['avg'], 'score': s['score']} for h,s in top_hooks], ensure_ascii=False, indent=2)}

HOOKS QUE FALLAN:
{json.dumps([{'hook': h[:80], 'avg_views': s['avg'], 'score': s['score']} for h,s in low_hooks], ensure_ascii=False, indent=2)}

APRENDIZAJES PREVIOS:
{json.dumps(prev_learnings, ensure_ascii=False)}

TAREA: Analiza todos los datos y genera un JSON de estrategia actualizada.

RESPONDE SOLO este JSON:
{{
  "niche_weights": {{
    "deportes": 0.30,
    "ia_noticias": 0.20,
    "finanzas": 0.15,
    "entretenimiento": 0.10,
    "negocios_digitales": 0.10,
    "productividad_ia": 0.08,
    "cripto_inversiones": 0.05,
    "politica_latam": 0.02
  }},
  "best_hooks": ["top 6 fórmulas de gancho basadas en los datos reales"],
  "avoid_hooks": ["3 patrones a evitar porque tuvieron bajos views"],
  "best_hora": 17,
  "duracion_optima": 58,
  "recomendaciones": [
    "recomendación concreta 1 basada en datos",
    "recomendación concreta 2",
    "recomendación concreta 3"
  ],
  "insight_semana": "el insight más importante aprendido esta iteración",
  "nivel_confianza": 0.45,
  "learnings_nuevos": ["aprendizaje nuevo 1 con dato numérico", "aprendizaje nuevo 2"]
}}

REGLAS:
- Los pesos en niche_weights deben sumar 1.0
- Basa TODO en los datos reales de arriba, no en suposiciones
- nivel_confianza: 0.1 si hay <5 videos, 0.4 si hay <20, 0.7 si hay <50, 0.9 si hay +50
- Si no hay suficientes datos, mantén pesos iguales y di "insuficientes datos para X"
"""

    client = genai.Client(api_key=GEMINI_API_KEY)
    for model in ["gemini-2.5-flash", "gemini-2.0-flash"]:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            text = resp.text.strip()
            if "```" in text:
                for part in text.split("```"):
                    part = part.strip().lstrip("json").strip()
                    if part.startswith("{"): text = part; break
            data = json.loads(text)
            print(f"  ✓ Síntesis Gemini ({model}) — confianza: {data.get('nivel_confianza',0):.0%}")
            return data
        except Exception as e:
            print(f"  ! Gemini {model}: {str(e)[:60]}")
            time.sleep(5)
    return {}

# ── CAPA 4: ADAPTAR — reescribir viral_patterns con nueva estrategia ───────────
def update_viral_patterns(strategy: dict):
    """Sincroniza viral_patterns.json con los hooks ganadores aprendidos."""
    if not PATTERNS_FILE.exists(): return
    try:
        patterns = json.loads(PATTERNS_FILE.read_text())
        if strategy.get("best_hooks"):
            # Los hooks aprendidos de nuestros propios videos van primero
            existing = patterns.get("hook_formulas", [])
            merged   = strategy["best_hooks"] + [h for h in existing if h not in strategy["best_hooks"]]
            patterns["hook_formulas"] = merged[:12]
        if strategy.get("insight_semana"):
            patterns["insight_clave"] = strategy["insight_semana"]
        patterns["updated"] = str(date.today())
        PATTERNS_FILE.write_text(json.dumps(patterns, indent=2, ensure_ascii=False))
        print("  ✓ viral_patterns.json sincronizado con aprendizajes propios")
    except Exception as e:
        print(f"  ! update_viral_patterns: {str(e)[:60]}")

# ── CAPA 5: REGISTRAR nuevo video ──────────────────────────────────────────────
def register_video(video_id: str, titulo: str, nicho: str, hook_formula: str,
                   hora_publicacion: int = 13):
    """Llama desde generate_short.py después de publicar un video."""
    memory = load_memory()
    existing_ids = {v["id"] for v in memory["videos"]}
    if video_id in existing_ids:
        return  # ya registrado
    memory["videos"].append({
        "id":           video_id,
        "titulo":       titulo,
        "nicho":        nicho,
        "hook_formula": hook_formula,
        "hora":         hora_publicacion,
        "published":    str(datetime.now()),
        "views":        0,
        "likes":        0,
        "comments":     0,
        "iteraciones_medido": 0,
    })
    memory["total_videos"] = len(memory["videos"])
    save_memory(memory)
    print(f"  ✓ Video registrado en memoria: {titulo[:50]}")

# ── CICLO PRINCIPAL ────────────────────────────────────────────────────────────
def run():
    print("\n" + "="*60)
    print(f"  LEARNING LOOP — Iteración {load_memory().get('iteracion', 0) + 1}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*60)

    memory   = load_memory()
    strategy = load_strategy()

    # ── 1. OBSERVAR: actualizar métricas de todos los videos ──────────────────
    print("\n[1/4] Observando métricas del canal...")
    yt, yta = build_youtube_clients()
    if yt:
        live_videos = get_channel_videos(yt, max_results=50)
        existing_ids = {v["id"]: i for i, v in enumerate(memory["videos"])}

        for lv in live_videos:
            vid_id = lv["id"]
            if vid_id in existing_ids:
                # Actualizar métricas de video ya registrado
                idx = existing_ids[vid_id]
                memory["videos"][idx]["views"]    = lv["views"]
                memory["videos"][idx]["likes"]    = lv["likes"]
                memory["videos"][idx]["comments"] = lv["comments"]
                memory["videos"][idx]["hora"]     = lv["hora"]
                memory["videos"][idx]["iteraciones_medido"] = \
                    memory["videos"][idx].get("iteraciones_medido", 0) + 1
                # Enriquecer con Analytics si tiene +24h
                if yta and memory["videos"][idx].get("iteraciones_medido", 0) <= 3:
                    extras = enrich_with_analytics(yta, vid_id, lv["published"])
                    memory["videos"][idx].update(extras)
            else:
                # Video nuevo (subido manualmente o no registrado)
                nicho = "ia_noticias"  # default
                for n_key in ["finanzas","negocios","cripto","productividad"]:
                    if n_key in lv["titulo"].lower():
                        nicho = n_key; break
                memory["videos"].append({**lv, "nicho": nicho, "hook_formula": "",
                                          "iteraciones_medido": 1})

        memory["total_videos"] = len(memory["videos"])
        total_views = sum(v.get("views", 0) for v in memory["videos"])
        print(f"  {len(live_videos)} videos actualizados | {total_views:,} views totales")
    else:
        print("  ! YouTube API no disponible — análisis con datos en caché")

    # ── 2. ANALIZAR: calcular scores ──────────────────────────────────────────
    print("\n[2/4] Analizando patrones...")
    niche_scores = analyze_niches(memory)
    hook_scores  = analyze_hooks(memory)
    hora_scores  = analyze_timing(memory)
    memory["niche_scores"] = niche_scores
    memory["hook_scores"]  = hook_scores
    memory["hora_scores"]  = hora_scores

    top_niche = max(niche_scores.items(), key=lambda x: x[1].get("score", 0))
    print(f"  Nicho líder: {top_niche[0]} (score {top_niche[1]['score']:.2f})")
    if hook_scores:
        top_hook = max(hook_scores.items(), key=lambda x: x[1].get("score", 0))
        print(f"  Mejor hook:  {top_hook[0][:60]}...")
    best_hora = max(hora_scores.items(), key=lambda x: x[1].get("avg", 0), default=(("17", {})))[0] if hora_scores else "17"
    print(f"  Mejor hora:  {best_hora}:00")

    # ── 3. APRENDER: síntesis con Gemini ──────────────────────────────────────
    print("\n[3/4] Sintetizando aprendizajes con Gemini...")
    synthesis = {}
    if len(memory.get("videos", [])) >= 3:
        synthesis = gemini_synthesize(memory, niche_scores, hook_scores)
    else:
        print(f"  ! Solo {len(memory.get('videos',[]))} videos — mínimo 3 para síntesis")

    # ── 4. ADAPTAR: actualizar estrategia ─────────────────────────────────────
    print("\n[4/4] Actualizando estrategia...")
    if synthesis:
        strategy.update({
            "niche_weights":   synthesis.get("niche_weights",   strategy["niche_weights"]),
            "best_hooks":      synthesis.get("best_hooks",       strategy.get("best_hooks", [])),
            "avoid_hooks":     synthesis.get("avoid_hooks",      strategy.get("avoid_hooks", [])),
            "best_hora":       synthesis.get("best_hora",        strategy.get("best_hora", 17)),
            "duracion_optima": synthesis.get("duracion_optima",  strategy.get("duracion_optima", 58)),
            "recomendaciones": synthesis.get("recomendaciones",  []),
            "insight_semana":  synthesis.get("insight_semana",   ""),
            "nivel_confianza": synthesis.get("nivel_confianza",  0.0),
        })
        new_learnings = synthesis.get("learnings_nuevos", [])
        if new_learnings:
            memory["learnings"] = (memory.get("learnings", []) + new_learnings)[-30:]
            print(f"  + {len(new_learnings)} aprendizajes nuevos guardados")

    strategy["iteracion"] = memory.get("iteracion", 0) + 1
    memory["iteracion"]   = strategy["iteracion"]

    # Sincronizar con viral_patterns.json
    update_viral_patterns(strategy)

    save_memory(memory)
    save_strategy(strategy)

    # ── Resumen GitHub Actions ─────────────────────────────────────────────────
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(f"\n## Learning Loop — Iteración {strategy['iteracion']}\n")
            f.write(f"**Confianza del modelo:** {strategy.get('nivel_confianza',0):.0%}\n")
            f.write(f"**Videos analizados:** {memory['total_videos']}\n\n")
            f.write(f"**Nicho líder:** `{top_niche[0]}` (score {top_niche[1]['score']:.2f})\n\n")
            f.write(f"**Insight:** {strategy.get('insight_semana','')}\n\n")
            f.write("**Recomendaciones:**\n")
            for r in strategy.get("recomendaciones", []):
                f.write(f"- {r}\n")
            f.write("\n**Aprendizajes acumulados:**\n")
            for l in memory.get("learnings", [])[-5:]:
                f.write(f"- {l}\n")

    print(f"\n  ✓ Iteración {strategy['iteracion']} completada")
    print(f"  ✓ Confianza del modelo: {strategy.get('nivel_confianza',0):.0%}")
    if strategy.get("insight_semana"):
        print(f"  ✓ Insight: {strategy['insight_semana'][:80]}")
    return strategy

if __name__ == "__main__":
    run()
