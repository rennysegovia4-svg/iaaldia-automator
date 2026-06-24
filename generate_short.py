#!/usr/bin/env python3
"""
IA al Día v6.0 — Integración 8 repos:
  1. MoneyPrinterTurbo — captions PIL con palabra activa en CYAN
  2. MoneyPrinter      — caja de fondo + contorno en captions
  3. Wav2Lip           — lip sync opcional (USE_WAV2LIP=False por defecto)
  4. Fay               — evaluado, no viable headless sin GUI
  5. PaddleGAN         — cinematic curves + vignette via FFmpeg
  6. Manim             — intro animado 2s "IA al Día"
  7. stable-diffusion-videos — multi-clip con crossfade xfade entre presentadores
  8. MoviePy           — concatenación intro + video principal
"""

import os, json, random, requests, subprocess, tempfile, time, re, base64, glob, textwrap, sys
import feedparser, shutil, urllib.parse, urllib.request, asyncio
from pathlib import Path
from datetime import datetime, date

# Idioma: "es" (español, canal principal) o "en" (inglés, canal clon)
LANG_CODE = os.environ.get("LANG_CODE", "es")
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import edge_tts, imageio_ffmpeg
from mutagen.mp3 import MP3

FFMPEG = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()

BASE_DIR       = Path(__file__).parent
ENV_FILE       = BASE_DIR / ".env"
# Soporte multi-canal: canal ES usa token.json, canal EN usa token_en.json
_suffix        = f"_{LANG_CODE}" if LANG_CODE != "es" else ""
CLIENT_SECRETS = BASE_DIR / f"client_secrets{_suffix}.json"
TOKEN_FILE     = BASE_DIR / f"token{_suffix}.json"
CREDITS_FILE   = BASE_DIR / "credits.json"
SCOPES         = ["https://www.googleapis.com/auth/youtube"]
GEMINI_MODELS  = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-pro"]

_MAC_FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
_LIN_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_MAC_REG  = "/System/Library/Fonts/Supplemental/Arial.ttf"
_LIN_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = _MAC_FONT if os.path.exists(_MAC_FONT) else _LIN_FONT
FONT_REG  = _MAC_REG  if os.path.exists(_MAC_REG)  else _LIN_REG

COST_PER_VIDEO  = {"gemini_tts": 0.006, "imagen4_thumb": 0.04, "gemini_pro": 0.005}
CREDIT_TOTAL    = 300.0
ALERT_THRESHOLD = 30.0

# ── Wav2Lip (repo 3) — deshabilitado por defecto; requiere ~700MB modelo ──────
USE_WAV2LIP = False

# Nichos: se cargan dinámicamente según el día
from niches import get_niche, NICHES
from learning_loop import load_strategy, register_video

# Estrategia aprendida — pesos dinámicos por nicho
_STRATEGY  = load_strategy()
_NICHE_KEY, _NICHE = get_niche(LANG_CODE, _STRATEGY.get("niche_weights"))
PRESENTER_QUERIES = _NICHE["pexels_queries"]
RSS_FEEDS         = _NICHE["rss_feeds"]
print(f"[Nicho del día] {_NICHE['nombre']} ({_NICHE_KEY}) | confianza modelo: {_STRATEGY.get('nivel_confianza',0):.0%}")

# ── Personas narradoras — rotan cada día para máxima variedad ──────────────────
NARRATOR_PERSONAS = {
    "periodista_urgente": {
        "instruccion": (
            "Hablas como locutor de noticias de última hora en radio. Tono serio y urgente. "
            "Mezcla frases cortas de golpe (3-5 palabras) con frases de contexto más largas (10-15 palabras). "
            "Empieza SIEMPRE con el dato más impactante, nunca con presentación. "
            "Usa: 'Hace pocas horas...', 'Acaba de confirmarse...', 'Esto acaba de salir:'"
        ),
        "conectores": ["y esto es lo más importante:", "pero hay algo que nadie menciona:", "mira lo que dicen los datos:"],
        "cierre": "Sígueme para estar informado antes que nadie.",
        "voice_edge": ("es-MX-JorgeNeural", "+8%", "-1Hz"),
    },
    "amigo_que_sabe": {
        "instruccion": (
            "Hablas como si le contaras un secreto a un amigo cercano. Tono cálido, casual y directo. "
            "Usa 'mira', 'te cuento', 'fíjate', 'y lo más loco es que...'. "
            "Alterna frases cortas de impacto con frases más largas de explicación. "
            "Suenas como alguien que acaba de descubrir algo y no puede guardárselo."
        ),
        "conectores": ["y aquí viene lo bueno:", "pero espera, hay más:", "y lo que nadie te cuenta es esto:"],
        "cierre": "Sígueme, que yo te traigo todo esto primero.",
        "voice_edge": ("es-CO-GonzaloNeural", "-3%", "-2Hz"),
    },
    "provocador": {
        "instruccion": (
            "Desafías al espectador. Preguntas que incomodan seguidas de datos duros. "
            "Ritmo variable: una pregunta corta, pausa implícita, dato largo contundente. "
            "Usa: '¿En serio todavía no sabes esto?', 'La mayoría se equivoca aquí.', 'Te voy a decir algo incómodo:'. "
            "No eres agresivo, pero sí directo al punto de que duele un poco."
        ),
        "conectores": ["y aquí es donde la gente se equivoca:", "pero nadie quiere escuchar esto:", "la realidad es esta:"],
        "cierre": "Sígueme si quieres saber lo que los demás no te dicen.",
        "voice_edge": ("es-ES-AlvaroNeural", "+2%", "+1Hz"),
    },
    "analista_frio": {
        "instruccion": (
            "Solo datos. Sin emoción, sin hipérboles. Hablas como analista que presenta cifras en una reunión. "
            "Frases claras y directas. Varía la longitud para que no suene monótono: "
            "una cifra corta, una explicación media, una consecuencia larga. "
            "Usa: 'El dato es simple:', 'Los números muestran que...', 'Tres cifras que importan:'"
        ),
        "conectores": ["el segundo dato es más relevante:", "la consecuencia directa:", "lo que estos números indican:"],
        "cierre": "Sígueme para análisis con datos reales cada día.",
        "voice_edge": ("es-AR-TomasNeural", "-5%", "-3Hz"),
    },
    "storyteller": {
        "instruccion": (
            "Cuentas una historia corta con inicio, giro inesperado y lección. "
            "Frases cortas para tensión, frases largas para descripción. Fluido, natural. "
            "Empieza poniendo al espectador en escena: 'Imagina esto:', 'El martes pasado, algo pasó.', 'Hay una empresa que conozco.'. "
            "El giro debe llegar en el segundo tercio del guión, no al final."
        ),
        "conectores": ["y aquí viene el giro:", "entonces pasó algo que nadie esperaba:", "la lección fue clara:"],
        "cierre": "Sígueme para más historias que te enseñan algo real.",
        "voice_edge": ("es-MX-DaliaNeural", "-8%", "-2Hz"),
    },
    "coach": {
        "instruccion": (
            "Motivador pero concreto, nunca con frases vacías. Cada oración lleva a una acción. "
            "Energía alta al inicio, baja un poco en el medio para explicar, sube al final para el CTA. "
            "Usa: 'Tienes 60 segundos para entender esto.', 'Un solo cambio puede transformar tu resultado.', 'La acción concreta es esta:'. "
            "Prohibido el relleno: cada palabra debe tener un propósito."
        ),
        "conectores": ["el siguiente paso concreto:", "y si lo aplicas hoy mismo:", "esto es lo que debes hacer:"],
        "cierre": "Sígueme para más herramientas que sí funcionan.",
        "voice_edge": ("es-MX-JorgeNeural", "+5%", "+0Hz"),
    },
}

