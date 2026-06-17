#!/usr/bin/env python3
"""
YouTube Shorts Automator — IA al Día
Mejoras: trending topics, hooks virales, miniaturas personalizadas
"""

import os
import json
import random
import requests
import subprocess
import tempfile
import time
import math
import feedparser
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import edge_tts
import asyncio
import imageio_ffmpeg
from mutagen.mp3 import MP3

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# ── Config ───────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"

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

CLIENT_SECRETS = BASE_DIR / "client_secrets.json"
TOKEN_FILE     = BASE_DIR / "token.json"
SCOPES         = ["https://www.googleapis.com/auth/youtube"]

TTS_VOICE = "es-CL-LorenzoNeural"

# Colores del canal IA al Día
BG_DARK  = (8, 12, 28)
BG_MID   = (14, 22, 54)
CYAN     = (0, 220, 255)
CYAN_DIM = (0, 140, 180)
WHITE    = (255, 255, 255)
GRAY     = (160, 175, 210)

# Temas de respaldo si los RSS fallan
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

# Hooks virales probados (se inyectan al prompt)
HOOK_FORMULAS = [
    "Empieza con una pregunta que genere curiosidad inmediata, por ejemplo: '¿Sabías que el 90% de la gente usa mal la IA?'",
    "Empieza con una afirmación sorpresiva: 'Esto va a reemplazar tu trabajo antes de que termine el año...'",
    "Empieza con un dato impactante: 'En solo 3 meses esta IA pasó de 0 a 100 millones de usuarios...'",
    "Empieza con urgencia: 'Para antes de cerrar este video. Lo que voy a mostrarte cambia todo...'",
    "Empieza con controversia: 'La mayoría de expertos en IA están equivocados en esto...'",
]


# ── Opción 3: Trending topics desde RSS ──────────────────────────────────────
RSS_FEEDS = [
    "https://venturebeat.com/category/ai/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
]

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
        print("      Sin RSS disponible, usando tema de respaldo")
        return random.choice(FALLBACK_TOPICS)

    # Pedir a Gemini que elija el más viral y lo adapte al español
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""Eres experto en contenido viral de IA para YouTube en español latinoamericano.

Estas son las noticias de IA más recientes en inglés:
{chr(10).join(f'- {h}' for h in headlines[:12])}

Selecciona la noticia con más potencial viral para una audiencia latina y tradúcela/adáptala a un tema de Short de YouTube en español.
Responde SOLO con el tema en español (1 oración, sin comillas, sin puntos al final), máximo 15 palabras."""

    for attempt in range(3):
        try:
            r = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            topic = r.text.strip().strip('"').strip("'")
            print(f"      Tema trending: {topic}")
            return topic
        except Exception as e:
            if attempt < 2:
                time.sleep(10)
            else:
                return random.choice(FALLBACK_TOPICS)


# ── Paso 1: Generar script con hooks virales ──────────────────────────────────
def generate_script(topic: str) -> dict:
    client = genai.Client(api_key=GEMINI_API_KEY)
    hook = random.choice(HOOK_FORMULAS)

    prompt = f"""Eres un creador de contenido viral en YouTube con 5 millones de suscriptores, especializado en inteligencia artificial para audiencia latinoamericana.

Crea un guión ULTRA enganchador para un YouTube Short (55 segundos máximo, 130-150 palabras) sobre: {topic}

REGLA DE ORO DEL GANCHO: {hook}

REGLAS DEL GUIÓN:
- Los primeros 3 segundos son CRÍTICOS: deben generar curiosidad o impacto inmediato
- Usa lenguaje conversacional y directo, como si hablaras con un amigo en persona
- Escribe oraciones CORTAS. Máximo 12 palabras por oración. Así suena más natural al hablar.
- Usa puntos seguidos frecuentemente. No comas largas. El ritmo debe ser dinámico.
- Sin asteriscos, guiones, ni símbolos especiales
- Termina con: "Sígueme para más IA al Día"
- Español latinoamericano neutro

