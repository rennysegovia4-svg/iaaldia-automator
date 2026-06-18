#!/usr/bin/env python3
"""
YouTube Shorts Automator — IA al Día
Pipeline: trending topic → script → TTS → imágenes IA → slideshow → captions → YouTube
"""

import os, json, random, requests, subprocess, tempfile, time, math, feedparser
import shutil, concurrent.futures, urllib.parse
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import edge_tts, asyncio, imageio_ffmpeg
from mutagen.mp3 import MP3

import shutil as _shutil
FFMPEG = _shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent
ENV_FILE       = BASE_DIR / ".env"
CLIENT_SECRETS = BASE_DIR / "client_secrets.json"
TOKEN_FILE     = BASE_DIR / "token.json"
SCOPES         = ["https://www.googleapis.com/auth/youtube"]
TTS_VOICE      = "es-CL-LorenzoNeural"
FONT           = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
GEMINI_MODELS  = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

BG_DARK  = (8, 12, 28)
BG_MID   = (14, 22, 54)
CYAN     = (0, 220, 255)
CYAN_DIM = (0, 140, 180)
WHITE    = (255, 255, 255)
GRAY     = (160, 175, 210)

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

# ── Afiliados (ingresos desde el día 1) ──────────────────────────────────────
AFFILIATES = (
    "\n\n💡 Herramientas IA que recomiendo:\n"
    "→ ChatGPT: https://chat.openai.com\n"
    "→ Claude AI: https://claude.ai\n"
    "→ Gemini: https://gemini.google.com\n"
    "→ Perplexity: https://perplexity.ai"
)

FALLBACK_TOPICS = [
    "una herramienta de inteligencia artificial que está cambiando el trabajo",
    "cómo ChatGPT puede ayudarte a ganar más dinero",
    "el error más común al usar inteligencia artificial",
    "una función de IA que casi nadie conoce",
    "cómo la inteligencia artificial está reemplazando empleos en 2026",
    "la herramienta de IA gratuita más poderosa del momento",
    "cómo crear contenido con IA en minutos",
    "trucos de ChatGPT que te ahorran horas de trabajo",
    "las 3 IAs que debes conocer este año",
    "cómo ganar dinero con inteligencia artificial desde casa",
    "herramientas de IA que reemplazan al diseñador gráfico",
    "qué hace diferente a Claude de ChatGPT",
    "la IA que crea imágenes en segundos",
    "cómo automatizar tu negocio con inteligencia artificial",
    "el lado oscuro de la inteligencia artificial",
]

HOOK_FORMULAS = [
    "Empieza con una pregunta que genere curiosidad inmediata, por ejemplo: '¿Sabías que el 90% de la gente usa mal la IA?'",
    "Empieza con una afirmación sorpresiva: 'Esto va a reemplazar tu trabajo antes de que termine el año...'",
    "Empieza con un dato impactante: 'En solo 3 meses esta IA pasó de 0 a 100 millones de usuarios...'",
    "Empieza con urgencia: 'Para antes de cerrar este video. Lo que voy a mostrarte cambia todo...'",
    "Empieza con controversia: 'La mayoría de expertos en IA están equivocados en esto...'",
]

RSS_FEEDS = [
    "https://venturebeat.com/category/ai/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
]


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

Estas son las noticias de IA más recientes:
{chr(10).join(f'- {h}' for h in headlines[:12])}

Selecciona la más viral para LATAM y adáptala al español.
Responde SOLO con el tema (1 oración, sin comillas, máximo 15 palabras)."""

    for model in GEMINI_MODELS:
        try:
            r = client.models.generate_content(model=model, contents=prompt)
            topic = r.text.strip().strip('"').strip("'")
            print(f"      Tema trending: {topic}")
            return topic
        except Exception as e:
            if "429" in str(e):
                continue
            time.sleep(10)
    return random.choice(FALLBACK_TOPICS)


# ── Paso 2: Script viral ──────────────────────────────────────────────────────
def generate_script(topic: str) -> dict:
    client = genai.Client(api_key=GEMINI_API_KEY)
    hook   = random.choice(HOOK_FORMULAS)

    prompt = f"""Eres un creador de contenido viral en YouTube con 5 millones de suscriptores, especializado en IA para LATAM.

Crea un guión ULTRA enganchador para un YouTube Short (55 segundos, 130-150 palabras) sobre: {topic}

GANCHO: {hook}

REGLAS:
- Primeros 3 segundos: frase corta de 5-8 palabras que detenga el scroll
- Voz OPINADA: di "yo creo", "me parece increíble", "esto me preocupa"
- Oraciones CORTAS, máximo 12 palabras. Puntos frecuentes.
- Sin asteriscos, guiones, ni símbolos especiales
- Final con loop: última frase genera curiosidad para releer
- Última oración SIEMPRE: "Sígueme para más IA al Día"
- Español latinoamericano neutro

