#!/usr/bin/env python3
"""
YouTube Shorts Automator — IA al Día v3.0
Pipeline premium: research → script (Pro) → TTS (Gemini) → Ken Burns →
                  Whisper captions → música → Imagen 4 → YouTube
"""

import os, json, random, requests, subprocess, tempfile, time, math
import feedparser, shutil, concurrent.futures, urllib.parse, urllib.request, re, base64
from pathlib import Path
from datetime import datetime, date
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import edge_tts, asyncio, imageio_ffmpeg
from mutagen.mp3 import MP3

FFMPEG = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent
ENV_FILE       = BASE_DIR / ".env"
CLIENT_SECRETS = BASE_DIR / "client_secrets.json"
TOKEN_FILE     = BASE_DIR / "token.json"
CREDITS_FILE   = BASE_DIR / "credits.json"
SCOPES         = ["https://www.googleapis.com/auth/youtube"]
TTS_VOICE_EDGE = "es-CL-LorenzoNeural"
GEMINI_MODELS  = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]

_MAC_FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
_LIN_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT      = _MAC_FONT if os.path.exists(_MAC_FONT) else _LIN_FONT

BG_DARK  = (8, 12, 28)
BG_MID   = (14, 22, 54)
CYAN     = (0, 220, 255)
CYAN_DIM = (0, 140, 180)
WHITE    = (255, 255, 255)
GRAY     = (160, 175, 210)

# Costo estimado por video con billing activo
COST_PER_VIDEO = {
    "gemini_tts":       0.006,
    "imagen4_thumb":    0.04,
    "gemini_pro_script":0.005,
}
CREDIT_TOTAL   = 300.0
ALERT_THRESHOLD = 30.0   # Avisar cuando quedan menos de $30


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

RSS_FEEDS = [
    "https://venturebeat.com/category/ai/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
]

FALLBACK_TOPICS = [
    "cómo la IA está eliminando empleos en sectores que nadie esperaba",
    "el modelo de IA que superó a los médicos en diagnósticos",
    "por qué las empresas están despidiendo programadores por culpa de la IA",
    "la herramienta de IA que los creadores de contenido no quieren que conozcas",
    "cómo China está ganando la carrera de la inteligencia artificial en 2026",
    "el lado oscuro de los chatbots que nadie te cuenta",
    "por qué el 40% de los empleos actuales desaparecerán en 5 años según la ONU",
    "la IA que puede leer tus emociones y lo que eso implica",
]

AFFILIATES = (
    "\n\n💡 Herramientas IA que recomiendo:\n"
    "→ ChatGPT: https://chat.openai.com\n"
    "→ Claude AI: https://claude.ai\n"
    "→ Gemini: https://gemini.google.com\n"
    "→ Perplexity: https://perplexity.ai"
)


# ── Créditos — control de gasto ───────────────────────────────────────────────
def load_credits() -> dict:
    if CREDITS_FILE.exists():
        try:
            return json.loads(CREDITS_FILE.read_text())
        except Exception:
            pass
    return {"spent": 0.0, "runs": 0, "last_run": "", "billing_active": False}

def save_credits(data: dict):
    CREDITS_FILE.write_text(json.dumps(data, indent=2))

def update_credits(used_tts: bool, used_imagen: bool, used_pro: bool) -> dict:
    data = load_credits()
    cost = 0.0
    if used_tts:    cost += COST_PER_VIDEO["gemini_tts"]
    if used_imagen: cost += COST_PER_VIDEO["imagen4_thumb"]
    if used_pro:    cost += COST_PER_VIDEO["gemini_pro_script"]
    data["spent"]        += cost
    data["runs"]         += 1
    data["last_run"]      = str(date.today())
    data["billing_active"] = (used_tts or used_imagen or used_pro)
    save_credits(data)
    remaining = CREDIT_TOTAL - data["spent"]
    print(f"      Crédito usado hoy: ${cost:.3f} | Total: ${data['spent']:.2f} | Restante: ${remaining:.2f}")
    if remaining < ALERT_THRESHOLD:
        print(f"\n  ⚠️  ALERTA: Quedan solo ${remaining:.2f} de crédito Google.")
        print(f"  ⚠️  Agrega más crédito en console.cloud.google.com para evitar cobros.\n")
    return data