El formato DEBE ser exactamente este JSON válido (sin markdown, sin texto extra):
{{
  "titulo": "título con emoji, máximo 60 caracteres, que genere clicks",
  "descripcion": "2-3 oraciones + hashtags: #IA #InteligenciaArtificial #ChatGPT #Tecnologia #Shorts #IaAlDia",
  "tags": ["inteligencia artificial", "chatgpt", "ia", "tecnologia", "shorts", "ia al dia"],
  "guion": "guión completo listo para leer en voz alta, sin símbolos especiales",
  "keyword_video": "keyword en inglés para Pexels (robot, artificial intelligence, technology, future, computer, data, brain)"
}}"""

    for attempt in range(5):
        try:
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            break
        except Exception as e:
            if "503" in str(e) and attempt < 4:
                wait = 15 * (attempt + 1)
                print(f"      Servidor ocupado, reintentando en {wait}s...")
                time.sleep(wait)
            else:
                raise

    text = response.text.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break

    return json.loads(text)


# ── Paso 2: Audio ─────────────────────────────────────────────────────────────
def _add_natural_pauses(text: str) -> str:
    # Pausa larga tras punto final de oración
    text = text.replace(". ", "... ")
    # Pausa media tras coma
    text = text.replace(", ", ",  ")
    # Pausa antes de "y" al inicio de idea nueva
    text = text.replace(" Y ", "  Y ")
    text = text.replace(" Pero ", "  Pero ")
    text = text.replace(" Ahora ", "  Ahora ")
    return text

async def _audio_async(text: str, path: str):
    text = _add_natural_pauses(text)
    communicate = edge_tts.Communicate(
        text,
        TTS_VOICE,
        rate="-8%",   # más lento = más natural
        pitch="-3Hz", # más grave = más cálido
        volume="+10%"
    )
    await communicate.save(path)

def generate_audio(text: str, path: str):
    asyncio.run(_audio_async(text, path))


# ── Paso 3: Video de fondo ────────────────────────────────────────────────────
def download_pexels_video(keyword: str, output_path: str) -> bool:
    headers = {"Authorization": PEXELS_API_KEY}
    for query in [keyword, "technology", "future city"]:
        params = {"query": query, "orientation": "portrait", "size": "medium", "per_page": 15}
        r = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params)
        videos = r.json().get("videos", [])
        if videos:
            break
    if not videos:
        return False
    video = random.choice(videos[:8])
    files = sorted(video["video_files"], key=lambda x: x.get("width", 0))
    r = requests.get(files[-1]["link"], stream=True)
    with open(output_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return True


# ── Paso 4: Ensamblar video ───────────────────────────────────────────────────
def create_short(audio_path: str, bg_video_path: str, output_path: str):
    duration = MP3(audio_path).info.length + 0.5
    cmd = [
        FFMPEG, "-y",
        "-stream_loop", "-1", "-i", bg_video_path,
        "-i", audio_path,
        "-t", str(duration),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest", "-movflags", "+faststart",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr[-300:]}")


# ── Opción 5: Miniatura personalizada ────────────────────────────────────────
def create_thumbnail(title: str, output_path: str):
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Gradiente de fondo
    def lerp(c1, c2, t):
        return tuple(int(c1[i] + (c2[i]-c1[i])*t) for i in range(3))

    for x in range(W):
        c = lerp(BG_DARK, BG_MID, x/W * 0.9)
        draw.line([(x,0),(x,H)], fill=c)

    # Red neuronal decorativa
    random.seed(hash(title) % 9999)
    nodes = [(random.randint(0, W), random.randint(0, H)) for _ in range(40)]
    for i, (x1,y1) in enumerate(nodes):
        for x2,y2 in nodes[i+1:i+3]:
            d = math.sqrt((x2-x1)**2+(y2-y1)**2)
            if d < 250:
                draw.line([(x1,y1),(x2,y2)], fill=(0,50,80), width=1)
    for x,y in nodes:
        draw.ellipse([x-3,y-3,x+3,y+3], fill=CYAN_DIM)

    # Barra lateral izquierda cyan
    draw.rectangle([0, 0, 8, H], fill=CYAN)

    # Logo "IA al Día" arriba izquierda
    try:
        f_logo = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 36)
        f_title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 72)
        f_sub   = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 36)
    except:
        f_logo = f_title = f_sub = ImageFont.load_default()

    draw.text((30, 28), "IA", font=f_logo, fill=WHITE)
    draw.text((75, 28), "al Día", font=f_logo, fill=CYAN)

    # Línea separadora
    draw.rectangle([30, 80, 300, 83], fill=CYAN)

    # Título del video (centrado, máximo 2 líneas)
    words = title.replace("🤯","").replace("🔥","").replace("💡","").strip().split()
    lines, line = [], []
    for w in words:
        line.append(w)
        if len(" ".join(line)) > 22:
            lines.append(" ".join(line[:-1]))
            line = [w]
    if line:
        lines.append(" ".join(line))
    lines = lines[:3]

    y_start = H//2 - len(lines) * 45
    for i, ln in enumerate(lines):
        draw.text((W//2, y_start + i*85), ln, font=f_title,
                  fill=WHITE, anchor="mm",
                  stroke_width=3, stroke_fill=BG_DARK)

    # Emoji grande si hay en el título
    emojis = [c for c in title if ord(c) > 127000]
    if emojis:
        draw.text((W-90, H//2), emojis[0], font=f_title, fill=CYAN, anchor="mm")

    # Línea inferior + subtexto
    draw.rectangle([30, H-70, W-30, H-67], fill=CYAN)
    draw.text((W//2, H-40), "Inteligencia Artificial para todos los días",
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
        print(f"      Miniatura omitida (canal sin verificar): {str(e)[:60]}")


# ── Auth YouTube ──────────────────────────────────────────────────────────────
def get_youtube_client():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


# ── Subir a YouTube ───────────────────────────────────────────────────────────
def upload_to_youtube(youtube, video_path: str, title: str, description: str, tags: list) -> str:
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
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
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
        bg_path     = os.path.join(tmp, "background.mp4")
        output_path = os.path.join(tmp, "short.mp4")
        thumb_path  = os.path.join(tmp, "thumbnail.png")

        print("[1/6] Buscando tema trending de IA...")
        topic = get_trending_topic()

        print("[2/6] Generando script con hook viral...")
        script = generate_script(topic)
        print(f"      Título: {script['titulo']}")

        print("[3/6] Generando voz (Lorenzo, Chile)...")
        generate_audio(script["guion"], audio_path)

        print(f"[4/6] Descargando video de fondo...")
        download_pexels_video(script["keyword_video"], bg_path)

        print("[5/6] Ensamblando Short 1080x1920...")
        create_short(audio_path, bg_path, output_path)

        print("[5/6] Generando miniatura personalizada...")
        create_thumbnail(script["titulo"], thumb_path)

        print("[6/6] Subiendo a YouTube...")
        youtube = get_youtube_client()
        video_id = upload_to_youtube(
            youtube, output_path,
            script["titulo"], script["descripcion"], script["tags"]
        )
        upload_thumbnail(youtube, video_id, thumb_path)

    print(f"\n  Short publicado: https://youtube.com/shorts/{video_id}")
    print(f"  Título: {script['titulo']}\n")


if __name__ == "__main__":
    main()
