#!/usr/bin/env python3
"""
viral_learner.py — Aprende de virales de YouTube Shorts y actualiza patrones.
Corre diariamente vía GitHub Actions. Los patrones se usan en generate_short.py.
"""
import os, json, time, sys
from pathlib import Path
from datetime import date, datetime

BASE_DIR      = Path(__file__).parent
PATTERNS_FILE = BASE_DIR / "viral_patterns.json"
ENV_FILE      = BASE_DIR / ".env"

# ── Cargar env ─────────────────────────────────────────────────────────────────
def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if k in
                ["GEMINI_API_KEY", "PEXELS_API_KEY"]})
    return env

ENV            = load_env()
GEMINI_API_KEY = ENV.get("GEMINI_API_KEY", "")

# ── Queries de búsqueda por nicho ──────────────────────────────────────────────
NICHE_QUERIES = {
    "ia_noticias":        ["inteligencia artificial shorts viral", "IA noticias shorts 2026", "chatgpt shorts español"],
    "finanzas":           ["finanzas personales shorts viral", "como ahorrar dinero shorts", "inversiones shorts latam"],
    "negocios_digitales": ["negocio digital shorts viral", "emprendimiento shorts latam", "ganar dinero online shorts"],
    "cripto_inversiones": ["bitcoin shorts viral español", "criptomonedas shorts 2026", "cripto latam shorts"],
    "productividad_ia":   ["productividad ia shorts", "herramientas ia gratis shorts", "chatgpt trucos shorts"],
}

GLOBAL_QUERIES = [
    "shorts viral español 2026",
    "shorts millones de vistas español",
    "youtube shorts trending latin america",
]

# ── YouTube API ────────────────────────────────────────────────────────────────
def build_youtube():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    token_path   = BASE_DIR / "token.json"
    secrets_path = BASE_DIR / "client_secrets.json"
    SCOPES = ["https://www.googleapis.com/auth/youtube"]

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            print(f"  ! Token refresh: {str(e)[:80]}")
            return None
    if not creds or not creds.valid:
        print("  ! Token no válido para YouTube API")
        return None
    return build("youtube", "v3", credentials=creds)

def search_viral_shorts(yt, query, max_results=10):
    """Busca Shorts virales con YouTube Data API v3."""
    try:
        resp = yt.search().list(
            part="snippet",
            q=query + " #shorts",
            type="video",
            videoDuration="short",
            order="viewCount",
            regionCode="CL",
            relevanceLanguage="es",
            maxResults=max_results,
            fields="items(id/videoId,snippet/title,snippet/description,snippet/channelTitle)"
        ).execute()

        video_ids = [i["id"]["videoId"] for i in resp.get("items", []) if "videoId" in i.get("id", {})]
        if not video_ids:
            return []

        # Obtener stats de cada video
        stats_resp = yt.videos().list(
            part="statistics,contentDetails,snippet",
            id=",".join(video_ids),
            fields="items(id,snippet/title,snippet/description,snippet/tags,statistics/viewCount,statistics/likeCount,contentDetails/duration)"
        ).execute()

        videos = []
        for item in stats_resp.get("items", []):
            stats = item.get("statistics", {})
            views = int(stats.get("viewCount", 0))
            if views < 50_000:
                continue
            videos.append({
                "id":          item["id"],
                "titulo":      item["snippet"]["title"],
                "descripcion": item["snippet"].get("description", "")[:300],
                "tags":        item["snippet"].get("tags", [])[:8],
                "views":       views,
                "likes":       int(stats.get("likeCount", 0)),
                "duracion":    item.get("contentDetails", {}).get("duration", ""),
            })
        return sorted(videos, key=lambda x: x["views"], reverse=True)
    except Exception as e:
        print(f"  ! search_viral_shorts({query[:30]}): {str(e)[:60]}")
        return []