# Plantillas de estructura — 4 formatos que rotan
SCRIPT_TEMPLATES = {
    "NEWS_FLASH":      "GANCHO(dato urgente real) → QUÉ PASÓ(quién, qué, dónde, cifra real) → POR QUÉ IMPORTA PARA TI(impacto personal directo) → ACCIÓN HOY(qué hace el espectador)",
    "HISTORIA_GIRO":   "ESCENA INICIAL(personaje/empresa/situación concreta) → CONFLICTO(el problema o dato sorprendente) → GIRO INESPERADO(lo que nadie esperaba) → LECCIÓN APLICABLE(qué haces tú con esto)",
    "LISTA_RAPIDA":    "PROMESA(voy a darte N cosas en 60 segundos) → ITEM 1 con dato real → ITEM 2 con dato real → ITEM 3 con dato real → REMATE(por qué importan juntas)",
    "PREGUNTA_RETORICA":"PREGUNTA QUE DUELE O SORPRENDE → DATO que la responde de forma inesperada → REVELACIÓN(la respuesta correcta que nadie te dijo) → CTA concreto y accionable",
}

# Selección determinista por día — mismo nicho, misma persona durante el día
_day_num      = datetime.now().timetuple().tm_yday
_PERSONA_KEYS  = list(NARRATOR_PERSONAS.keys())
_TEMPLATE_KEYS = list(SCRIPT_TEMPLATES.keys())
_PERSONA_KEY   = _PERSONA_KEYS[_day_num % len(_PERSONA_KEYS)]
_TEMPLATE_KEY  = _TEMPLATE_KEYS[(_day_num + 2) % len(_TEMPLATE_KEYS)]
_PERSONA       = NARRATOR_PERSONAS[_PERSONA_KEY]
_TEMPLATE      = SCRIPT_TEMPLATES[_TEMPLATE_KEY]


def _validate_guion(guion: str) -> str:
    """
    Valida que el guión encaje en 58-62 segundos (140-175 palabras a ~160 wpm).
    Si es muy largo, corta en el último punto antes del límite.
    Limpia caracteres problemáticos para TTS.
    """
    # Limpiar chars problemáticos para TTS
    for bad, good in [("«", '"'), ("»", '"'), ("–", "-"), ("—", "-"),
                      ("\n", " "), ("  ", " "), ("...", ".")]:
        guion = guion.replace(bad, good)
    guion = guion.strip()

    words = guion.split()
    if len(words) > 178:
        truncated = " ".join(words[:178])
        last_punct = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
        if last_punct > len(truncated) * 0.65:
            guion = truncated[:last_punct + 1]
        else:
            guion = truncated + "."

    return guion


_AFFILIATES_BY_NICHE = {
    "ia_noticias":       "\n\n💡 Herramientas IA que recomiendo:\n→ ChatGPT: https://chat.openai.com\n→ Claude AI: https://claude.ai\n→ Gemini: https://gemini.google.com\n→ Perplexity: https://perplexity.ai",
    "finanzas":          "\n\n💡 Recursos de finanzas:\n→ Fintual: https://fintual.cl\n→ FXCM: https://www.fxcm.com\n→ Binance: https://binance.com",
    "negocios_digitales":"\n\n💡 Herramientas para tu negocio:\n→ Shopify: https://shopify.com\n→ Canva: https://canva.com\n→ Dropi: https://dropi.co",
    "cripto_inversiones": "\n\n⚠️ No es consejo financiero.\n💡 Exchanges confiables:\n→ Binance: https://binance.com\n→ Buda: https://buda.com",
    "productividad_ia":  "\n\n💡 Herramientas gratis que uso:\n→ ChatGPT: https://chat.openai.com\n→ Canva IA: https://canva.com\n→ Notion AI: https://notion.so",
}
AFFILIATES = _AFFILIATES_BY_NICHE.get(_NICHE_KEY, _AFFILIATES_BY_NICHE["ia_noticias"])

def load_env():
    env = {}
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

ENV            = load_env()
GEMINI_API_KEY = ENV["GEMINI_API_KEY"]
PEXELS_API_KEY = ENV["PEXELS_API_KEY"]


# ── Créditos ───────────────────────────────────────────────────────────────────
def load_credits():
    if CREDITS_FILE.exists():
        try: return json.loads(CREDITS_FILE.read_text())
        except: pass
    return {"spent": 0.0, "runs": 0, "last_run": ""}

def update_credits(used_tts, used_imagen, used_pro):
    data  = load_credits()
    cost  = (COST_PER_VIDEO["gemini_tts"]    * used_tts +
             COST_PER_VIDEO["imagen4_thumb"] * used_imagen +
             COST_PER_VIDEO["gemini_pro"]    * used_pro)
    data["spent"]   += cost
    data["runs"]    += 1
    data["last_run"] = str(date.today())
    CREDITS_FILE.write_text(json.dumps(data, indent=2))
    remaining = CREDIT_TOTAL - data["spent"]
    print(f"      Crédito: ${cost:.3f} hoy | Total: ${data['spent']:.2f} | Resto: ${remaining:.2f}")
    if remaining < ALERT_THRESHOLD:
        print(f"\n  ⚠️  ALERTA: Solo ${remaining:.2f} restantes. Recarga en console.cloud.google.com\n")
        s = os.environ.get("GITHUB_STEP_SUMMARY", "")
        if s: open(s, "a").write(f"\n⚠️ CRÉDITO BAJO: ${remaining:.2f} de $300\n")
    return data


# ── Paso 1: RSS + research ─────────────────────────────────────────────────────
def get_headlines():
    headlines = []
    for url in RSS_FEEDS:
        try:
            for e in feedparser.parse(url).entries[:4]:
                t = e.get("title", "").strip()
                if t and len(t) > 10:
                    headlines.append(t)
        except: pass
    return headlines[:12]

def research_topic(topic):
    """3 búsquedas DuckDuckGo para hechos verificables."""
    results = []
    for query in [topic + " 2026", topic + " estadisticas datos", topic + " empresa reporte"]:
        try:
            data = urllib.parse.urlencode({"q": query, "b": ""}).encode()
            req  = urllib.request.Request(
                "https://html.duckduckgo.com/html/", data=data,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)<', html)
            results.extend(s.strip()[:220] for s in snippets[:4])
        except: pass
        if len(results) >= 8: break
    return "\n".join(f"• {r}" for r in results[:10]) if results else ""