# ── Paso 1: Trending topic ────────────────────────────────────────────────────
def get_trending_topic() -> str:
    headlines = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                title = entry.get("title", "").strip()
                if title and len(title) > 10:
                    headlines.append(title)
        except Exception:
            continue
    if not headlines:
        return random.choice(FALLBACK_TOPICS)

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""Eres experto en contenido viral de IA para YouTube en español latinoamericano.

Noticias recientes de IA:
{chr(10).join(f'- {h}' for h in headlines[:12])}

Selecciona la noticia más impactante para LATAM. Reformúlala como tema de YouTube Short.
Responde SOLO con el tema (1 oración, 10-15 palabras, sin comillas)."""

    for model in GEMINI_MODELS[:2]:
        try:
            r = client.models.generate_content(model=model, contents=prompt)
            topic = r.text.strip().strip('"').strip("'")
            print(f"      Tema: {topic}")
            return topic
        except Exception:
            time.sleep(5)
    return random.choice(FALLBACK_TOPICS)


# ── Paso 1b: Research gate anti-alucinación ──────────────────────────────────
def research_topic(topic: str) -> str:
    try:
        data = urllib.parse.urlencode({"q": topic + " 2026", "b": ""}).encode()
        req  = urllib.request.Request(
            "https://html.duckduckgo.com/html/", data=data,
            headers={"User-Agent": "Mozilla/5.0 (compatible; researchbot/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)<', html)
        if snippets:
            return "\n".join(s.strip()[:250] for s in snippets[:6])
    except Exception:
        pass
    return ""


# ── Paso 2: Script con Gemini 2.5 Pro — estructura de historia ────────────────
def generate_script(topic: str, research: str = "") -> dict:
    client  = genai.Client(api_key=GEMINI_API_KEY)

    research_block = ""
    if research:
        research_block = f"\nHECHOS VERIFICADOS (úsalos, no inventes cifras):\n{research}\n"

    prompt = f"""Eres el creador de contenido de IA más exitoso de habla hispana en YouTube, con 8 millones de suscriptores.

TEMA: {topic}
{research_block}
Crea un guión para YouTube Short de 58-62 segundos (155-170 palabras).

ESTRUCTURA OBLIGATORIA:
[GANCHO 0-4s] Una frase de 6-8 palabras que interrumpa el scroll. Usa UNA de estas fórmulas:
  • "Nadie te dijo que [verdad incómoda]"
  • "[número] de personas ya [hacen algo] y tú no"
  • "Esto va a desaparecer antes de [fecha cercana]"
  • "La IA acaba de hacer algo que [consecuencia inesperada]"

[TENSIÓN 4-18s] El problema o cambio real. Un dato numérico concreto. Hazlo urgente.

[EVIDENCIA 18-35s] Caso real, empresa, estudio o persona específica. No generalices.

[GIRO 35-48s] El ángulo que nadie menciona. Tu opinión directa, sin rodeos.

[IMPLICACIÓN 48-57s] Qué significa esto para quien ve el video ahora mismo.

[CIERRE 57-62s] Pregunta que queda en la cabeza + "Sígueme para más IA al Día."

REGLAS:
- Máximo 9 palabras por oración
- Voz humana: "yo lo vi", "nadie habla de esto", "me preocupa que"
- Al menos 2 datos numéricos (%, millones, días, etc.)
- Sin palabras vacías: "increíble", "revolucionario", "impresionante"
- Español latinoamericano neutro, fluido, no robótico

