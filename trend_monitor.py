#!/usr/bin/env python3
"""
trend_monitor.py — Detecta temas virales en tiempo real y dispara publicación inmediata.

Flujo:
  1. Google Trends RSS: MX, AR, CO, CL, ES  (sin pytrends, sin API key)
  2. YouTube chart=mostPopular via OAuth existente
  3. RSS velocity: mismo tema en múltiples feeds
  4. Score viral compuesto (0-100)
  5. Si score > THRESHOLD y cooldown OK → dispatch workflow_dispatch en GitHub

Corre cada 2 horas via .github/workflows/viral_monitor.yml
"""

import os, json, re, time, sys, hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests

BASE_DIR   = Path(__file__).parent
ENV_FILE   = BASE_DIR / ".env"
STATE_FILE = BASE_DIR / "viral_state.json"

# ── Config ────────────────────────────────────────────────────────────────────
VIRAL_THRESHOLD  = 45       # score mínimo para disparar publicación
COOLDOWN_HOURS   = 4        # no publicar viral si ya se publicó hace < 4h
MAX_PER_DAY      = 3        # máximo de virales extra por día (no saturar)
GEOS             = ["MX", "AR", "CO", "CL", "ES"]
REPO             = "rennysegovia4-svg/iaaldia-automator"
PUBLISH_WORKFLOW = "publish_short.yml"

# Palabras clave por nicho — para filtrar si el tema es relevante para el canal
NICHE_KEYWORDS = {
    "ia_noticias": [
        "inteligencia artificial","chatgpt","openai","claude","gemini","gpt","ia ","robot",
        "tecnología","machine learning","deepmind","copilot","llama","mistral","groq",
    ],
    "finanzas": [
        "dólar","bitcoin","cripto","ethereum","bolsa","mercado","inflación","finanzas",
        "inversión","nasdaq","sp500","acciones","oro precio","peso","economía",
    ],
    "deportes": [
        "mundial","copa","champions","nba","nfl","tenis","fútbol","futbol","messi","ronaldo",
        "wimbledon","roland garros","us open","f1","fórmula 1","gol","partido","liga mx",
    ],
    "politica_latam": [
        "presidente","elecciones","gobierno","congreso","senado","ministro","política",
        "trump","milei","petro","sheinbaum","lula","xi jinping","putin",
    ],
    "entretenimiento": [
        "bad bunny","shakira","j balvin","karol g","reggaeton","escándalo","chisme",
        "famoso","netflix","serie","pelicula","oscar","grammy","taylor swift","drake",
        "peso pluma","bizarrap","maluma","anuel","nicki nicole","rosalía","nathy peluso",
        "farandula","celebridad","actor","cantante","reality","tiktok viral","trend",
    ],
    "negocios_digitales": [
        "amazon","apple","google","meta","microsoft","startup","unicornio","elon musk",
        "emprendedor","negocio online","dropshipping","shopify","tiktok ban",
    ],
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items()})
    return env

ENV = load_env()

def load_state():
    if STATE_FILE.exists():
        try: return json.loads(STATE_FILE.read_text())
        except: pass
    return {"last_viral": None, "published_today": 0, "published_topics": [], "last_reset": str(datetime.now(timezone.utc).date())}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))

def topic_id(topic):
    return hashlib.md5(topic.lower().strip().encode()).hexdigest()[:8]

def normalize(text):
    return re.sub(r'\s+', ' ', text.lower().strip())

def match_niches(topic_text):
    import re as _re
    topic_lower = normalize(topic_text)
    matched = []
    for niche, kws in NICHE_KEYWORDS.items():
        for kw in kws:
            pattern = r'\b' + _re.escape(kw.strip()) + r'\b'
            if _re.search(pattern, topic_lower):
                matched.append(niche)
                break
    return matched

# ── Fuente 1: Google Trends RSS ───────────────────────────────────────────────
def fetch_google_trends():
    """Retorna {topic: {countries: [...], traffic: str}} desde RSS de cada geo."""
    topics = {}
    for geo in GEOS:
        try:
            r = requests.get(
                f"https://trends.google.com/trending/rss?geo={geo}",
                timeout=10, headers={"User-Agent": "Mozilla/5.0"}
            )
            if r.status_code != 200:
                continue
            ns = {"ht": "https://trends.google.com/trending/rss"}
            root = ET.fromstring(r.text)
            for item in root.findall(".//item"):
                title_el   = item.find("title")
                traffic_el = item.find("ht:approx_traffic", ns)
                if title_el is None:
                    continue
                t  = title_el.text.strip()
                tr = traffic_el.text.strip() if traffic_el is not None else "100+"
                if t not in topics:
                    topics[t] = {"countries": [], "traffic": tr, "niches": []}
                topics[t]["countries"].append(geo)
                if not topics[t]["niches"]:
                    topics[t]["niches"] = match_niches(t)
        except Exception as e:
            print(f"  Trends {geo}: {e}")
        time.sleep(0.5)
    return topics