# ── Análisis con Gemini ────────────────────────────────────────────────────────
def analyze_with_gemini(videos_by_niche: dict, existing_patterns: dict) -> dict:
    """Manda los datos de virales a Gemini y pide análisis de patrones."""
    if not GEMINI_API_KEY:
        print("  ! GEMINI_API_KEY no disponible para análisis")
        return {}

    from google import genai

    # Construir resumen de virales
    lines = []
    for niche, videos in videos_by_niche.items():
        lines.append(f"\n=== NICHO: {niche} ===")
        for v in videos[:8]:
            lines.append(f"  [{v['views']:,} views] \"{v['titulo']}\"")
            if v.get("descripcion"):
                lines.append(f"    desc: {v['descripcion'][:150]}")

    viral_summary = "\n".join(lines)

    prompt = f"""Eres un experto en YouTube Shorts con acceso a datos reales de virales.
Analiza estos videos virales de YouTube Shorts en español y extrae patrones accionables.

VIDEOS VIRALES REALES (ordenados por views):
{viral_summary}

PATRONES ACTUALES DEL CANAL (mejóralos):
{json.dumps(existing_patterns.get("hook_formulas", []), ensure_ascii=False, indent=2)}

TAREA: Analiza y entrega un JSON con estos campos exactos:

{{
  "hook_formulas": [
    "fórmula de gancho que aparece en múltiples virales, lista top 12"
  ],
  "title_patterns": [
    "patrón de título: [número] + [verbo impactante] + [resultado], lista top 8"
  ],
  "palabras_prohibidas": [
    "palabras que matan el CTR en thumbnails y títulos, lista top 10"
  ],
  "palabras_clave_virales": [
    "palabras que aparecen en múltiples títulos virales, lista top 15"
  ],
  "estructura_gancho_optima": "descripción de la estructura del gancho que más se repite en los virales",
  "duracion_optima_segundos": 58,
  "patrones_por_nicho": {{
    "ia_noticias":        {{"hooks": ["top 3 hooks para este nicho"], "topics": ["top 3 temas virales"]}},
    "finanzas":           {{"hooks": ["top 3 hooks"], "topics": ["top 3 temas"]}},
    "negocios_digitales": {{"hooks": ["top 3 hooks"], "topics": ["top 3 temas"]}},
    "cripto_inversiones": {{"hooks": ["top 3 hooks"], "topics": ["top 3 temas"]}},
    "productividad_ia":   {{"hooks": ["top 3 hooks"], "topics": ["top 3 temas"]}}
  }},
  "insight_clave": "1 insight no obvio que explica por qué estos videos son virales",
  "recomendacion_thumbnail": "qué tipo de thumbnail genera más CTR según los patrones observados"
}}

REGLAS:
- Solo usa patrones que observes en los datos reales arriba
- Sé específico: "Fórmula X hace Y" no "optimiza el contenido"
- Si no hay suficientes datos para un nicho, pon patrones basados en los globales
- Responde SOLO el JSON, sin markdown
"""

    client = genai.Client(api_key=GEMINI_API_KEY)
    for model in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-pro"]:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            text = resp.text.strip()
            if "```" in text:
                for part in text.split("```"):
                    part = part.strip().lstrip("json").strip()
                    if part.startswith("{"): text = part; break
            data = json.loads(text)
            print(f"  ✓ Análisis Gemini completado ({model})")
            return data
        except Exception as e:
            print(f"  ! Gemini {model}: {str(e)[:60]}")
            time.sleep(5)
    return {}

# ── Guardar / cargar patrones ──────────────────────────────────────────────────
def load_patterns() -> dict:
    if PATTERNS_FILE.exists():
        try:
            return json.loads(PATTERNS_FILE.read_text())
        except:
            pass
    return _default_patterns()

def _default_patterns() -> dict:
    return {
        "updated": str(date.today()),
        "hook_formulas": [
            "Acaban de confirmar que [hecho real impactante]",
            "El [N]% de [grupo] ya está [haciendo algo]",
            "Despidieron a [N] personas. El motivo fue [causa]",
            "[Empresa] acaba de anunciar que [hecho verificado]",
            "Esto ya existe. Y nadie en LATAM lo sabe.",
            "Si tienes [N] y no haces esto, los estás perdiendo",
            "Con [N] al mes puedes tener [resultado] en [N] años",
            "Esta herramienta hace en 3 min lo que te toma 3 horas",
        ],
        "title_patterns": [
            "[Número] [cosa] que [resultado impactante] 🤖",
            "[Empresa/persona] acaba de [acción]: lo que nadie dice",
            "Por qué el [N]% de [grupo] ya usa [solución]",
            "[Acción concreta] en [N] días: caso real",
        ],
        "palabras_prohibidas": ["increíble", "revolucionario", "impresionante", "fascinante", "épico"],
        "palabras_clave_virales": ["confirmaron", "despidieron", "ya existe", "nadie sabe", "datos reales"],
        "estructura_gancho_optima": "Dato impactante + cifra real + consecuencia personal en ≤8 palabras",
        "duracion_optima_segundos": 58,
        "patrones_por_nicho": {},
        "insight_clave": "Los virales confirman algo que el espectador sospechaba pero no tenía datos para creer",
        "recomendacion_thumbnail": "Cara con expresión de sorpresa + número grande + fondo de color sólido",
        "top_videos_semana": [],
    }

