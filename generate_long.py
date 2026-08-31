#!/usr/bin/env python3
"""
YouTube Long-Form Automator — IA al Día
Videos educativos de 8-10 minutos sobre IA. RPM $3-15 vs $0.03 de Shorts.
Pipeline: trending → script largo → TTS → 100+ imágenes IA → slideshow → YouTube
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

AFFILIATES = (
    "\n\n💡 Herramientas IA que recomiendo:\n"
    "→ ChatGPT: https://chat.openai.com\n"
    "→ Claude AI: https://claude.ai\n"
    "→ Gemini: https://gemini.google.com\n"
    "→ Perplexity: https://perplexity.ai"
)

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
    "cómo la inteligencia artificial está transformando el mundo del trabajo en 2026",
    "las 10 herramientas de IA más poderosas disponibles hoy gratis",
    "todo lo que debes saber sobre ChatGPT 5 y sus capacidades",
    "cómo ganar dinero con inteligencia artificial desde casa en 2026",
    "el futuro del trabajo con inteligencia artificial: qué empleos desaparecen",
]

IMAGE_STYLES = [
    "professional dark infographic, neon blue cyan, flat design, no text, vertical 9:16",
    "futuristic tech visualization, dark background, glowing elements, minimal, vertical",
    "modern educational diagram, navy background, bright cyan accents, geometric, vertical",
    "digital art tech concept, dark purple blue gradient, clean, no words, vertical 9:16",
    "data visualization abstract, dark theme, bright highlights, professional, vertical",
]


# ── Paso 1: Trending topic ────────────────────────────────────────────────────
def get_trending_topic() -> str:
    headlines = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                title = entry.get("title", "").strip()
                if title and len(title) > 10:
                    headlines.append(title)
        except Exception:
            continue

    if not headlines:
        return random.choice(FALLBACK_TOPICS)

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""Eres experto en contenido educativo viral de IA en español.

Noticias recientes de IA:
{chr(10).join(f'- {h}' for h in headlines[:15])}

Selecciona el tema con más potencial para un VIDEO LARGO (8-10 min) educativo en YouTube en español LATAM.
Debe ser un tema con suficiente profundidad para desarrollar 800-1000 palabras.
Responde SOLO el tema (1 oración, sin comillas, máximo 20 palabras)."""

    for model in GEMINI_MODELS:
        try:
            r = client.models.generate_content(model=model, contents=prompt)
            topic = r.text.strip().strip('"').strip("'")
            print(f"      Tema: {topic}")
            return topic
        except Exception as e:
            if "429" in str(e):
                continue
            time.sleep(10)
    return random.choice(FALLBACK_TOPICS)


# ── Paso 2: Script largo (800-1000 palabras) ──────────────────────────────────
def generate_long_script(topic: str) -> dict:
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""Eres un youtuber educativo sobre IA con 5 millones de suscriptores en LATAM. Creas videos profundos y bien investigados.

Crea un guión educativo COMPLETO para un video de YouTube de 8-10 minutos sobre: {topic}

ESTRUCTURA DEL VIDEO:
1. HOOK (0-30s): Pregunta o dato impactante que engancha. 40-50 palabras.
2. INTRODUCCIÓN (30s-1min): Presenta el tema y por qué importa. 80-100 palabras.
3. DESARROLLO (1min-7min): 4-5 secciones con subtítulos. Cada sección 150-180 palabras.
4. EJEMPLOS PRÁCTICOS: Casos reales, números, resultados concretos.
5. CIERRE (7min-8min): Resumen + llamada a la acción. 80-100 palabras.

ESTILO:
- Voz conversacional, como si hablaras con un amigo inteligente
- Incluye tu opinión personal ("yo creo", "en mi experiencia", "me sorprende que")
- Datos y números concretos cuando sea posible
- Oraciones cortas y dinámicas
- Sin asteriscos, guiones ni símbolos
- Español latinoamericano neutro

SEO:
- Título: keyword al inicio, 60-70 chars, 1 emoji, promete valor claro
- 15 tags específicos de 2-3 palabras sobre IA