# ── Fuente 2: YouTube mostPopular ─────────────────────────────────────────────
def fetch_youtube_trending():
    """Retorna lista de {title, views, vph, video_id, channel} de videos populares."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        token_path = BASE_DIR / "token.json"
        if not token_path.exists():
            return []
        creds = Credentials.from_authorized_user_file(
            str(token_path), ["https://www.googleapis.com/auth/youtube"]
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        yt = build("youtube", "v3", credentials=creds)
        results = []
        now_utc = datetime.now(timezone.utc)

        for region in ["MX", "AR", "CO", "CL"]:
            try:
                r = yt.videos().list(
                    part="snippet,statistics",
                    chart="mostPopular",
                    regionCode=region,
                    maxResults=25,
                ).execute()
                for item in r.get("items", []):
                    s = item.get("statistics", {})
                    published = item["snippet"]["publishedAt"]
                    pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    hours = max(0.1, (now_utc - pub_dt).total_seconds() / 3600)
                    views = int(s.get("viewCount", 0))
                    results.append({
                        "title":      item["snippet"]["title"],
                        "video_id":   item["id"],
                        "channel":    item["snippet"]["channelTitle"],
                        "views":      views,
                        "vph":        round(views / hours, 0),
                        "hours_old":  round(hours, 1),
                        "region":     region,
                        "niches":     match_niches(item["snippet"]["title"] + " " + item["snippet"].get("description","")[:200]),
                    })
            except Exception:
                pass
            time.sleep(0.3)

        return results
    except Exception as e:
        print(f"  YouTube trending: {e}")
        return []

# ── Fuente 3: RSS velocity (nuestros feeds) ───────────────────────────────────
def fetch_rss_velocity():
    """Cuenta cuántos feeds nuestros cubren cada tema en las últimas 3 horas."""
    from niches import NICHES
    import feedparser
    recent_titles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=3)
    for niche_data in NICHES.values():
        for feed_url in niche_data.get("rss", []):
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:10]:
                    published = entry.get("published_parsed") or entry.get("updated_parsed")
                    if published:
                        pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                        if pub_dt >= cutoff:
                            recent_titles.append(normalize(entry.get("title", "")))
            except Exception:
                pass
            time.sleep(0.2)
    return recent_titles

# ── Motor de scoring ──────────────────────────────────────────────────────────
def score_topic(topic, trend_data, yt_videos, rss_titles):
    """Calcula score viral 0-100 para un tema de Google Trends."""
    score = 0
    debug = []

    # 1. Países en Google Trends
    countries = trend_data.get("countries", [])
    n_countries = len(countries)
    geo_score = min(40, n_countries * 15)
    score += geo_score
    debug.append(f"geo:{geo_score}({n_countries}países)")

    # 2. Tiene niches relevantes para el canal
    niches = trend_data.get("niches", [])
    if niches:
        score += 20
        debug.append(f"nicho:{niches[0]}")
    else:
        # Sin niche relevante = topic local no aplicable al canal
        return 0, "sin_niche", [], debug

    # 3. Coincide con videos trending de YouTube
    topic_lower = normalize(topic)
    yt_match_score = 0
    yt_context = ""
    for vid in yt_videos:
        if any(w in normalize(vid["title"]) for w in topic_lower.split() if len(w) > 3):
            vph = vid["vph"]
            if vph > 200000:
                yt_match_score = 30
            elif vph > 50000:
                yt_match_score = 20
            elif vph > 10000:
                yt_match_score = 10
            else:
                yt_match_score = 5
            yt_context = f"{vid['title']} ({vid['views']:,} vistas, {vid['vph']:,.0f}vph)"
            break
    score += yt_match_score
    if yt_match_score:
        debug.append(f"yt:{yt_match_score}")

    # 4. Velocidad en RSS propios
    rss_hits = sum(1 for t in rss_titles if any(w in t for w in topic_lower.split() if len(w) > 4))
    rss_score = min(20, rss_hits * 7)
    score += rss_score
    if rss_score:
        debug.append(f"rss:{rss_score}({rss_hits}feeds)")

    primary_niche = niches[0] if niches else "ia_noticias"
    context = yt_context or f"Trending en {', '.join(countries)} — {trend_data.get('traffic','')}"
    return min(100, score), primary_niche, context, debug

# ── Trigger GitHub Actions ────────────────────────────────────────────────────
def dispatch_viral_short(viral_topic, viral_context, viral_score, viral_niche):
    token = ENV.get("GITHUB_TOKEN", "")
    if not token:
        print("  Sin GITHUB_TOKEN — no se puede disparar workflow.")
        return False

    payload = {
        "ref": "main",
        "inputs": {
            "tipo":          "short",
            "viral_topic":   viral_topic,
            "viral_context": viral_context[:300],
            "viral_score":   str(viral_score),
            "viral_niche":   viral_niche,
        }
    }
    r = requests.post(
        f"https://api.github.com/repos/{REPO}/actions/workflows/{PUBLISH_WORKFLOW}/dispatches",
        json=payload,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        },
        timeout=15,
    )
    if r.status_code == 204:
        print(f"  ✅ Workflow disparado: score={viral_score} | {viral_topic[:60]}")
        return True
    else:
        print(f"  ❌ GitHub API {r.status_code}: {r.text[:100]}")
        return False

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    now = datetime.now(timezone.utc)
    print(f"\n{'='*55}")
    print(f"  Trend Monitor — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*55}")

    state = load_state()

    # Reset contador diario
    today = str(now.date())
    if state.get("last_reset") != today:
        state["published_today"] = 0
        state["published_topics"] = []
        state["last_reset"] = today

    # Cooldown: no publicar si ya se publicó viral muy recientemente
    if state.get("last_viral"):
        last_dt = datetime.fromisoformat(state["last_viral"])
        if (now - last_dt).total_seconds() < COOLDOWN_HOURS * 3600:
            remaining = COOLDOWN_HOURS - (now - last_dt).total_seconds() / 3600
            print(f"  En cooldown — {remaining:.1f}h restantes para siguiente viral")
            return

    if state.get("published_today", 0) >= MAX_PER_DAY:
        print(f"  Límite diario alcanzado ({MAX_PER_DAY} virales/día)")
        return

    print("[1/4] Google Trends RSS...")
    trends = fetch_google_trends()
    print(f"      {len(trends)} temas trending en LATAM")

    print("[2/4] YouTube mostPopular...")
    yt_videos = fetch_youtube_trending()
    print(f"      {len(yt_videos)} videos analizados")

    print("[3/4] RSS velocity...")
    rss_titles = fetch_rss_velocity()
    print(f"      {len(rss_titles)} artículos recientes en feeds")

    print("[4/4] Scoring...")
    candidates = []
    for topic, data in trends.items():
        # No repetir temas ya publicados hoy
        if topic_id(topic) in state.get("published_topics", []):
            continue
        score, niche, context, debug = score_topic(topic, data, yt_videos, rss_titles)
        if score > 0:
            candidates.append({
                "topic":   topic,
                "score":   score,
                "niche":   niche,
                "context": context,
                "debug":   debug,
                "countries": data.get("countries", []),
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)

    print(f"\n  Top 5 candidatos:")
    for c in candidates[:5]:
        bar = "█" * (c["score"] // 10)
        print(f"  [{c['score']:>3}] {bar:10} {c['topic'][:45]} | {'+'.join(c['countries'])}")

    # Verificar si hay alguno sobre el umbral
    winner = next((c for c in candidates if c["score"] >= VIRAL_THRESHOLD), None)

    if not winner:
        print(f"\n  Sin viral (threshold={VIRAL_THRESHOLD}). Mejor score: {candidates[0]['score'] if candidates else 0}")
        return

    print(f"\n  🔥 VIRAL DETECTADO: {winner['topic']}")
    print(f"     Score: {winner['score']} | Nicho: {winner['niche']}")
    print(f"     Contexto: {winner['context'][:80]}")

    success = dispatch_viral_short(
        winner["topic"],
        winner["context"],
        winner["score"],
        winner["niche"],
    )

    if success:
        state["last_viral"] = now.isoformat()
        state["published_today"] = state.get("published_today", 0) + 1
        state["published_topics"] = state.get("published_topics", []) + [topic_id(winner["topic"])]
        save_state(state)
        print(f"  Estado guardado — virales hoy: {state['published_today']}/{MAX_PER_DAY}")


if __name__ == "__main__":
    main()