def save_patterns(patterns: dict):
    patterns["updated"] = str(date.today())
    PATTERNS_FILE.write_text(json.dumps(patterns, indent=2, ensure_ascii=False))
    print(f"  ✓ Patrones guardados en {PATTERNS_FILE.name}")

# ── Main ───────────────────────────────────────────────────────────────────────
def run():
    print("\n" + "="*55)
    print(f"  Viral Learner — {date.today()}")
    print("="*55)

    existing = load_patterns()
    yt = build_youtube()

    videos_by_niche = {}
    all_top = []

    if yt:
        # Buscar virales por nicho
        for niche_key, queries in NICHE_QUERIES.items():
            niche_videos = []
            for q in queries[:2]:  # 2 queries por nicho = 10 unidades API c/u = 200 total
                vids = search_viral_shorts(yt, q, max_results=8)
                niche_videos.extend(vids)
                time.sleep(1)
            # Deduplicar por id
            seen = set()
            deduped = []
            for v in sorted(niche_videos, key=lambda x: x["views"], reverse=True):
                if v["id"] not in seen:
                    seen.add(v["id"])
                    deduped.append(v)
            videos_by_niche[niche_key] = deduped[:10]
            total_v = sum(v["views"] for v in deduped[:5])
            print(f"  {niche_key}: {len(deduped)} videos | top views: {deduped[0]['views']:,}" if deduped else f"  {niche_key}: 0 videos")
            all_top.extend(deduped[:3])

        # Búsquedas globales de virales
        global_videos = []
        for q in GLOBAL_QUERIES[:2]:
            global_videos.extend(search_viral_shorts(yt, q, max_results=10))
            time.sleep(1)
        if global_videos:
            videos_by_niche["_global"] = sorted(global_videos, key=lambda x: x["views"], reverse=True)[:15]
            print(f"  global: {len(videos_by_niche['_global'])} videos")
    else:
        print("  ! YouTube API no disponible — usando análisis solo con patrones anteriores")

    # Analizar con Gemini
    if any(videos_by_niche.values()):
        new_patterns = analyze_with_gemini(videos_by_niche, existing)
        if new_patterns:
            # Merge: preservar campos que Gemini no devuelve
            merged = {**existing, **new_patterns}
            merged["top_videos_semana"] = [
                {"titulo": v["titulo"], "views": v["views"], "id": v["id"]}
                for v in sorted(all_top, key=lambda x: x["views"], reverse=True)[:20]
            ]
            save_patterns(merged)

            # Resumen para GitHub Actions Step Summary
            summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
            if summary_path:
                with open(summary_path, "a") as f:
                    f.write(f"\n## Viral Learner — {date.today()}\n")
                    f.write(f"**Insight clave:** {merged.get('insight_clave','')}\n\n")
                    f.write(f"**Hooks top:**\n")
                    for h in merged.get("hook_formulas", [])[:5]:
                        f.write(f"- {h}\n")
                    f.write(f"\n**Videos más virales:**\n")
                    for v in merged.get("top_videos_semana", [])[:5]:
                        f.write(f"- [{v['titulo']}](https://youtube.com/watch?v={v['id']}) — {v['views']:,} views\n")
            return merged
    else:
        print("  ! Sin datos nuevos — patrones anteriores sin cambios")

    return existing

if __name__ == "__main__":
    patterns = run()
    print(f"\n  Insight: {patterns.get('insight_clave', 'N/A')}")
    print(f"  Hook top: {patterns.get('hook_formulas', ['N/A'])[0]}")
    print(f"  Thumbnail: {patterns.get('recomendacion_thumbnail', 'N/A')}\n")