JSON exacto (sin markdown):
{{
  "titulo": "título SEO para video largo, keyword-first, emoji al final, 60-70 chars",
  "descripcion": "Párrafo 1 (125 chars con keyword). Párrafo 2: índice del video (00:00 Intro\\n01:00 Sección 1\\netc.). #IA #InteligenciaArtificial #ChatGPT #Tecnologia #IaAlDia",
  "tags": ["ia 2026", "inteligencia artificial completo", "chatgpt tutorial", "ia herramientas", "ia al dia", "tecnologia latina", "ia noticias", "futuro ia", "automatizacion ia", "ia español", "ia para todos", "ia trabajo", "ia gratis", "ia educacion", "ia tutorial"],
  "guion": "guión completo 800-1000 palabras, listo para narrar en voz alta",
  "keyword_video": "keyword en inglés para imágenes (artificial intelligence, technology, robot, data, future)"
}}"""

    response = None
    for model in GEMINI_MODELS:
        for attempt in range(3):
            try:
                response = client.models.generate_content(model=model, contents=prompt)
                break
            except Exception as e:
                if "429" in str(e):
                    break
                if attempt < 2:
                    time.sleep(15 * (attempt + 1))
        if response:
            break
    if not response:
        raise RuntimeError("Todos los modelos Gemini agotaron cuota")

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
    text = text.replace(" Sin embargo ", "  Sin embargo ")
    return text

async def _tts_async(text: str, path: str):
    communicate = edge_tts.Communicate(
        _add_pauses(text), TTS_VOICE,
        rate="-6%", pitch="-3Hz", volume="+10%"
    )
    await communicate.save(path)

def generate_audio(text: str, path: str):
    asyncio.run(_tts_async(text, path))


# ── Paso 4: 100+ imágenes IA (1 cada 5 segundos) ─────────────────────────────
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
        r = requests.get(url, timeout=50)
        if r.status_code == 200 and len(r.content) > 5000:
            with open(out_path, "wb") as f:
                f.write(r.content)
            return out_path
    except Exception:
        pass
    return None

def _pexels_fallback(keyword: str, output_path: str, n_clips: int = 5) -> bool:
    headers = {"Authorization": PEXELS_API_KEY}
    queries = [keyword, "technology future", "artificial intelligence", "data science", "robot"]
    clips, used_ids = [], set()

    clip_dir = output_path + "_clips"
    os.makedirs(clip_dir, exist_ok=True)

    for i, q in enumerate(queries[:n_clips]):
        params = {"query": q, "orientation": "portrait", "size": "medium", "per_page": 15}
        r = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params)
        videos = [v for v in r.json().get("videos", []) if v["id"] not in used_ids]
        if not videos:
            continue
        video = random.choice(videos[:8])
        used_ids.add(video["id"])
        files = sorted(video["video_files"], key=lambda x: x.get("width", 0))
        dl    = requests.get(files[-1]["link"], stream=True)
        path  = os.path.join(clip_dir, f"clip_{i}.mp4")
        with open(path, "wb") as f:
            for chunk in dl.iter_content(chunk_size=8192):
                f.write(chunk)
        clips.append(path)

    if not clips:
        shutil.rmtree(clip_dir, ignore_errors=True)
        return False

    n = len(clips)
    inputs = []
    for c in clips:
        inputs += ["-i", c]
    filt = "".join(
        f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[v{i}];"
        for i in range(n)
    )
    filt += "".join(f"[v{i}]" for i in range(n))
    filt += f"concat=n={n}:v=1:a=0[vout]"
    cmd = [FFMPEG, "-y", *inputs,
           "-filter_complex", filt, "-map", "[vout]",
           "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-stream_loop", "-1",
           output_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    shutil.rmtree(clip_dir, ignore_errors=True)
    return result.returncode == 0

def generate_background(guion: str, keyword: str, duration: float, tmp_dir: str) -> str:
    img_dir = os.path.join(tmp_dir, "slides")
    os.makedirs(img_dir, exist_ok=True)

    # 1 imagen cada 5 segundos para video largo
    n_slides   = max(20, int(duration / 5))
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
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(_fetch_image, tasks))

    image_paths = [p for p in results if p and os.path.exists(p)]

    if len(image_paths) >= 15:
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

    print("      Pollinations limitado, usando Pexels fallback...")
    pexels_path = os.path.join(tmp_dir, "background.mp4")
    _pexels_fallback(keyword, pexels_path, n_clips=5)
    return pexels_path


# ── Paso 5: Captions animadas ─────────────────────────────────────────────────
def estimate_captions(script: str, duration: float) -> list:
    words         = script.split()
    time_per_word = (duration - 1.0) / max(len(words), 1)
    phrases, i    = [], 0
    while i < len(words):
        chunk  = words[i:i+5]
        phrase = " ".join(chunk)
        start  = 0.5 + i * time_per_word
        end    = 0.5 + (i + len(chunk)) * time_per_word
        phrases.append((phrase, start, end))
        i += 5
    return phrases

def build_caption_filter(phrases: list) -> str:
    filters = []
    for text, start, end in phrases:
        safe = (text.replace("'","").replace('"',"")
                    .replace("\\","").replace("%","")
                    .replace(":","").replace("\n"," "))[:40]
        filters.append(
            f"drawtext=fontfile='{FONT}':text='{safe}'"
            f":fontcolor=white:fontsize=60"
            f":x=(w-text_w)/2:y=h-260"
            f":box=1:boxcolor=black@0.6:boxborderw=14"
            f":enable='between(t,{start:.2f},{end:.2f})'"
        )
    return ",".join(filters)


# ── Paso 6: Ensamblar video ───────────────────────────────────────────────────
def create_video(audio_path: str, bg_path: str, output_path: str, script_text: str = ""):
    duration = MP3(audio_path).info.length + 0.5
    is_slideshow = "slideshow" in bg_path

    vf_base = "eq=contrast=1.1:brightness=-0.01:saturation=1.2"
    if not is_slideshow:
        vf_base = ("scale=1188:2112:force_original_aspect_ratio=increase,"
                   "crop=1080:1920," + vf_base)

    vf = vf_base
    if script_text:
        phrases    = estimate_captions(script_text, duration)
        cap_filter = build_caption_filter(phrases)
        if cap_filter:
            vf += "," + cap_filter

    cmd = [
        FFMPEG, "-y",
        "-i", bg_path,
        "-i", audio_path,
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
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

    draw.rectangle([0,0,12,H], fill=CYAN)

    try:
        f_logo  = ImageFont.truetype(FONT, 40)
        f_title = ImageFont.truetype(FONT, 68)
        f_sub   = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 34)
    except:
        f_logo = f_title = f_sub = ImageFont.load_default()

    draw.text((30,28), "IA", font=f_logo, fill=WHITE)
    draw.text((82,28), "al Día", font=f_logo, fill=CYAN)
    draw.rectangle([30,88,320,91], fill=CYAN)

    clean_title = title
    for emoji in ["🤯","🔥","💡","😱","⚠️","🚀","🤖"]:
        clean_title = clean_title.replace(emoji, "")
    clean_title = clean_title.strip()

    words  = clean_title.split()
    lines, line = [], []
    for w in words:
        line.append(w)
        if len(" ".join(line)) > 24:
            lines.append(" ".join(line[:-1]))
            line = [w]
    if line:
        lines.append(" ".join(line))
    lines   = lines[:3]
    y_start = H//2 - len(lines)*48
    for i, ln in enumerate(lines):
        draw.text((W//2, y_start+i*88), ln, font=f_title,
                  fill=WHITE, anchor="mm", stroke_width=3, stroke_fill=BG_DARK)

    emojis = [c for c in title if ord(c) > 127000]
    if emojis:
        draw.text((W-100, H//2), emojis[0], font=f_title, fill=CYAN, anchor="mm")

    draw.rectangle([30,H-75,W-30,H-72], fill=CYAN)
    draw.text((W//2,H-44), "IA al Día • Educación sobre Inteligencia Artificial",
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
            "tags": tags + ["inteligenciaartificial", "tecnologia", "ia", "iaaldia", "educacion"],
            "categoryId": "27",  # Educación (mayor RPM que Entretenimiento)
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
    print(f"  IA al Día LONG — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*52}\n")

    with tempfile.TemporaryDirectory() as tmp:
        audio_path  = os.path.join(tmp, "audio.mp3")
        output_path = os.path.join(tmp, "video.mp4")
        thumb_path  = os.path.join(tmp, "thumbnail.png")

        print("[1/6] Buscando tema para video largo...")
        topic = get_trending_topic()

        print("[2/6] Generando script educativo (800-1000 palabras)...")
        script = generate_long_script(topic)
        print(f"      Título: {script['titulo']}")
        word_count = len(script['guion'].split())
        print(f"      Palabras: {word_count}")

        print("[3/6] Generando narración TTS...")
        generate_audio(script["guion"], audio_path)
        duration = MP3(audio_path).info.length + 0.5
        print(f"      Duración: {duration/60:.1f} minutos")

        print(f"[4/6] Generando fondo con imágenes IA...")
        bg_path = generate_background(
            script["guion"], script.get("keyword_video", ""), duration, tmp
        )

        print("[5/6] Ensamblando video...")
        create_video(audio_path, bg_path, output_path, script["guion"])

        print("[5/6] Generando miniatura...")
        create_thumbnail(script["titulo"], thumb_path)

        descripcion_final = (
            script["descripcion"]
            + AFFILIATES
            + "\n\n━━━━━━━━━━━━━━━━\n"
            "🤖 IA al Día — Noticias y educación sobre inteligencia artificial para LATAM.\n"
            "⚠️ Contenido creado con asistencia de IA con fines educativos e informativos.\n"
            "📩 Contacto: iaaldia@gmail.com"
        )

        print("[6/6] Subiendo a YouTube...")
        youtube  = get_youtube_client()
        video_id = upload_to_youtube(
            youtube, output_path,
            script["titulo"], descripcion_final, script["tags"]
        )
        upload_thumbnail(youtube, video_id, thumb_path)

    print(f"\n  Video publicado: https://youtube.com/watch?v={video_id}")
    print(f"  Título: {script['titulo']}")
    print(f"  Duración: {duration/60:.1f} min\n")


if __name__ == "__main__":
    main()