# ── Paso 2: Script Gemini 2.5 Pro ─────────────────────────────────────────────
def _build_viral_context(niche_key: str) -> str:
    """Carga patrones virales aprendidos e inyecta en el prompt."""
    try:
        from viral_learner import load_patterns
        p = load_patterns()
        hooks   = p.get("hook_formulas", [])[:6]
        titles  = p.get("title_patterns", [])[:4]
        insight = p.get("insight_clave", "")
        thumb   = p.get("recomendacion_thumbnail", "")
        niche_p = p.get("patrones_por_nicho", {}).get(niche_key, {})
        niche_h = niche_p.get("hooks", [])[:3]
        niche_t = niche_p.get("topics", [])[:3]
        words   = p.get("palabras_clave_virales", [])[:8]
        banned  = p.get("palabras_prohibidas", [])[:5]
        updated = p.get("updated", "")

        block = f"""
PATRONES VIRALES APRENDIDOS DE YOUTUBE (actualizado {updated}):
Insight clave: {insight}
Hooks que más funcionan en este nicho:
{chr(10).join(f'• {h}' for h in (niche_h or hooks[:3]))}
Patrones de título viral:
{chr(10).join(f'• {t}' for t in titles)}
Palabras que aparecen en virales: {', '.join(words)}
Palabras prohibidas (matan el CTR): {', '.join(banned)}
Temas trending en este nicho: {', '.join(niche_t) if niche_t else 'según noticias del día'}
Thumbnail que más CTR genera: {thumb}
"""
        return block
    except Exception:
        return ""

def generate_script(headlines, research):
    client  = genai.Client(api_key=GEMINI_API_KEY)
    h_block = "\n".join(f"- {h}" for h in headlines) if headlines else "tendencias IA 2026"
    r_block = f"\nHECHOS VERIFICADOS:\n{research}\n" if research else ""
    viral_ctx = _build_viral_context(_NICHE_KEY)

    # ── Canal en inglés [AI-Youtube-Shorts-Generator + ShortGPT] ─────────────
    if LANG_CODE == "en":
        prompt = f"""You are the most influential AI tech journalist in the English-speaking world.
Your channel has millions of followers because you always report REAL facts with REAL data.

TODAY'S REAL NEWS (use as base):
{h_block}

VERIFIED FACTS FROM RESEARCH:
{r_block if r_block else "No additional data — use only the news above."}

TASK: Write a YouTube Short script of 58-62 seconds (155-170 words in English).

HOOK (first 3-5 words, must stop the scroll — pick ONE formula):
• "They just confirmed that [real shocking fact]"
• "[Real number]% of [group] is already [doing something with AI]"
• "[Company] just fired [real number] people. The reason was AI."
• "This already exists. Nobody in [country] knows about it."

REQUIRED STRUCTURE:
[0-5s]   HOOK — real fact, real number, immediate impact
[5-20s]  CONTEXT — why it matters, verified stat
[20-38s] CONCRETE CASE — real company/country/person. Name them.
[38-50s] CONSEQUENCE — what happens if ignored
[50-62s] CALL TO ACTION — what viewer can do TODAY + "Follow for daily AI updates."

STRICT RULES:
- ONLY use facts from the news above. If unsure, say "reports indicate" — never invent stats.
- Max 8 words per sentence. Direct voice. No filler words.
- Natural English, not robotic.

RESPOND JSON only (no markdown):
{{
  "titulo": "SEO title: main keyword at start, max 52 chars, 1 emoji at end",
  "descripcion": "2 sentences with main keyword. Concrete data. #Shorts #AI #ArtificialIntelligence #ChatGPT #Technology #AINews",
  "tags": ["ai 2026","artificial intelligence news","chatgpt update","ai tools","machine learning","ai jobs","future of ai","automation","ai replacing jobs","tech news","ai daily","ai shorts"],
  "guion": "full script 155-170 words, ready to read",
  "hook_texto": "first 5-7 exact words of the script"
}}"""
        used_pro = False
        response = None
        for model in GEMINI_MODELS:
            for attempt in range(3):
                try:
                    response = client.models.generate_content(model=model, contents=prompt)
                    used_pro = (model == "gemini-2.5-pro")
                    break
                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower(): break
                    if attempt < 2: time.sleep(15 * (attempt + 1))
            if response: break
        if not response: return _fallback_script(), False
        text = response.text.strip()
        if "```" in text:
            for part in text.split("```"):
                part = part.strip().lstrip("json").strip()
                if part.startswith("{"): text = part; break
        try:    return json.loads(text), used_pro
        except: return _fallback_script(), False
    # ─────────────────────────────────────────────────────────────────────────

    niche_ctx  = _NICHE.get("prompt_nicho", "")
    niche_tags = json.dumps(_NICHE["tags"], ensure_ascii=False)
    niche_hash = _NICHE["hashtags"]
    canal_name = _NICHE["nombre"]

    prompt = f"""Eres un creador de contenido de habla hispana con millones de seguidores.
Tu canal "{canal_name}" triunfa porque suenas HUMANO, no robótico. Cada guión tiene personalidad propia.

══ CONTEXTO DEL NICHO ══
{niche_ctx}

══ ESTILO DE NARRADOR HOY: {_PERSONA_KEY.upper().replace("_"," ")} ══
{_PERSONA["instruccion"]}
Conectores que usas naturalmente: {" / ".join(_PERSONA["conectores"])}
Cierre de canal: "{_PERSONA["cierre"]}"

══ PLANTILLA DE ESTRUCTURA HOY: {_TEMPLATE_KEY} ══
{_TEMPLATE}

══ PATRONES VIRALES APRENDIDOS ══
{viral_ctx}

══ NOTICIAS REALES DE HOY (usa como base, no inventes) ══
{h_block}

══ DATOS VERIFICADOS (cita al menos 1) ══
{r_block if r_block else "Usa solo las noticias de arriba. Si no tienes dato exacto, di 'según reportes'."}

══ TAREA ══
Escribe UN guión de YouTube Short de 58-62 segundos (entre 145 y 175 palabras).

REGLAS DE ORO:
1. El gancho empieza con el dato más impactante. NUNCA con "Hola" o presentación.
2. Varía el largo de las oraciones: mezcla frases cortas (impacto) con frases más largas (explicación).
   Ejemplo natural: "Esto acaba de confirmarse. [Nombre real] despidió a 500 personas esta semana.
   No fue de golpe, venía gestándose hace 8 meses. Lo que nadie te explica es el motivo real."
3. Usa conectores humanos del estilo asignado (ver arriba). Prohibido: "increíble", "revolucionario", "épico".
4. Español latinoamericano conversacional. Nada de lenguaje de presentación corporativa.
5. SOLO hechos verificados. Si no tienes la cifra exacta, di "según fuentes" o "se estima que".
6. El cierre usa la frase exacta del narrador asignado (ver arriba).

RESPONDE JSON sin markdown:
{{
  "titulo": "Título SEO: keyword principal al inicio, máx 52 chars, 1 emoji al final",
  "descripcion": "2 oraciones con keyword. Dato concreto. {niche_hash}",
  "tags": {niche_tags},
  "guion": "guión completo 145-175 palabras, CON PERSONALIDAD, listo para leer en voz alta",
  "hook_texto": "primeras 6-8 palabras exactas del guión"
}}"""

    used_pro = False
    response = None
    for model in GEMINI_MODELS:
        for attempt in range(3):
            try:
                response = client.models.generate_content(model=model, contents=prompt)
                used_pro = (model == "gemini-2.5-pro")
                break
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower(): break
                if attempt < 2: time.sleep(15 * (attempt + 1))
        if response: break

    if not response:
        return _fallback_script(), False

    text = response.text.strip()
    if "```" in text:
        for part in text.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"): text = part; break
    try:
        result = json.loads(text)
        result["guion"] = _validate_guion(result.get("guion", ""))
        return result, used_pro
    except:
        return _fallback_script(), False