RESPONDE JSON exacto sin markdown:
{{
  "titulo": "Título SEO: keyword al inicio, máximo 52 chars, un emoji al final",
  "descripcion": "2 oraciones con keyword. Contexto de valor. #Shorts #IA #InteligenciaArtificial #ChatGPT #Tecnologia #IaAlDia",
  "tags": ["ia 2026", "inteligencia artificial noticias", "chatgpt novedades", "ia herramientas", "ia al dia", "shorts ia", "tecnologia latina", "ia trabajo", "futuro ia", "automatizacion", "ia español", "ia impacto"],
  "guion": "guión completo listo para leer, sin símbolos ni acotaciones",
  "hook_texto": "exactamente las primeras 6-8 palabras del guión",
  "visual_prompts": [
    "prompt en inglés para imagen de la sección GANCHO (dramático, impactante)",
    "prompt para sección TENSIÓN (urgente, oscuro)",
    "prompt para sección EVIDENCIA (datos, gráficos, infográfico)",
    "prompt para sección GIRO (ángulo diferente, sorpresa visual)",
    "prompt para sección IMPLICACIÓN (consecuencias, futuro cercano)",
    "prompt para sección CIERRE (llamada a la acción, energía positiva)"
  ],
  "keyword_video": "keyword en inglés para búsqueda de imágenes de respaldo"
}}"""

    used_pro = False
    response = None
    for model in GEMINI_MODELS:
        for attempt in range(3):
            try:
                response = client.models.generate_content(model=model, contents=prompt)
                if model == "gemini-2.5-pro":
                    used_pro = True
                break
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    break
                if attempt < 2:
                    time.sleep(15 * (attempt + 1))
        if response:
            break

    if not response:
        return _fallback_script(topic), False

    text = response.text.strip()
    if "```" in text:
        for part in text.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"):
                text = part
                break
    try:
        return json.loads(text), used_pro
    except Exception:
        return _fallback_script(topic), False

def _fallback_script(topic: str) -> dict:
    return {
        "titulo": f"IA 2026: {topic[:38]} 🤖",
        "descripcion": f"{topic}. Todo sobre inteligencia artificial en 2026. #Shorts #IA #InteligenciaArtificial #ChatGPT #Tecnologia #IaAlDia",
        "tags": ["ia 2026", "inteligencia artificial noticias", "chatgpt novedades", "ia herramientas", "ia al dia", "shorts ia", "tecnologia latina", "ia trabajo", "futuro ia", "automatizacion", "ia español", "ia impacto"],
        "guion": f"Nadie te dijo esto sobre la inteligencia artificial. {topic}. El 40% de los empleos actuales van a cambiar en los próximos 3 años según la ONU. Yo lo veo cada semana en cómo las empresas reemplazan tareas. Lo que nadie menciona es que no es tarde para adaptarse. Pero sí es tarde para ignorarlo. La pregunta no es si te va a afectar. La pregunta es qué vas a hacer antes de que llegue. Sígueme para más IA al Día.",
        "hook_texto": "Nadie te dijo esto sobre la IA",
        "visual_prompts": [
            "dramatic AI robot face close-up, red lighting, cinematic, dark",
            "data visualization, falling numbers, dark background, tension",
            "corporate office workers replaced by robots, blue neon",
            "person looking at screen shocked, neon reflections, dramatic",
            "future city AI controlled, sunset, orange blue contrast",
            "subscribe button glowing, cyan neon, dark background"
        ],
        "keyword_video": "artificial intelligence future"
    }


# ── Paso 3: Voz — Gemini TTS (natural) con fallback Edge-TTS ─────────────────
def _add_pauses(text: str) -> str:
    text = text.replace(". ", "... ")
    text = text.replace(", ", ",  ")
    text = text.replace(" Y ", "  Y ")
    text = text.replace(" Pero ", "  Pero ")
    text = text.replace(" Ahora ", "  Ahora ")
    return text

def _generate_audio_gemini(text: str, path: str) -> bool:
    try:
        from google.genai import types as gtypes
        gemini = genai.Client(api_key=GEMINI_API_KEY)
        response = gemini.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text,
            config=gtypes.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=gtypes.SpeechConfig(
                    voice_config=gtypes.VoiceConfig(
                        prebuilt_voice_config=gtypes.PrebuiltVoiceConfig(
                            voice_name="Charon"
                        )
                    )
                )
            )
        )
        part = response.candidates[0].content.parts[0]
        if not (hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data):
            return False
        raw_bytes = base64.b64decode(part.inline_data.data)
        if len(raw_bytes) < 1000:
            return False
        raw_path = path.replace(".mp3", "_raw.pcm")
        with open(raw_path, "wb") as f:
            f.write(raw_bytes)
        cmd = [FFMPEG, "-y", "-f", "s16le", "-ar", "24000", "-ac", "1",
               "-i", raw_path, "-c:a", "libmp3lame", "-b:a", "128k", path]
        r = subprocess.run(cmd, capture_output=True)
        os.remove(raw_path)
        if r.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 1000:
            print("      Voz: Gemini TTS ✓")
            return True
    except Exception as e:
        if "429" not in str(e) and "quota" not in str(e).lower():
            print(f"      Gemini TTS error: {str(e)[:60]}")
    return False

async def _tts_edge_async(text: str, path: str):
    communicate = edge_tts.Communicate(
        _add_pauses(text), TTS_VOICE_EDGE,
        rate="-5%", pitch="-2Hz", volume="+10%"
    )
    await communicate.save(path)

def generate_audio(text: str, path: str) -> bool:
    if _generate_audio_gemini(text, path):
        return True
    print("      Voz: Edge-TTS fallback (Lorenzo)")
    asyncio.run(_tts_edge_async(text, path))
    return False


# ── Paso 3b: Whisper — captions con timestamps exactos ───────────────────────
def transcribe_whisper(audio_path: str) -> list:
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("tiny", device="cpu", compute_type="int8",
                             download_root="/tmp/whisper_models")
        segments, _ = model.transcribe(audio_path, language="es", word_timestamps=True)
        words = []
        for seg in segments:
            for w in (seg.words or []):
                word = w.word.strip()
                if word:
                    words.append({"word": word, "start": w.start, "end": w.end})
        if not words:
            return None
        phrases = []
        for i in range(0, len(words), 4):
            chunk = words[i:i+4]
            phrases.append((" ".join(w["word"] for w in chunk), chunk[0]["start"], chunk[-1]["end"]))
        print(f"      Whisper: {len(phrases)} frases ✓")
        return phrases
    except Exception as e:
        print(f"      Whisper no disponible: {str(e)[:50]}")
        return None

def estimate_captions(script: str, duration: float) -> list:
    words         = script.split()
    time_per_word = (duration - 1.0) / max(len(words), 1)
    phrases, i    = [], 0
    while i < len(words):
        chunk = words[i:i+4]
        start = 0.5 + i * time_per_word
        end   = 0.5 + (i + len(chunk)) * time_per_word
        phrases.append((" ".join(chunk), start, end))
        i += 4
    return phrases


# ── Paso 3c: Música ambient + voice ducking ───────────────────────────────────
def generate_ambient_music(duration: float, output_path: str) -> bool:
    try:
        expr = (
            "aevalsrc="
            "0.06*sin(2*PI*130.8*t)*abs(sin(2*PI*0.2*t+0.5))+"
            "0.05*sin(2*PI*164.8*t)*abs(sin(2*PI*0.2*t+1.0))+"
            "0.04*sin(2*PI*196.0*t)*abs(sin(2*PI*0.2*t+1.5))+"
            "0.03*sin(2*PI*261.6*t)*abs(sin(2*PI*0.2*t+2.0))"
            ":s=44100"
        )
        cmd = [FFMPEG, "-y", "-f", "lavfi", "-i", expr,
               "-t", str(duration + 1),
               "-af", f"afade=t=in:d=2,afade=t=out:st={duration-2}:d=2",
               "-c:a", "aac", "-b:a", "64k", output_path]
        return subprocess.run(cmd, capture_output=True).returncode == 0
    except Exception:
        return False

def build_duck_filter(phrases: list, duration: float,
                      vol_speech: float = 0.07, vol_gap: float = 0.20) -> str:
    if not phrases:
        return f"volume={vol_speech}"
    regions = [(max(0, s - 0.2), min(duration, e + 0.2)) for _, s, e in phrases]
    expr = str(vol_gap)
    for start, end in regions:
        expr = f"if(between(t,{start:.2f},{end:.2f}),{vol_speech},{expr})"
    return f"volume='{expr}':eval=frame"


# ── Paso 4: Imágenes IA con Ken Burns ─────────────────────────────────────────
IMAGE_BASE_STYLE = ", vertical 9:16, no text, cinematic lighting, ultra detailed, 4K"

KEN_BURNS = [
    # (zoom_start, zoom_end, pan_x_expr, pan_y_expr)  — para zoompan de FFmpeg
    "zoompan=z='min(zoom+0.0012,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",   # zoom in center
    "zoompan=z='if(lte(on,1),1.25,max(1.0,zoom-0.0012))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",  # zoom out center
    "zoompan=z='1.15':x='0':y='ih/2-(ih/zoom/2)'",                                    # pan derecha fija
    "zoompan=z='1.15':x='iw-iw/zoom':y='ih/2-(ih/zoom/2)'",                           # pan izquierda fija
    "zoompan=z='min(zoom+0.001,1.2)':x='0':y='0'",                                    # zoom in esquina
    "zoompan=z='1.1':x='iw/2-(iw/zoom/2)':y='ih-ih/zoom'",                            # pan arriba
]

def _fetch_image(args):
    idx, prompt, out_path, seed = args
    try:
        encoded = urllib.parse.quote(prompt)
        url = (f"https://image.pollinations.ai/prompt/{encoded}"
               f"?width=1080&height=1920&nologo=true&seed={seed}&model=flux")
        r = requests.get(url, timeout=45)
        if r.status_code == 200 and len(r.content) > 5000:
            with open(out_path, "wb") as f:
                f.write(r.content)
            return out_path
    except Exception:
        pass
    return None

def _image_to_kenburns_clip(img_path: str, clip_path: str, duration: float, direction_idx: int) -> bool:
    """Convierte una imagen en un clip con efecto Ken Burns."""
    fps  = 25
    frames = int(duration * fps)
    kb   = KEN_BURNS[direction_idx % len(KEN_BURNS)]
    vf   = (
        f"scale=1300:-1,"
        f"{kb}:d={frames}:fps={fps}:s=1080x1920,"
        f"format=yuv420p,"
        f"fade=t=in:st=0:d=0.4,"
        f"fade=t=out:st={duration-0.4:.2f}:d=0.4"
    )
    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-i", img_path,
        "-vf", vf,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-r", str(fps),
        clip_path
    ]
    return subprocess.run(cmd, capture_output=True).returncode == 0

def _pexels_fallback(keyword: str, output_path: str) -> bool:
    headers = {"Authorization": PEXELS_API_KEY}
    for query in [keyword, "technology future", "artificial intelligence"]:
        params = {"query": query, "orientation": "portrait", "size": "medium", "per_page": 15}
        r = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params)
        videos = r.json().get("videos", [])
        if videos:
            video = random.choice(videos[:8])
            files = sorted(video["video_files"], key=lambda x: x.get("width", 0))
            dl    = requests.get(files[-1]["link"], stream=True)
            with open(output_path, "wb") as f:
                for chunk in dl.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
    return False

def generate_background(guion: str, keyword: str, visual_prompts: list,
                        duration: float, tmp_dir: str) -> str:
    img_dir  = os.path.join(tmp_dir, "slides")
    clip_dir = os.path.join(tmp_dir, "clips")
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(clip_dir, exist_ok=True)

    # Usar visual_prompts del script si están disponibles (más temáticos)
    n_slides = max(10, int(duration / 4))
    if visual_prompts and len(visual_prompts) >= 4:
        # Ciclar los prompts temáticos
        prompts = [visual_prompts[i % len(visual_prompts)] + IMAGE_BASE_STYLE
                   for i in range(n_slides)]
    else:
        words      = guion.split()
        chunk_size = max(1, len(words) // n_slides)
        chunks     = [words[i:i+chunk_size] for i in range(0, len(words), chunk_size)][:n_slides]
        styles     = [
            "dramatic dark atmosphere, neon red orange, cinematic close-up",
            "data visualization dark, cyan blue infographic, corporate",
            "futuristic tech, glowing particles, dark navy, professional",
            "AI network visualization, deep purple blue, abstract nodes",
        ]
        prompts = [f"{keyword}, {' '.join(c)[:60]}, {styles[i%len(styles)]}{IMAGE_BASE_STYLE}"
                   for i, c in enumerate(chunks)]

    tasks = [(i, p, os.path.join(img_dir, f"slide_{i:03d}.jpg"), random.randint(1, 99999))
             for i, p in enumerate(prompts)]

    print(f"      Generando {len(tasks)} imágenes IA...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(_fetch_image, tasks))

    image_paths = [p for p in results if p and os.path.exists(p)]

    if len(image_paths) >= 6:
        print(f"      {len(image_paths)}/{len(tasks)} imágenes ✓ — aplicando Ken Burns...")
        secs_per  = duration / len(image_paths)
        clip_paths = []
        for i, img_path in enumerate(image_paths):
            clip_path = os.path.join(clip_dir, f"clip_{i:03d}.mp4")
            if _image_to_kenburns_clip(img_path, clip_path, secs_per, i):
                clip_paths.append(clip_path)

        if clip_paths:
            concat_file = os.path.join(tmp_dir, "clips.txt")
            with open(concat_file, "w") as f:
                for c in clip_paths:
                    f.write(f"file '{c}'\n")
                f.write(f"file '{clip_paths[-1]}'\n")  # último frame extra
            slideshow = os.path.join(tmp_dir, "slideshow.mp4")
            cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
                   "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                   "-vf", "format=yuv420p", slideshow]
            if subprocess.run(cmd, capture_output=True).returncode == 0:
                print("      Ken Burns slideshow ✓")
                return slideshow

    print("      Fallback: Pexels video...")
    pexels_path = os.path.join(tmp_dir, "background.mp4")
    _pexels_fallback(keyword, pexels_path)
    return pexels_path


# ── Paso 5: Captions — estilo limpio blanco con sombra ───────────────────────
def build_caption_filter(phrases: list, hook_text: str = "") -> str:
    def safe(t):
        return (t.replace("'", "").replace('"', "").replace("\\", "")
                 .replace("%", "").replace(":", "").replace("\n", " "))[:38]

    filters = []

    # Hook visual — blanco grande con borde cyan, solo primeros 3.5s
    if hook_text:
        s = safe(hook_text)
        filters.append(
            f"drawtext=fontfile='{FONT}':text='{s}'"
            f":fontcolor=white:fontsize=86"
            f":x=(w-text_w)/2:y=(h/2)-60"
            f":shadowcolor=black:shadowx=3:shadowy=3"
            f":bordercolor=0x00DCFF:borderw=4"
            f":enable='between(t,0.0,3.5)'"
        )

    # Captions — blanco limpio con sombra negra (sin caja)
    for text, start, end in phrases:
        s = safe(text)
        filters.append(
            f"drawtext=fontfile='{FONT}':text='{s}'"
            f":fontcolor=white:fontsize=72"
            f":x=(w-text_w)/2:y=h-280"
            f":shadowcolor=black@0.9:shadowx=4:shadowy=4"
            f":bordercolor=black:borderw=2"
            f":enable='between(t,{start:.2f},{end:.2f})'"
        )
    return ",".join(filters)


# ── Paso 6: Ensamblar video ───────────────────────────────────────────────────
def create_short(audio_path: str, bg_path: str, output_path: str,
                 phrases: list, hook_text: str = "", music_path: str = ""):
    duration = MP3(audio_path).info.length + 0.5

    is_slideshow = "slideshow" in bg_path or "clips" in bg_path
    base_vf = (
        "eq=contrast=1.10:brightness=-0.01:saturation=1.30:gamma=0.96"
        if is_slideshow else
        "scale=1188:2112:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "eq=contrast=1.10:brightness=-0.01:saturation=1.30:gamma=0.96"
    )

    cap_filter = build_caption_filter(phrases, hook_text)
    vf = base_vf + ("," + cap_filter if cap_filter else "")

    if music_path and os.path.exists(music_path):
        duck = build_duck_filter(phrases, duration)
        cmd = [FFMPEG, "-y",
               "-i", bg_path, "-i", audio_path, "-i", music_path,
               "-t", str(duration),
               "-filter_complex",
               f"[2:a]{duck}[music];[1:a][music]amix=inputs=2:duration=first:weights=1 0.5[aout]",
               "-map", "0:v", "-map", "[aout]",
               "-vf", vf,
               "-c:v", "libx264", "-preset", "fast", "-crf", "20",
               "-c:a", "aac", "-b:a", "192k",
               "-shortest", "-movflags", "+faststart", output_path]
    else:
        cmd = [FFMPEG, "-y",
               "-i", bg_path, "-i", audio_path,
               "-t", str(duration), "-vf", vf,
               "-c:v", "libx264", "-preset", "fast", "-crf", "20",
               "-c:a", "aac", "-b:a", "192k",
               "-shortest", "-movflags", "+faststart", output_path]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg: {r.stderr[-400:]}")


# ── Miniatura — Imagen 4 Fast + branding Pillow ───────────────────────────────
def create_thumbnail(title: str, output_path: str) -> bool:
    if _create_thumbnail_imagen4(title, output_path):
        return True
    _create_thumbnail_pillow(title, output_path)
    return False

def _create_thumbnail_imagen4(title: str, output_path: str) -> bool:
    try:
        from google.genai import types as gtypes
        import io
        gemini = genai.Client(api_key=GEMINI_API_KEY)
        clean  = re.sub(r'[\U0001F000-\U0001FFFF]', '', title).strip()
        prompt = (
            "YouTube thumbnail background image, no text, dark cinematic scene, "
            "artificial intelligence and technology theme, dramatic neon cyan blue lighting, "
            "photorealistic, ultra sharp, 16:9 aspect ratio, high contrast, professional"
        )
        response = gemini.models.generate_images(
            model="imagen-4.0-fast-generate-001",
            prompt=prompt,
            config=gtypes.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",
                safety_filter_level="BLOCK_LOW_AND_ABOVE",
            )
        )
        img_bytes = response.generated_images[0].image.image_bytes
        base_img  = Image.open(io.BytesIO(img_bytes)).resize((1280, 720))
        _overlay_branding(base_img, clean, output_path)
        print("      Miniatura: Imagen 4 ✓")
        return True
    except Exception as e:
        if "429" not in str(e) and "quota" not in str(e).lower():
            print(f"      Imagen 4: {str(e)[:70]}")
        return False

def _create_thumbnail_pillow(title: str, output_path: str):
    W, H = 1280, 720
    img  = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    lerp = lambda c1, c2, t: tuple(int(c1[i]+(c2[i]-c1[i])*t) for i in range(3))
    for x in range(W):
        draw.line([(x,0),(x,H)], fill=lerp(BG_DARK, BG_MID, x/W))
    random.seed(hash(title) % 9999)
    nodes = [(random.randint(0,W), random.randint(0,H)) for _ in range(50)]
    for i,(x1,y1) in enumerate(nodes):
        for x2,y2 in nodes[i+1:i+4]:
            if math.sqrt((x2-x1)**2+(y2-y1)**2) < 200:
                draw.line([(x1,y1),(x2,y2)], fill=(0,40,70), width=1)
    for x,y in nodes:
        draw.ellipse([x-4,y-4,x+4,y+4], fill=CYAN_DIM)
    clean = re.sub(r'[\U0001F000-\U0001FFFF]', '', title).strip()
    _overlay_branding(img, clean, output_path)

def _overlay_branding(img: Image.Image, title: str, output_path: str):
    draw = ImageDraw.Draw(img)
    W, H = img.size
    try:
        f_logo  = ImageFont.truetype(FONT, 34)
        f_title = ImageFont.truetype(FONT, 66)
        f_sub   = ImageFont.truetype(FONT, 28)
    except Exception:
        f_logo = f_title = f_sub = ImageFont.load_default()

    # Barra lateral izquierda
    draw.rectangle([0, 0, 7, H], fill=CYAN)
    # Branding superior
    draw.text((26, 24), "IA", font=f_logo, fill=WHITE)
    draw.text((68, 24), "al Día", font=f_logo, fill=CYAN)
    draw.rectangle([26, 74, 280, 77], fill=CYAN)

    # Título centrado con sombra
    words = title.split()
    lines, line = [], []
    for w in words:
        line.append(w)
        if len(" ".join(line)) > 20:
            lines.append(" ".join(line[:-1]))
            line = [w]
    if line:
        lines.append(" ".join(line))
    lines   = lines[:3]
    y_start = H // 2 - len(lines) * 40
    for i, ln in enumerate(lines):
        # Sombra
        draw.text((W//2 + 3, y_start + i*80 + 3), ln, font=f_title,
                  fill=(0,0,0), anchor="mm")
        draw.text((W//2, y_start + i*80), ln, font=f_title,
                  fill=WHITE, anchor="mm")

    # Barra inferior
    draw.rectangle([26, H-66, W-26, H-63], fill=CYAN)
    draw.text((W//2, H-38), "Inteligencia Artificial • Todos los días",
              font=f_sub, fill=GRAY, anchor="mm")
    img.save(output_path)


def upload_thumbnail(youtube, video_id: str, thumb_path: str):
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumb_path, mimetype="image/png")
        ).execute()
        print("      Miniatura subida ✓")
    except Exception as e:
        print(f"      Miniatura omitida: {str(e)[:60]}")


# ── Auth YouTube ──────────────────────────────────────────────────────────────
def get_youtube_client():
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

def upload_to_youtube(youtube, video_path: str, title: str,
                      description: str, tags: list) -> str:
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags + ["shorts", "inteligenciaartificial", "tecnologia", "ia", "iaaldia"],
            "categoryId": "28",
            "defaultLanguage": "es",
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    media   = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Subiendo... {int(status.progress()*100)}%", end="\r")
    print()
    return response["id"]


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*55}")
    print(f"  IA al Día v3.0 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}\n")

    with tempfile.TemporaryDirectory() as tmp:
        audio_path  = os.path.join(tmp, "audio.mp3")
        music_path  = os.path.join(tmp, "ambient.aac")
        output_path = os.path.join(tmp, "short.mp4")
        thumb_path  = os.path.join(tmp, "thumbnail.png")

        used_tts = used_imagen = used_pro = False

        print("[1/7] Buscando tema trending...")
        topic = get_trending_topic()

        print("[2/7] Research gate (DuckDuckGo)...")
        research = research_topic(topic)
        if research:
            print(f"      {len(research.splitlines())} snippets verificados ✓")

        print("[3/7] Generando script (Gemini 2.5 Pro)...")
        result = generate_script(topic, research)
        if isinstance(result, tuple):
            script, used_pro = result
        else:
            script = result
        print(f"      Título: {script['titulo']}")
        visual_prompts = script.get("visual_prompts", [])

        print("[4/7] Generando voz...")
        used_tts = generate_audio(script["guion"], audio_path)
        duration = MP3(audio_path).info.length + 0.5
        print(f"      Duración: {duration:.1f}s")

        print("[5/7] Generando fondo con Ken Burns...")
        bg_path = generate_background(
            script["guion"], script["keyword_video"],
            visual_prompts, duration, tmp
        )

        print("[6/7] Whisper captions...")
        phrases = transcribe_whisper(audio_path) or estimate_captions(script["guion"], duration)

        print("[6/7] Música ambient...")
        has_music = generate_ambient_music(duration, music_path)

        print("[6/7] Ensamblando...")
        create_short(audio_path, bg_path, output_path, phrases,
                     script.get("hook_texto", ""),
                     music_path if has_music else "")

        print("[6/7] Miniatura...")
        used_imagen = create_thumbnail(script["titulo"], thumb_path)

        descripcion_final = (
            script["descripcion"]
            + AFFILIATES
            + "\n\n━━━━━━━━━━━━━━━━\n"
            "🤖 IA al Día — Noticias de IA para LATAM cada día.\n"
            "⚠️ Contenido creado con asistencia de IA con fines educativos."
        )

        print("[7/7] Subiendo a YouTube...")
        youtube  = get_youtube_client()
        video_id = upload_to_youtube(
            youtube, output_path,
            script["titulo"], descripcion_final, script["tags"]
        )
        upload_thumbnail(youtube, video_id, thumb_path)

        # Control de créditos
        credits = update_credits(used_tts, used_imagen, used_pro)
        remaining = CREDIT_TOTAL - credits["spent"]
        if remaining < ALERT_THRESHOLD:
            # Escribir en GitHub Step Summary si estamos en Actions
            summary = os.environ.get("GITHUB_STEP_SUMMARY", "")
            if summary:
                with open(summary, "a") as f:
                    f.write(f"\n⚠️ **ALERTA DE CRÉDITO**: Quedan ${remaining:.2f} de $300.00\n")
                    f.write("Recarga en console.cloud.google.com antes del próximo ciclo.\n")

    print(f"\n  ✓ Short: https://youtube.com/shorts/{video_id}")
    print(f"  ✓ Título: {script['titulo']}")
    print(f"  ✓ Crédito restante: ${CREDIT_TOTAL - credits['spent']:.2f}\n")


if __name__ == "__main__":
    main()