SEO TÍTULO 2026:
- Keyword principal en primeros 40 caracteres
- 4-6 palabras máximo
- Un emoji al final

JSON exacto (sin markdown):
{{
  "titulo": "título SEO keyword-first, máximo 55 chars, un emoji",
  "descripcion": "1-2 oraciones con keyword (aparece en preview). Contexto breve. #Shorts #IA #InteligenciaArtificial #ChatGPT #Tecnologia #IaAlDia",
  "tags": ["ia 2026", "inteligencia artificial", "chatgpt trucos", "ia herramientas gratis", "ia al dia", "shorts ia", "tecnologia latina", "ia noticias", "futuro ia", "automatizacion ia", "ia español", "ia para todos"],
  "guion": "guión completo para leer en voz alta, sin símbolos",
  "hook_texto": "primeras 5-7 palabras exactas del guión",
  "keyword_video": "keyword en inglés (robot, artificial intelligence, technology, future, data)"
}}"""

    response = None
    for model in GEMINI_MODELS:
        for attempt in range(3):
            try:
                response = client.models.generate_content(model=model, contents=prompt)
                break
            except Exception as e:
                if "429" in str(e):
                    break  # probar siguiente modelo
                if attempt < 2:
                    time.sleep(15 * (attempt + 1))
        if response:
            break
    if not response:
        # Fallback: template con el topic del día
        print("      Gemini sin cuota, usando template de emergencia...")
        return {
            "titulo": f"IA 2026: {topic[:35]} 🤖",
            "descripcion": f"{topic}. Todo sobre inteligencia artificial en 2026. #Shorts #IA #InteligenciaArtificial #ChatGPT #Tecnologia #IaAlDia",
            "tags": ["ia 2026", "inteligencia artificial", "chatgpt trucos", "ia herramientas gratis", "ia al dia", "shorts ia", "tecnologia latina", "ia noticias", "futuro ia", "automatizacion ia", "ia español", "ia para todos"],
            "guion": f"¿Sabías que {topic}? La inteligencia artificial está cambiando todo más rápido de lo que imaginas. Yo creo que esto es el mayor cambio tecnológico de nuestra generación. Millones de personas ya están usando IA para ganar dinero, ahorrar tiempo y ser más productivos. La pregunta no es si la IA va a afectar tu vida. La pregunta es si vas a estar preparado o no. Hoy tienes la oportunidad de adelantarte. Empieza a aprender IA ahora. Sígueme para más IA al Día.",
            "hook_texto": "La IA está cambiando todo ahora",
            "keyword_video": "artificial intelligence technology future"
        }

    text = response.text.strip()
    if "```" in text:
        for part in text.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"):
                text = part
                break
    return json.loads(text)


# ── Paso 3: Audio TTS ─────────────────────────────────────────────────────────
def _add_pauses(text: str) -> str:
    text = text.replace(". ", "... ")
    text = text.replace(", ", ",  ")
    text = text.replace(" Y ", "  Y ")
    text = text.replace(" Pero ", "  Pero ")
    text = text.replace(" Ahora ", "  Ahora ")
    return text

async def _tts_async(text: str, path: str):
    communicate = edge_tts.Communicate(
        _add_pauses(text), TTS_VOICE,
        rate="-8%", pitch="-3Hz", volume="+10%"
    )
    await communicate.save(path)

def generate_audio(text: str, path: str):
    asyncio.run(_tts_async(text, path))


# ── Paso 4: Imágenes IA con Pollinations.ai (gratis, sin API key) ─────────────
IMAGE_STYLES = [
    "professional dark infographic, neon blue cyan, flat design, no text, vertical",
    "futuristic tech visualization, dark background, glowing elements, minimal, vertical",
    "modern educational diagram, navy background, bright cyan accents, geometric, vertical",
    "digital art tech concept, dark purple blue gradient, clean composition, no words, vertical",
]

def _build_prompt(words: list, keyword: str, idx: int) -> str:
    segment = " ".join(words)[:80]
    style   = IMAGE_STYLES[idx % len(IMAGE_STYLES)]
    return f"{keyword}, {segment}, {style}"

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

def _pexels_fallback(keyword: str, output_path: str) -> bool:
    headers = {"Authorization": PEXELS_API_KEY}
    for query in [keyword, "technology future", "artificial intelligence"]:
        params = {"query": query, "orientation": "portrait", "size": "medium", "per_page": 15}
        r = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params)
        videos = r.json().get("videos", [])
        if videos:
            video = random.choice(videos[:8])
            files = sorted(video["video_files"], key=lambda x: x.get("width", 0))
            dl = requests.get(files[-1]["link"], stream=True)
            with open(output_path, "wb") as f:
                for chunk in dl.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
    return False

def generate_background(guion: str, keyword: str, duration: float, tmp_dir: str) -> str:
    """Genera slideshow con imágenes IA cambiando cada 3s. Fallback a Pexels."""
    img_dir = os.path.join(tmp_dir, "slides")
    os.makedirs(img_dir, exist_ok=True)

    n_slides   = max(12, int(duration / 3))
    words      = guion.split()
    chunk_size = max(1, len(words) // n_slides)
    chunks     = [words[i:i+chunk_size] for i in range(0, len(words), chunk_size)][:n_slides]

    tasks = [
        (i, _build_prompt(chunk, keyword, i),
         os.path.join(img_dir, f"slide_{i:03d}.jpg"),
         random.randint(1, 99999))
        for i, chunk in enumerate(chunks)
    ]

    print(f"      Generando {len(tasks)} imágenes IA en paralelo...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(_fetch_image, tasks))

    image_paths = [p for p in results if p and os.path.exists(p)]

    # Si consiguió suficientes imágenes → slideshow
    if len(image_paths) >= 8:
        print(f"      {len(image_paths)}/{len(tasks)} imágenes generadas ✓")
        secs_per = duration / len(image_paths)
        concat   = os.path.join(tmp_dir, "slides.txt")
        with open(concat, "w") as f:
            for p in image_paths:
                f.write(f"file '{p}'\n")
                f.write(f"duration {secs_per:.3f}\n")
            f.write(f"file '{image_paths[-1]}'\n")

        slideshow = os.path.join(tmp_dir, "slideshow.mp4")
        cmd = [
            FFMPEG, "-y",
            "-f", "concat", "-safe", "0", "-i", concat,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,format=yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-r", "30",
            slideshow
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return slideshow

    # Fallback: Pexels
    print("      Pollinations limitado, usando Pexels como fallback...")
    pexels_path = os.path.join(tmp_dir, "background.mp4")
    _pexels_fallback(keyword, pexels_path)
    return pexels_path


# ── Paso 5: Captions animadas ─────────────────────────────────────────────────
def estimate_captions(script: str, duration: float) -> list:
    words         = script.split()
    time_per_word = (duration - 1.0) / max(len(words), 1)
    phrases, i    = [], 0
    while i < len(words):
        chunk = words[i:i+4]
        phrase = " ".join(chunk)
        start  = 0.5 + i * time_per_word
        end    = 0.5 + (i + len(chunk)) * time_per_word
        phrases.append((phrase, start, end))
        i += 4
    return phrases

def build_caption_filter(phrases: list, hook_text: str = "") -> str:
    filters = []
    if hook_text:
        safe = (hook_text.replace("'","").replace('"',"")
                         .replace("\\","").replace("%","")
                         .replace(":","").replace("\n"," "))[:40]
        filters.append(
            f"drawtext=fontfile='{FONT}':text='{safe}'"
            f":fontcolor=white:fontsize=90"
            f":x=(w-text_w)/2:y=(h-text_h)/2-80"
            f":box=1:boxcolor=black@0.75:boxborderw=22"
            f":bordercolor=0x00DCFF:borderw=3"
            f":enable='between(t,0.0,2.5)'"
        )
    for text, start, end in phrases:
        safe = (text.replace("'","").replace('"',"")
                    .replace("\\","").replace("%","")
                    .replace(":","").replace("\n"," "))[:35]
        filters.append(
            f"drawtext=fontfile='{FONT}':text='{safe}'"
            f":fontcolor=yellow:fontsize=74"
            f":x=(w-text_w)/2:y=h-310"
            f":box=1:boxcolor=black@0.65:boxborderw=18"
            f":enable='between(t,{start:.2f},{end:.2f})'"
        )
    return ",".join(filters)


# ── Paso 6: Ensamblar video ───────────────────────────────────────────────────
def create_short(audio_path: str, bg_path: str, output_path: str,
                 script_text: str = "", hook_text: str = ""):
    duration = MP3(audio_path).info.length + 0.5

    vf = (
        "scale=1188:2112:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "eq=contrast=1.12:brightness=-0.02:saturation=1.35:gamma=0.95"
    )

    if script_text:
        phrases    = estimate_captions(script_text, duration)
        cap_filter = build_caption_filter(phrases, hook_text)
        if cap_filter:
            vf += "," + cap_filter

    # Si el bg es slideshow (ya a 1080x1920) omitir scale/crop
    is_slideshow = "slideshow" in bg_path
    if is_slideshow:
        vf = "eq=contrast=1.12:brightness=-0.02:saturation=1.35:gamma=0.95"
        if script_text:
            vf += "," + cap_filter

    cmd = [
        FFMPEG, "-y",
        "-i", bg_path,
        "-i", audio_path,
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest", "-movflags", "+faststart",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr[-400:]}")


# ── Miniatura ─────────────────────────────────────────────────────────────────
def create_thumbnail(title: str, output_path: str):
    W, H = 1280, 720
    img  = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)

    lerp = lambda c1, c2, t: tuple(int(c1[i]+(c2[i]-c1[i])*t) for i in range(3))
    for x in range(W):
        draw.line([(x,0),(x,H)], fill=lerp(BG_DARK, BG_MID, x/W*0.9))

    random.seed(hash(title) % 9999)
    nodes = [(random.randint(0,W), random.randint(0,H)) for _ in range(40)]
    for i,(x1,y1) in enumerate(nodes):
        for x2,y2 in nodes[i+1:i+3]:
            if math.sqrt((x2-x1)**2+(y2-y1)**2) < 250:
                draw.line([(x1,y1),(x2,y2)], fill=(0,50,80), width=1)
    for x,y in nodes:
        draw.ellipse([x-3,y-3,x+3,y+3], fill=CYAN_DIM)

    draw.rectangle([0,0,8,H], fill=CYAN)

    try:
        f_logo  = ImageFont.truetype(FONT, 36)
        f_title = ImageFont.truetype(FONT, 72)
        f_sub   = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 36)
    except:
        f_logo = f_title = f_sub = ImageFont.load_default()

    draw.text((30,28), "IA", font=f_logo, fill=WHITE)
    draw.text((75,28), "al Día", font=f_logo, fill=CYAN)
    draw.rectangle([30,80,300,83], fill=CYAN)

    words  = title.replace("🤯","").replace("🔥","").replace("💡","").replace("😱","").strip().split()
    lines, line = [], []
    for w in words:
        line.append(w)
        if len(" ".join(line)) > 22:
            lines.append(" ".join(line[:-1]))
            line = [w]
    if line:
        lines.append(" ".join(line))
    lines    = lines[:3]
    y_start  = H//2 - len(lines)*45
    for i, ln in enumerate(lines):
        draw.text((W//2, y_start+i*85), ln, font=f_title,
                  fill=WHITE, anchor="mm", stroke_width=3, stroke_fill=BG_DARK)

    emojis = [c for c in title if ord(c) > 127000]
    if emojis:
        draw.text((W-90, H//2), emojis[0], font=f_title, fill=CYAN, anchor="mm")

    draw.rectangle([30,H-70,W-30,H-67], fill=CYAN)
    draw.text((W//2,H-40), "Inteligencia Artificial para todos los días",
              font=f_sub, fill=GRAY, anchor="mm")
    img.save(output_path)


def upload_thumbnail(youtube, video_id: str, thumb_path: str):
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumb_path, mimetype="image/png")
        ).execute()
        print("      Miniatura aplicada ✓")
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
    print(f"\n{'='*52}")
    print(f"  IA al Día — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*52}\n")

    with tempfile.TemporaryDirectory() as tmp:
        audio_path  = os.path.join(tmp, "audio.mp3")
        output_path = os.path.join(tmp, "short.mp4")
        thumb_path  = os.path.join(tmp, "thumbnail.png")

        print("[1/6] Buscando tema trending...")
        topic = get_trending_topic()

        print("[2/6] Generando script con hook viral...")
        script = generate_script(topic)
        print(f"      Título: {script['titulo']}")

        print("[3/6] Generando voz (Lorenzo, Chile)...")
        generate_audio(script["guion"], audio_path)
        duration = MP3(audio_path).info.length + 0.5

        print("[4/6] Generando fondo con imágenes IA...")
        bg_path = generate_background(
            script["guion"], script["keyword_video"], duration, tmp
        )

        print("[5/6] Ensamblando Short...")
        hook_text = script.get("hook_texto", "")
        create_short(audio_path, bg_path, output_path, script["guion"], hook_text)

        print("[5/6] Generando miniatura...")
        create_thumbnail(script["titulo"], thumb_path)

        descripcion_final = (
            script["descripcion"]
            + AFFILIATES
            + "\n\n━━━━━━━━━━━━━━━━\n"
            "🤖 IA al Día — Noticias de inteligencia artificial para LATAM.\n"
            "⚠️ Contenido creado con asistencia de IA con fines educativos."
        )

        print("[6/6] Subiendo a YouTube...")
        youtube  = get_youtube_client()
        video_id = upload_to_youtube(
            youtube, output_path,
            script["titulo"], descripcion_final, script["tags"]
        )
        upload_thumbnail(youtube, video_id, thumb_path)

    print(f"\n  Short publicado: https://youtube.com/shorts/{video_id}")
    print(f"  Título: {script['titulo']}\n")


if __name__ == "__main__":
    main()