def _fallback_script():
    fb = _NICHE.get("fallback", {})
    return {
        "titulo":      fb.get("titulo", "IA 2026: lo que nadie te cuenta 🤖"),
        "descripcion": fb.get("descripcion", "Contenido de valor para América Latina. #Shorts"),
        "tags":        _NICHE.get("tags", ["ia 2026","inteligencia artificial","shorts"]),
        "guion":       fb.get("guion", "Contenido próximamente. Sígueme para más."),
        "hook_texto":  fb.get("hook_texto", "Esto es lo que nadie te dice"),
    }


# ── Paso 3: TTS — 4 capas de fallback, siempre produce audio ──────────────────

def _elevenlabs_tts(text: str, path: str) -> bool:
    """ElevenLabs — voz más humana disponible. Requiere ELEVENLABS_API_KEY en .env."""
    try:
        env = load_env()
        api_key = env.get("ELEVENLABS_API_KEY", "")
        if not api_key:
            return False
        # Diego (es): voz masculina latina natural
        voice_id = env.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            json={
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.48, "similarity_boost": 0.78, "style": 0.28}
            },
            timeout=30
        )
        if r.status_code == 200 and len(r.content) > 2000:
            open(path, "wb").write(r.content)
            print("      Voz: ElevenLabs ✓"); return True
        print(f"      ElevenLabs: HTTP {r.status_code}")
    except Exception as e:
        print(f"      ElevenLabs: {str(e)[:55]}")
    return False

def _gemini_tts(text: str, path: str) -> bool:
    try:
        from google.genai import types as gt
        c = genai.Client(api_key=GEMINI_API_KEY)
        # Aoede = voz femenina más natural en español que Charon
        voice_name = "Aoede" if LANG_CODE == "es" else "Charon"
        r = c.models.generate_content(
            model="gemini-2.5-flash-preview-tts", contents=text,
            config=gt.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=gt.SpeechConfig(voice_config=gt.VoiceConfig(
                    prebuilt_voice_config=gt.PrebuiltVoiceConfig(voice_name=voice_name)
                ))
            )
        )
        part = r.candidates[0].content.parts[0]
        if not (hasattr(part, "inline_data") and part.inline_data and part.inline_data.data):
            return False
        raw = base64.b64decode(part.inline_data.data)
        if len(raw) < 1000: return False
        rp = path.replace(".mp3", "_raw.pcm")
        open(rp, "wb").write(raw)
        ok = subprocess.run(
            [FFMPEG, "-y", "-f", "s16le", "-ar", "24000", "-ac", "1",
             "-i", rp, "-c:a", "libmp3lame", "-b:a", "192k", path],
            capture_output=True).returncode == 0
        if os.path.exists(rp): os.remove(rp)
        if ok and os.path.exists(path) and os.path.getsize(path) > 1000:
            print(f"      Voz: Gemini TTS {voice_name} ✓"); return True
    except Exception as e:
        if "429" not in str(e) and "quota" not in str(e).lower():
            print(f"      Gemini TTS: {str(e)[:55]}")
    return False

async def _edge_tts_async(text: str, path: str, persona_key: str = "periodista_urgente"):
    if LANG_CODE == "en":
        voice, rate, pitch = "en-US-GuyNeural", "-5%", "-2Hz"
    else:
        persona = NARRATOR_PERSONAS.get(persona_key, NARRATOR_PERSONAS["periodista_urgente"])
        voice, rate, pitch = persona["voice_edge"]
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume="+15%").save(path)

def _polish_audio(path: str):
    """Compresión + normalización de loudness para voz más cálida y presente."""
    polished = path.replace(".mp3", "_pol.mp3")
    try:
        r = subprocess.run([
            FFMPEG, "-y", "-i", path,
            "-af", (
                "acompressor=threshold=-18dB:ratio=3:attack=5:release=100:makeup=2,"
                "loudnorm=I=-14:LRA=7:TP=-1.5,"
                "equalizer=f=250:width_type=o:width=2:g=-2,"
                "equalizer=f=3000:width_type=o:width=1:g=1"
            ),
            "-c:a", "libmp3lame", "-b:a", "192k", polished
        ], capture_output=True, timeout=30)
        if r.returncode == 0 and os.path.exists(polished) and os.path.getsize(polished) > 1000:
            os.replace(polished, path)
    except Exception:
        if os.path.exists(polished):
            try: os.remove(polished)
            except: pass

def generate_audio(text: str, path: str, persona_key: str = "periodista_urgente") -> bool:
    """4 capas de fallback — siempre produce audio válido."""
    # Capa 1: ElevenLabs (más humano, requiere API key opcional)
    if _elevenlabs_tts(text, path):
        _polish_audio(path); return True

    # Capa 2: Gemini TTS
    if _gemini_tts(text, path):
        _polish_audio(path); return True

    # Capa 3: Edge-TTS con voz de la persona (3 intentos)
    for attempt in range(3):
        try:
            asyncio.run(_edge_tts_async(text, path, persona_key))
            if os.path.exists(path) and os.path.getsize(path) > 2000:
                label = "" if attempt == 0 else f" (retry {attempt})"
                print(f"      Voz: Edge-TTS {persona_key}{label} ✓")
                _polish_audio(path); return False
        except Exception as e:
            print(f"      Edge-TTS intento {attempt+1}: {str(e)[:55]}")
            if attempt < 2: time.sleep(4)

    # Capa 4: gTTS como último recurso absoluto
    try:
        from gtts import gTTS
        gTTS(text=text, lang="es", slow=False).save(path)
        if os.path.exists(path) and os.path.getsize(path) > 2000:
            print("      Voz: gTTS último recurso ✓")
            _polish_audio(path); return False
    except Exception as e:
        print(f"      gTTS: {str(e)[:55]}")

    # Fallback nuclear: tono de audio para que el video no falle
    print("      ⚠️  TODOS LOS TTS FALLARON — audio de emergencia")
    word_count  = len(text.split())
    est_dur     = max(30, int(word_count / 2.6))
    subprocess.run([
        FFMPEG, "-y", "-f", "lavfi",
        "-i", f"aevalsrc=0.0*sin(440*2*PI*t):s=44100",
        "-t", str(est_dur), "-c:a", "libmp3lame", "-b:a", "128k", path
    ], capture_output=True)
    return False


# ── Paso 4: Presentador Pexels — multi-clip xfade (stable-diffusion-videos) ───

def _download_pexels_clip(query, tmp_dir, idx):
    """Descarga y escala un clip de Pexels a 1080x1920."""
    headers = {"Authorization": PEXELS_API_KEY}
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search", headers=headers,
            params={"query": query, "orientation": "portrait",
                    "per_page": 15, "size": "medium"}, timeout=12
        )
        videos = r.json().get("videos", [])
        usable = [v for v in videos if v.get("duration", 0) >= 5]
        if not usable: return None

        video = random.choice(usable[:8])
        files = sorted(video["video_files"],
                       key=lambda x: x.get("width", 0) * x.get("height", 0), reverse=True)
        portrait = [f for f in files if f.get("width", 0) >= 720
                    and f.get("width", 999) <= f.get("height", 1)]
        chosen   = portrait[0] if portrait else files[0]

        raw = os.path.join(tmp_dir, f"pexels_raw_{idx}.mp4")
        dl  = requests.get(chosen["link"], stream=True, timeout=45)
        with open(raw, "wb") as f:
            for chunk in dl.iter_content(8192): f.write(chunk)
        if os.path.getsize(raw) < 50000: return None

        scaled = os.path.join(tmp_dir, f"pexels_scaled_{idx}.mp4")
        subprocess.run([
            FFMPEG, "-y", "-i", raw,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an",
            scaled
        ], capture_output=True)
        if os.path.exists(scaled) and os.path.getsize(scaled) > 10000:
            return scaled
    except: pass
    return None

def get_multi_presenter_video(tmp_dir, duration):
    """
    [stable-diffusion-videos] Descarga 2 clips de Pexels distintos y aplica
    crossfade xfade en el punto medio — da variedad visual sin GPU.
    """
    queries = PRESENTER_QUERIES.copy()
    random.shuffle(queries)
    clips = []

    for query in queries:
        if len(clips) >= 2: break
        clip = _download_pexels_clip(query, tmp_dir, len(clips))
        if clip:
            clips.append((query, clip))

    if not clips:
        return None

    # Un solo clip: loop directo
    if len(clips) == 1:
        q, c = clips[0]
        looped = os.path.join(tmp_dir, "presenter_loop.mp4")
        subprocess.run([
            FFMPEG, "-y", "-stream_loop", "-1", "-i", c,
            "-t", str(duration + 1),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an", looped
        ], capture_output=True)
        print(f"      Presentador: '{q}' ✓")
        return looped if os.path.exists(looped) else None

    # Dos clips: loop cada uno a mitad de duración + margen para xfade
    half     = duration / 2
    xfade_d  = 1.2   # duración del crossfade (segundos)
    offset   = half - xfade_d / 2

    c1_loop = os.path.join(tmp_dir, "clip1_loop.mp4")
    c2_loop = os.path.join(tmp_dir, "clip2_loop.mp4")
    for (_, src), dst, t in [(clips[0], c1_loop, half + xfade_d + 1),
                              (clips[1], c2_loop, half + xfade_d + 1)]:
        subprocess.run([
            FFMPEG, "-y", "-stream_loop", "-1", "-i", src,
            "-t", str(t), "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an", dst
        ], capture_output=True)

    xfade_out = os.path.join(tmp_dir, "presenter_xfade.mp4")
    result = subprocess.run([
        FFMPEG, "-y", "-i", c1_loop, "-i", c2_loop,
        "-filter_complex",
        f"[0:v][1:v]xfade=transition=fade:duration={xfade_d}:offset={offset:.2f}[vout]",
        "-map", "[vout]",
        "-t", str(duration + 1),
        "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-an", xfade_out
    ], capture_output=True)

    if result.returncode == 0 and os.path.exists(xfade_out) and os.path.getsize(xfade_out) > 10000:
        print(f"      Presentador: '{clips[0][0]}' + '{clips[1][0]}' xfade ✓")
        return xfade_out

    # fallback: solo primer clip
    print(f"      Presentador: '{clips[0][0]}' (xfade falló, usando 1 clip)")
    return c1_loop if os.path.exists(c1_loop) else None


# ── Paso 5: Whisper captions ───────────────────────────────────────────────────
def transcribe_whisper(audio_path):
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("tiny", device="cpu", compute_type="int8",
                             download_root="/tmp/whisper_models")
        lang = "en" if LANG_CODE == "en" else "es"
        segs, _ = model.transcribe(audio_path, language=lang, word_timestamps=True)
        words   = []
        for seg in segs:
            for w in (seg.words or []):
                wd = w.word.strip()
                if wd: words.append({"word": wd, "start": w.start, "end": w.end})
        if words:
            print(f"      Whisper: {len(words)} palabras ✓")
            return words
    except Exception as e:
        print(f"      Whisper no disponible: {str(e)[:50]}")
    return []

def estimate_words(script, duration):
    words = script.split()
    tpw   = (duration - 1.0) / max(len(words), 1)
    return [{"word": w, "start": 0.5 + i*tpw, "end": 0.5 + (i+1)*tpw}
            for i, w in enumerate(words)]


# ── Captions PIL — MoneyPrinterTurbo + MoneyPrinter style ─────────────────────
def render_caption_strip(words, tmp_dir, W=1080, cap_h=270):
    """
    [MoneyPrinterTurbo + MoneyPrinter] Renderiza grupos de palabras con PIL:
    - Palabra activa: CYAN 96px con sombra
    - Contexto anterior: blanco 62px semi-transparente
    - Caja oscura de fondo (MoneyPrinter style)
    Exporta como webm yuva420p para overlay con canal alfa.
    """
    caps_dir = os.path.join(tmp_dir, "cap_frames")
    os.makedirs(caps_dir, exist_ok=True)

    try:
        fb  = ImageFont.truetype(FONT_BOLD, 96)
        fsm = ImageFont.truetype(FONT_BOLD, 62)
    except:
        fb = fsm = ImageFont.load_default()

    cap_paths  = []
    cap_durs   = []

    for i, wd in enumerate(words):
        img  = Image.new("RGBA", (W, cap_h), (0, 0, 0, 0))

        # [MoneyPrinter] fondo oscuro semi-transparente detrás del texto
        bg = Image.new("RGBA", (W, cap_h), (0, 0, 0, 160))
        img.alpha_composite(bg)
        draw = ImageDraw.Draw(img)

        # Grupo de palabras: [prev] [ACTIVA] [siguiente]
        group = []
        if i > 0:
            group.append((words[i-1]["word"], fsm, (255, 255, 255, 150)))
        group.append((wd["word"], fb, (0, 220, 255, 255)))   # CYAN activa
        if i < len(words) - 1:
            group.append((words[i+1]["word"], fsm, (255, 255, 255, 110)))

        # Medir ancho total para centrar
        try:
            total_w = sum(draw.textlength(g[0], font=g[1]) for g in group) + 22 * (len(group)-1)
        except:
            total_w = sum(len(g[0]) * 40 for g in group)
        x  = max(16, (W - total_w) // 2)
        cy = cap_h // 2

        for text, font, color in group:
            is_active = (color == (0, 220, 255, 255))
            if is_active:
                # [MoneyPrinterTurbo] sombra multi-direccional en palabra activa
                for dx, dy in [(4,4),(-4,4),(4,-4),(-4,-4),(0,5)]:
                    try:
                        draw.text((x+dx, cy+dy), text, font=font,
                                  fill=(0,0,0,190), anchor="lm")
                    except TypeError:
                        draw.text((x+dx, cy - font.size//2 + dy), text,
                                  font=font, fill=(0,0,0,190))
            try:
                draw.text((x, cy), text, font=font, fill=color, anchor="lm")
                tw = draw.textlength(text, font=font)
            except TypeError:
                draw.text((x, cy - font.size//2), text, font=font, fill=color)
                tw = len(text) * 40
            x += tw + 22

        path = os.path.join(caps_dir, f"cap_{i:04d}.png")
        img.save(path)
        cap_paths.append(path)
        cap_durs.append(max(0.06, wd["end"] - wd["start"]))

    # FFmpeg concat → webm con alfa
    concat_f = os.path.join(tmp_dir, "cap_concat.txt")
    with open(concat_f, "w") as f:
        for path, dur in zip(cap_paths, cap_durs):
            f.write(f"file '{path}'\nduration {dur:.3f}\n")
        f.write(f"file '{cap_paths[-1]}'\n")

    cap_vid = os.path.join(tmp_dir, "cap_strip.webm")
    r = subprocess.run([
        FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_f,
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
        "-b:v", "600k", "-auto-alt-ref", "0", cap_vid
    ], capture_output=True, timeout=120)

    if r.returncode == 0 and os.path.exists(cap_vid) and os.path.getsize(cap_vid) > 1000:
        print(f"      Captions PIL: {len(words)} frames CYAN ✓")
        return cap_vid

    print("      Captions PIL: falló webm, usando drawtext fallback")
    return None


# ── Intro animado Manim ────────────────────────────────────────────────────────
def make_manim_intro(output_path):
    """
    [Manim] Intro animado de 2s: "IA al Día" con línea cyan que se dibuja.
    Requiere: pip install manim + apt libcairo2-dev libpango1.0-dev
    """
    try:
        scene_code = textwrap.dedent("""\
            from manim import *
            config.pixel_width  = 1080
            config.pixel_height = 1920
            config.frame_rate   = 25
            config.frame_width  = 4.5
            config.frame_height = 8.0

            class IntroIAalDia(Scene):
                def setup(self):
                    self.camera.background_color = "#08101E"
                def construct(self):
                    title = Text("IA al Dia", font_size=92, weight=BOLD, color=WHITE)
                    sub   = Text("Inteligencia Artificial · Todos los dias",
                                 font_size=26, color=GRAY_B)
                    line  = Line(LEFT * 3.0, RIGHT * 3.0,
                                 color=ManimColor("#00DCFF"), stroke_width=6)
                    sub.next_to(title, DOWN, buff=0.14)
                    line.next_to(sub,  DOWN, buff=0.20)
                    self.play(Write(title, run_time=0.75))
                    self.play(Create(line, run_time=0.45),
                              FadeIn(sub,  run_time=0.45))
                    self.wait(0.80)
        """)

        scene_file = "/tmp/manim_iaaldia_intro.py"
        with open(scene_file, "w") as f:
            f.write(scene_code)

        r = subprocess.run([
            "manim", scene_file, "IntroIAalDia",
            "--format=mp4", "--media_dir=/tmp/manim_media", "-q", "m",
        ], capture_output=True, timeout=120)

        files = glob.glob("/tmp/manim_media/**/*.mp4", recursive=True)
        if files:
            shutil.copy(sorted(files)[-1], output_path)
            print("      Manim intro: IA al Día animado ✓")
            return True
    except Exception as e:
        print(f"      Manim intro: omitido ({str(e)[:55]})")
    return False


# ── Concatenar intro + video (MoviePy) ────────────────────────────────────────
def prepend_intro(intro_path, main_path, output_path):
    """
    [MoviePy] Concatena el intro Manim con el video principal.
    Fallback a FFmpeg concat si MoviePy no está disponible.
    """
    try:
        from moviepy.editor import VideoFileClip, concatenate_videoclips
        intro = VideoFileClip(intro_path)
        main  = VideoFileClip(main_path)
        final = concatenate_videoclips([intro, main], method="compose")
        final.write_videofile(
            output_path, codec="libx264", audio_codec="aac",
            fps=25, preset="fast", logger=None
        )
        intro.close(); main.close(); final.close()
        print("      MoviePy: intro + video concatenados ✓")
        return True
    except Exception as e:
        print(f"      MoviePy concat: {str(e)[:50]}")

    # FFmpeg fallback
    try:
        concat_f = output_path + "_concat.txt"
        with open(concat_f, "w") as f:
            f.write(f"file '{intro_path}'\nfile '{main_path}'\n")
        r = subprocess.run([
            FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_f,
            "-c:v", "libx264", "-preset", "fast", "-crf", "17",
            "-c:a", "aac", "-b:a", "192k", output_path
        ], capture_output=True, timeout=120)
        os.remove(concat_f)
        if r.returncode == 0:
            print("      FFmpeg concat: intro + video ✓")
            return True
    except Exception as e:
        print(f"      Concat fallback: {str(e)[:50]}")
    return False


# ── Wav2Lip — lip sync opcional (repo 3) ──────────────────────────────────────
def apply_wav2lip(face_path, audio_path, output_path):
    """
    [Wav2Lip] Sincroniza movimientos labiales con el audio.
    Requiere ~700MB de modelo + GPU recomendada (CPU: ~8 min/video).
    Habilitado con USE_WAV2LIP = True arriba.
    """
    if not USE_WAV2LIP:
        return False
    try:
        wav2lip_dir = "/tmp/wav2lip_repo"
        if not os.path.exists(wav2lip_dir):
            subprocess.run([
                "git", "clone", "--depth=1",
                "https://github.com/Rudrabha/Wav2Lip.git", wav2lip_dir
            ], capture_output=True, timeout=120)

        model_path = "/tmp/wav2lip_gan.pth"
        if not os.path.exists(model_path):
            urllib.request.urlretrieve(
                "https://huggingface.co/numz/wav2lip_studio/resolve/main/Wav2Lip/wav2lip_gan.pth",
                model_path
            )
        r = subprocess.run([
            "python", f"{wav2lip_dir}/inference.py",
            "--checkpoint_path", model_path,
            "--face", face_path, "--audio", audio_path,
            "--outfile", output_path, "--nosmooth"
        ], capture_output=True, timeout=600)
        if r.returncode == 0 and os.path.exists(output_path):
            print("      Wav2Lip: lip sync ✓"); return True
    except Exception as e:
        print(f"      Wav2Lip: {str(e)[:55]}")
    return False

# Fay (https://github.com/xszyou/Fay): avatares 2.5D/3D con lip sync complejo.
# No implementado: requiere display/GUI, base de datos, WebSocket — no viable headless.


# ── Paso 6: Música ambient ─────────────────────────────────────────────────────
def make_ambient(duration, path):
    try:
        expr = ("aevalsrc=0.04*sin(2*PI*130.8*t)*abs(sin(2*PI*0.18*t))+"
                "0.03*sin(2*PI*196.0*t)*abs(sin(2*PI*0.18*t+1.5)):s=44100")
        return subprocess.run(
            [FFMPEG, "-y", "-f", "lavfi", "-i", expr,
             "-t", str(duration + 1),
             "-af", f"afade=t=in:d=2,afade=t=out:st={duration-2}:d=2",
             "-c:a", "aac", "-b:a", "64k", path],
            capture_output=True).returncode == 0
    except: return False


# ── Paso 7: Ensamblar con efectos PaddleGAN + captions PIL ────────────────────
def assemble(presenter_vid, audio_path, music_path,
             words, hook_text, cap_vid, output_path, duration):
    """
    [PaddleGAN] Aplica cinematic curves + vignette vía FFmpeg.
    [MoneyPrinterTurbo/MoneyPrinter] Overlay de caption strip PIL con alfa.
    Fallback a drawtext si cap_vid no está disponible.
    """

    def sf(t):
        for old, new in [("'",""),("\"",""),("\\",""),("%","pct"),(":",""),
                         ("¿",""),("¡",""),("\n"," "),
                         ("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n")]:
            t = t.replace(old, new)
        return t[:44]

    # [PaddleGAN] Cinematic grade: curvas para sombras frías + luces cálidas
    vf_grade = (
        "eq=contrast=1.12:brightness=0.02:saturation=1.25,"
        "curves="
          "r='0/0 0.08/0.10 0.92/0.96 1/1':"
          "g='0/0.02 0.5/0.51 1/0.97':"
          "b='0/0.05 0.5/0.52 1/0.93',"
        "vignette=PI/5:eval=init"    # [MoviePy-inspired] vignette cinematico
    )

    # Elementos fijos: gradiente, hook, branding
    fixed_filters = [
        "drawbox=x=0:y=1560:w=1080:h=360:color=black@0.60:t=fill",
    ]
    if hook_text:
        h = sf(hook_text)
        fixed_filters.append(
            f"drawtext=fontfile='{FONT_BOLD}':text='{h}'"
            f":fontcolor=white:fontsize=88"
            f":x=(w-text_w)/2:y=(h/2)-80"
            f":shadowcolor=black@0.99:shadowx=5:shadowy=5"
            f":bordercolor=black:borderw=4"
            f":enable='between(t,0,4.0)'"
        )
    fixed_filters += [
        f"drawtext=fontfile='{FONT_BOLD}':text='IA al Dia'"
        f":fontcolor=white:fontsize=38:x=36:y=30"
        f":shadowcolor=black@0.9:shadowx=3:shadowy=3",
        "drawbox=x=36:y=78:w=165:h=4:color=0x00DCFF:t=fill",
    ]

    has_music  = music_path and os.path.exists(music_path)
    use_cap_strip = cap_vid and os.path.exists(cap_vid)

    # ─── Con caption strip webm (overlay con alfa) ───────────────────────────
    if use_cap_strip:
        vf_chain   = vf_grade + "," + ",".join(fixed_filters) + ",format=yuv420p"
        cap_idx    = 3 if has_music else 2

        if has_music:
            fc = (
                f"[0:v]{vf_chain}[bg];"
                f"[bg][{cap_idx}:v]overlay=0:H-h-40:shortest=1[vout];"
                f"[2:a]volume=0.07[mus];"
                f"[1:a][mus]amix=inputs=2:duration=first:weights=1 0.5[aout]"
            )
            cmd = [FFMPEG, "-y",
                   "-i", presenter_vid, "-i", audio_path,
                   "-i", music_path, "-i", cap_vid,
                   "-t", str(duration), "-filter_complex", fc,
                   "-map", "[vout]", "-map", "[aout]"]
        else:
            fc = (
                f"[0:v]{vf_chain}[bg];"
                f"[bg][{cap_idx}:v]overlay=0:H-h-40:shortest=1[vout]"
            )
            cmd = [FFMPEG, "-y",
                   "-i", presenter_vid, "-i", audio_path, "-i", cap_vid,
                   "-t", str(duration), "-filter_complex", fc,
                   "-map", "[vout]", "-map", "1:a"]

    # ─── Fallback: drawtext por palabra ──────────────────────────────────────
    else:
        word_filters = []
        for wd in words:
            w = sf(wd["word"])
            if not w: continue
            word_filters.append(
                f"drawtext=fontfile='{FONT_BOLD}':text='{w}'"
                f":fontcolor=white:fontsize=112"
                f":x=(w-text_w)/2:y=h-310"
                f":shadowcolor=black@0.99:shadowx=6:shadowy=6"
                f":bordercolor=black:borderw=5"
                f":enable='between(t,{wd['start']:.2f},{wd['end']:.2f})'"
            )
        all_filters = fixed_filters + word_filters
        vf = vf_grade + "," + ",".join(all_filters) + ",format=yuv420p"

        if has_music:
            fc = (
                f"[0:v]{vf}[vout];"
                f"[2:a]volume=0.07[mus];"
                f"[1:a][mus]amix=inputs=2:duration=first:weights=1 0.5[aout]"
            )
            cmd = [FFMPEG, "-y",
                   "-i", presenter_vid, "-i", audio_path, "-i", music_path,
                   "-t", str(duration), "-filter_complex", fc,
                   "-map", "[vout]", "-map", "[aout]"]
        else:
            cmd = [FFMPEG, "-y",
                   "-i", presenter_vid, "-i", audio_path,
                   "-t", str(duration), "-vf", vf,
                   "-map", "0:v", "-map", "1:a"]

    cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "17",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart", output_path]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg: {r.stderr[-400:]}")
    print("      Video ensamblado ✓")


# ── Miniatura ──────────────────────────────────────────────────────────────────
def create_thumbnail(title, output_path):
    if _thumb_imagen4(title, output_path): return True
    _thumb_pillow(title, output_path); return False

def _thumb_imagen4(title, output_path):
    try:
        from google.genai import types as gt
        import io as _io
        c     = genai.Client(api_key=GEMINI_API_KEY)
        clean = re.sub(r'[\U0001F000-\U0001FFFF]', '', title).strip()
        r = c.models.generate_images(
            model="imagen-4.0-fast-generate-001",
            prompt="Professional YouTube thumbnail, dramatic dark background, AI technology neon blue glow, person shocked, high contrast, no text, 16:9, photorealistic",
            config=gt.GenerateImagesConfig(number_of_images=1, aspect_ratio="16:9",
                                           safety_filter_level="BLOCK_LOW_AND_ABOVE")
        )
        img = Image.open(_io.BytesIO(r.generated_images[0].image.image_bytes)).resize((1280, 720))
        _thumb_overlay(img, clean, output_path)
        print("      Miniatura: Imagen 4 ✓"); return True
    except Exception as e:
        if "429" not in str(e): print(f"      Imagen 4: {str(e)[:60]}")
        return False

def _thumb_pillow(title, output_path):
    import math
    img  = Image.new("RGB", (1280, 720), (8, 12, 28))
    draw = ImageDraw.Draw(img)
    for x in range(1280):
        t = x / 1280
        c = tuple(int(a + (b-a)*t) for a, b in zip((8,12,28), (18,28,60)))
        draw.line([(x,0),(x,720)], fill=c)
    random.seed(hash(title) % 9999)
    nodes = [(random.randint(0,1280), random.randint(0,720)) for _ in range(60)]
    for i, (x1,y1) in enumerate(nodes):
        for x2, y2 in nodes[i+1:i+5]:
            if math.hypot(x2-x1, y2-y1) < 220:
                draw.line([(x1,y1),(x2,y2)], fill=(0,35,70), width=1)
    for x, y in nodes:
        draw.ellipse([x-4,y-4,x+4,y+4], fill=(0,120,160))
    clean = re.sub(r'[\U0001F000-\U0001FFFF]', '', title).strip()
    _thumb_overlay(img, clean, output_path)

def _thumb_overlay(img, title, output_path):
    draw   = ImageDraw.Draw(img)
    W2, H2 = img.size
    try:
        fb = ImageFont.truetype(FONT_BOLD, 66)
        fl = ImageFont.truetype(FONT_BOLD, 32)
        fs = ImageFont.truetype(FONT_REG,  26)
    except: fb = fl = fs = ImageFont.load_default()
    draw.rectangle([0,0,7,H2], fill=(0,220,255))
    draw.text((26,22), "IA", font=fl, fill=(255,255,255))
    draw.text((70,22), "al Dia", font=fl, fill=(0,220,255))
    draw.rectangle([26,70,260,73], fill=(0,220,255))
    words = title.split(); lines, ln = [], []
    for w in words:
        ln.append(w)
        if len(" ".join(ln)) > 20: lines.append(" ".join(ln[:-1])); ln = [w]
    if ln: lines.append(" ".join(ln))
    y = H2//2 - len(lines[:3]) * 38
    for ln in lines[:3]:
        draw.text((W2//2+3, y+3), ln, font=fb, fill=(0,0,0), anchor="mm")
        draw.text((W2//2, y),     ln, font=fb, fill=(255,255,255), anchor="mm")
        y += 76
    draw.rectangle([26, H2-60, W2-26, H2-57], fill=(0,220,255))
    draw.text((W2//2, H2-34), "Inteligencia Artificial · Todos los dias",
              font=fs, fill=(160,175,210), anchor="mm")
    img.save(output_path)


# ── Auth + Upload YouTube ──────────────────────────────────────────────────────
def get_youtube():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow  = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)

def upload_video(yt, video_path, title, description, tags):
    body = {
        "snippet": {"title": title, "description": description,
                    "tags": tags + ["shorts","inteligenciaartificial","ia","iaaldia"],
                    "categoryId": "28", "defaultLanguage": "es"},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    media   = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status: print(f"  Subiendo... {int(status.progress()*100)}%", end="\r")
    print(); return response["id"]

def upload_thumb(yt, video_id, thumb_path):
    try:
        yt.thumbnails().set(videoId=video_id,
            media_body=MediaFileUpload(thumb_path, mimetype="image/png")).execute()
        print("      Miniatura subida ✓")
    except Exception as e:
        print(f"      Miniatura omitida: {str(e)[:50]}")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print(f"  IA al Día v11.0 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Nicho: {_NICHE['nombre']} | Persona: {_PERSONA_KEY} | Template: {_TEMPLATE_KEY}")
    print(f"{'='*60}\n")

    used_tts = used_imagen = used_pro = False

    with tempfile.TemporaryDirectory() as tmp:
        audio_path  = os.path.join(tmp, "audio.mp3")
        music_path  = os.path.join(tmp, "ambient.aac")
        raw_vid     = os.path.join(tmp, "short_raw.mp4")
        output_path = os.path.join(tmp, "short.mp4")
        intro_path  = os.path.join(tmp, "intro.mp4")
        thumb_path  = os.path.join(tmp, "thumbnail.png")

        print("[1/7] RSS + research...")
        headlines = get_headlines()
        topic     = headlines[0] if headlines else "inteligencia artificial 2026"
        research  = research_topic(topic)
        print(f"      {len(headlines)} titulares | research: {bool(research)}")

        print("[2/7] Script (Gemini 2.5 Pro)...")
        script, used_pro = generate_script(headlines, research)
        print(f"      Título: {script['titulo']}")

        print(f"[3/7] Voz (persona: {_PERSONA_KEY})...")
        used_tts = generate_audio(script["guion"], audio_path, _PERSONA_KEY)
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 100:
            raise RuntimeError("Audio no generado — todos los TTS fallaron.")
        duration  = MP3(audio_path).info.length + 0.5
        print(f"      Duración: {duration:.1f}s | palabras: {len(script['guion'].split())}")

        print("[4/7] Presentador (Pexels · xfade)...")
        presenter = get_multi_presenter_video(tmp, duration)
        if not presenter:
            raise RuntimeError("No se pudo obtener video de Pexels.")

        print("[5/7] Captions + música...")
        words   = transcribe_whisper(audio_path) or estimate_words(script["guion"], duration)
        cap_vid = render_caption_strip(words, tmp)
        has_music = make_ambient(duration, music_path)

        print("[6/7] Ensamblando (PaddleGAN grade + vignette)...")
        assemble(presenter, audio_path,
                 music_path if has_music else "",
                 words, script.get("hook_texto", ""),
                 cap_vid, raw_vid, duration)

        # [Manim + MoviePy] Intro animado + concatenación
        has_intro = make_manim_intro(intro_path)
        if has_intro and os.path.exists(intro_path):
            print("      Prepending Manim intro...")
            if not prepend_intro(intro_path, raw_vid, output_path):
                shutil.copy(raw_vid, output_path)
        else:
            shutil.copy(raw_vid, output_path)

        print("[6/7] Miniatura...")
        used_imagen = create_thumbnail(script["titulo"], thumb_path)

        desc_final = (
            script["descripcion"] + AFFILIATES +
            "\n\n━━━━━━━━━━━━━━━━\n"
            "🤖 IA al Día — Inteligencia Artificial para LATAM, todos los días.\n"
            "⚠️ Contenido creado con asistencia de IA con fines educativos."
        )

        print("[7/7] Subiendo a YouTube...")
        yt       = get_youtube()
        video_id = upload_video(yt, output_path, script["titulo"], desc_final, script["tags"])
        upload_thumb(yt, video_id, thumb_path)

        credits   = update_credits(used_tts, used_imagen, used_pro)
        remaining = CREDIT_TOTAL - credits["spent"]

        # ── Registrar video en memoria del learning loop ──────────────────────
        try:
            hook_usado = script.get("hook_texto", "")
            register_video(video_id, script["titulo"], _NICHE_KEY, hook_usado,
                           hora_publicacion=datetime.now().hour)
        except Exception as e:
            print(f"      Learning loop registro: {str(e)[:50]}")

        # ── Distribución multi-plataforma [ShortGPT + yt-short-clipper] ───
        print("[+] Distribución multi-plataforma...")
        try:
            from platforms import publish_tiktok, publish_instagram, get_seo_keywords
            _seo_kws = get_seo_keywords(script["titulo"], LANG_CODE)
            if _seo_kws:
                extra = [k for k in _seo_kws if k not in script["tags"]]
                script["tags"].extend(extra[:4])

            _desc_short = script["descripcion"][:300] + " #Shorts #IA #IaAlDia"
            publish_tiktok(output_path, script["titulo"], _desc_short)
            publish_instagram(output_path, _desc_short)
        except ImportError:
            print("      platforms.py no encontrado, omitiendo TikTok/Instagram")
        except Exception as e:
            print(f"      Multi-plataforma: {str(e)[:60]}")

    print(f"\n  ✓ https://youtube.com/shorts/{video_id}")
    print(f"  ✓ {script['titulo']}")
    print(f"  ✓ ${remaining:.2f} de crédito restante\n")


if __name__ == "__main__":
    main()
