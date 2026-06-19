#!/usr/bin/env python3
"""
IA al Día v4.0 — Demo Style + Breaking News
Formato: chat IA animado + PIP reacción Pexels + noticiario + captions TikTok word-by-word
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
import textwrap

FFMPEG = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent
ENV_FILE       = BASE_DIR / ".env"
CLIENT_SECRETS = BASE_DIR / "client_secrets.json"
TOKEN_FILE     = BASE_DIR / "token.json"
CREDITS_FILE   = BASE_DIR / "credits.json"
SCOPES         = ["https://www.googleapis.com/auth/youtube"]
GEMINI_MODELS  = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]

_MAC_FONT      = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
_LIN_FONT      = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_MAC_REG       = "/System/Library/Fonts/Supplemental/Arial.ttf"
_LIN_REG       = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD      = _MAC_FONT if os.path.exists(_MAC_FONT) else _LIN_FONT
FONT_REG       = _MAC_REG  if os.path.exists(_MAC_REG)  else _LIN_REG

# Paletas de UI por herramienta
TOOL_THEMES = {
    "ChatGPT": dict(
        bg=(13,17,23), chrome=(22,27,34), url="chat.openai.com",
        user_bubble=(50,54,66), ai_bg=(13,17,23),
        accent=(25,195,125), text=(225,232,240), label="ChatGPT"
    ),
    "Claude": dict(
        bg=(28,26,23), chrome=(44,42,38), url="claude.ai",
        user_bubble=(55,52,48), ai_bg=(28,26,23),
        accent=(204,120,50), text=(240,237,230), label="Claude"
    ),
    "Gemini": dict(
        bg=(26,28,30), chrome=(41,43,46), url="gemini.google.com",
        user_bubble=(52,55,60), ai_bg=(26,28,30),
        accent=(138,180,248), text=(232,234,237), label="Gemini"
    ),
}
TOOLS = list(TOOL_THEMES.keys())

W, H = 1080, 1920   # dimensiones Short 9:16

COST_PER_VIDEO  = {"gemini_tts": 0.006, "imagen4_thumb": 0.04, "gemini_pro": 0.005}
CREDIT_TOTAL    = 300.0
ALERT_THRESHOLD = 30.0

AFFILIATES = (
    "\n\n💡 Herramientas IA que uso en este video:\n"
    "→ ChatGPT: https://chat.openai.com\n"
    "→ Claude AI: https://claude.ai\n"
    "→ Gemini: https://gemini.google.com\n"
    "→ Perplexity: https://perplexity.ai"
)

RSS_FEEDS = [
    "https://venturebeat.com/category/ai/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
]

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


# ── Créditos ──────────────────────────────────────────────────────────────────
def load_credits():
    if CREDITS_FILE.exists():
        try: return json.loads(CREDITS_FILE.read_text())
        except: pass
    return {"spent": 0.0, "runs": 0, "last_run": ""}

def update_credits(used_tts, used_imagen, used_pro):
    data = load_credits()
    cost = (COST_PER_VIDEO["gemini_tts"] * used_tts +
            COST_PER_VIDEO["imagen4_thumb"] * used_imagen +
            COST_PER_VIDEO["gemini_pro"] * used_pro)
    data["spent"] += cost
    data["runs"]  += 1
    data["last_run"] = str(date.today())
    CREDITS_FILE.write_text(json.dumps(data, indent=2))
    remaining = CREDIT_TOTAL - data["spent"]
    print(f"      Crédito: ${cost:.3f} esta vez | Total: ${data['spent']:.2f} | Resto: ${remaining:.2f}")
    if remaining < ALERT_THRESHOLD:
        print(f"\n  ⚠️  ALERTA: Solo quedan ${remaining:.2f} de crédito. Recarga en console.cloud.google.com\n")
        summary = os.environ.get("GITHUB_STEP_SUMMARY", "")
        if summary:
            open(summary,"a").write(f"\n⚠️ **CRÉDITO BAJO**: ${remaining:.2f} restantes de $300\n")
    return data


# ── Paso 1: RSS + research ────────────────────────────────────────────────────
def get_headlines() -> list:
    headlines = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:4]:
                t = e.get("title", "").strip()
                if t and len(t) > 10:
                    headlines.append(t)
        except: pass
    return headlines[:12]

def research_topic(topic: str) -> str:
    try:
        data = urllib.parse.urlencode({"q": topic + " 2026", "b": ""}).encode()
        req  = urllib.request.Request(
            "https://html.duckduckgo.com/html/", data=data,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)<', html)
        return "\n".join(s.strip()[:200] for s in snippets[:5]) if snippets else ""
    except: return ""


# ── Paso 2: Script demo-style con Gemini 2.5 Pro ─────────────────────────────
def generate_script(headlines: list, research: str) -> tuple:
    client  = genai.Client(api_key=GEMINI_API_KEY)
    tool    = random.choice(TOOLS)
    h_block = "\n".join(f"- {h}" for h in headlines) if headlines else "tendencias IA 2026"
    r_block = f"\nHECHOS VERIFICADOS:\n{research}\n" if research else ""

    prompt = f"""Eres el creador de contenido de IA más viral de habla hispana.

NOTICIAS DEL DÍA:
{h_block}
{r_block}
HERRAMIENTA A DEMOSTRAR: {tool}

Crea un video corto (58-62 segundos) en formato DEMO donde se muestra cómo usar {tool} para algo útil y sorprendente.

ESTRUCTURA OBLIGATORIA:

GANCHO (0-4s): Frase de 7 palabras que detenga el scroll. Ejemplos:
  "Le pedí a la IA esto y quedé sin palabras"
  "Nadie te enseñó este truco de {tool}"
  "Hice esto en 10 segundos con IA y cambió todo"

DEMO (4-50s): Muestra el uso real. La narración explica QUÉ se está haciendo y POR QUÉ importa.
Incluye al menos UN dato numérico (tiempo ahorrado, dinero, %).

CIERRE (50-62s): Consecuencia para el espectador + "Sígueme para más IA al Día."

REGLAS:
- Narración máximo 9 palabras por oración
- Voz humana y directa: "mira esto", "no lo podía creer", "te juro que"
- Caso de uso PRÁCTICO: trabajo, dinero, productividad, aprendizaje
- El prompt de {tool} debe ser realista y copiable
- La respuesta de {tool} debe ser impresionante pero creíble

RESPONDE JSON sin markdown:
{{
  "titulo": "Título SEO, keyword al inicio, máximo 52 chars, emoji al final",
  "descripcion": "2 oraciones con keyword. Valor concreto. #Shorts #IA #{tool.replace(' ','')} #InteligenciaArtificial #IaAlDia",
  "tags": ["ia 2026", "chatgpt trucos", "ia productividad", "ia para trabajar", "ia al dia", "shorts ia", "tecnologia latina", "ia secretos", "futuro ia", "automatizacion ia", "ia gratis", "ia prompts"],
  "hook_texto": "primeras 7 palabras exactas del guión",
  "narracion": "guión completo de lo que dice la voz (155-170 palabras, estructura gancho→demo→cierre)",
  "prompt_usuario": "el prompt exacto que escribe el usuario en {tool} (máximo 2 líneas, realista)",
  "respuesta_ia": "la respuesta de {tool} que se muestra en pantalla (3-5 líneas, impresionante y útil)",
  "caso_uso": "descripción en 4 palabras del caso de uso",
  "ticker_noticias": ["noticia breve 1 sobre IA", "noticia breve 2", "noticia breve 3", "noticia breve 4"]
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
                if attempt < 2: time.sleep(15*(attempt+1))
        if response: break

    if not response:
        return _fallback_script(tool), False

    text = response.text.strip()
    if "```" in text:
        for part in text.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"): text = part; break
    try:
        return json.loads(text), used_pro
    except:
        return _fallback_script(tool), False

def _fallback_script(tool):
    return {
        "titulo": f"{tool}: el truco que nadie usa 🤯",
        "descripcion": f"Descubre cómo {tool} puede ahorrarte horas de trabajo. #Shorts #IA #InteligenciaArtificial #IaAlDia",
        "tags": ["ia 2026","chatgpt trucos","ia productividad","ia para trabajar","ia al dia","shorts ia","tecnologia latina","ia secretos","futuro ia","automatizacion ia","ia gratis","ia prompts"],
        "hook_texto": "Nadie te enseñó este truco de IA",
        "narracion": f"Nadie te enseñó este truco de {tool}. Llevo semanas usando esto y me ahorra más de 3 horas al día. Es simple. Le pides que haga algo que normalmente te tomaría toda la mañana. Y lo hace en 10 segundos. Yo lo uso para trabajo, para escribir, para planificar. El 80% de las personas usa mal la IA. Solo hacen preguntas básicas. Pero si sabes cómo pedirle las cosas, cambia todo. Esto lo hacen en las mejores empresas del mundo. Y tú lo puedes hacer desde hoy, gratis. Sígueme para más IA al Día.",
        "prompt_usuario": f"Actúa como un experto y ayúdame a redactar un email profesional para pedir un aumento de sueldo del 20%, siendo directo pero respetuoso.",
        "respuesta_ia": "Estimado [Nombre del jefe],\n\nLuego de 2 años de resultados consistentes, quiero conversar sobre ajustar mi compensación.\n\nHe liderado proyectos que generaron un 35% más de eficiencia. Estoy comprometido con seguir creciendo aquí.\n\n¿Podríamos agendar una reunión esta semana?\n\nGracias por su confianza.",
        "caso_uso": "email trabajo profesional",
        "ticker_noticias": ["OpenAI lanza GPT-5 con capacidades multimodales avanzadas","Google Gemini supera 1 billón de usuarios activos","IA reemplaza el 30% de tareas administrativas en empresas Fortune 500","Meta lanza modelo IA open source más potente hasta la fecha"],
        "tool": tool
    }


# ── Paso 3: TTS — Gemini o Edge ───────────────────────────────────────────────
def _add_pauses(text):
    return (text.replace(". ","... ").replace(", ","  ,")
                .replace(" Y ","  Y ").replace(" Pero ","  Pero "))

def _gemini_tts(text, path):
    try:
        from google.genai import types as gt
        c = genai.Client(api_key=GEMINI_API_KEY)
        r = c.models.generate_content(
            model="gemini-2.5-flash-preview-tts", contents=text,
            config=gt.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=gt.SpeechConfig(voice_config=gt.VoiceConfig(
                    prebuilt_voice_config=gt.PrebuiltVoiceConfig(voice_name="Charon")
                ))
            )
        )
        part = r.candidates[0].content.parts[0]
        if not (hasattr(part,"inline_data") and part.inline_data and part.inline_data.data):
            return False
        raw = base64.b64decode(part.inline_data.data)
        if len(raw) < 1000: return False
        rp = path.replace(".mp3","_raw.pcm")
        open(rp,"wb").write(raw)
        ok = subprocess.run([FFMPEG,"-y","-f","s16le","-ar","24000","-ac","1",
                             "-i",rp,"-c:a","libmp3lame","-b:a","128k",path],
                            capture_output=True).returncode == 0
        os.remove(rp)
        if ok and os.path.getsize(path) > 1000:
            print("      Voz: Gemini TTS ✓"); return True
    except Exception as e:
        if "429" not in str(e) and "quota" not in str(e).lower():
            print(f"      Gemini TTS: {str(e)[:50]}")
    return False

async def _edge_tts(text, path):
    await edge_tts.Communicate(_add_pauses(text), "es-CL-LorenzoNeural",
                                rate="-5%", pitch="-2Hz", volume="+10%").save(path)

def generate_audio(text, path):
    if _gemini_tts(text, path): return True
    print("      Voz: Edge-TTS (Lorenzo)")
    asyncio.run(_edge_tts(text, path)); return False


# ── Paso 4: Renderizar interfaz de chat (Pillow) ──────────────────────────────
def _wrap_text(text, font, max_width, draw):
    words = text.split()
    lines, line = [], []
    for w in words:
        test = " ".join(line + [w])
        if draw.textlength(test, font=font) <= max_width:
            line.append(w)
        else:
            if line: lines.append(" ".join(line))
            line = [w]
    if line: lines.append(" ".join(line))
    return lines

def render_chat_frame(theme: dict, prompt_user: str, response_ai: str,
                      response_progress: float, show_cursor: bool = True) -> Image.Image:
    """Renderiza un frame del chat. response_progress: 0.0-1.0"""
    img  = Image.new("RGB", (W, H), theme["bg"])
    draw = ImageDraw.Draw(img)

    # ── Chrome del navegador (top bar) ──
    bar_h = 90
    draw.rectangle([0, 0, W, bar_h], fill=theme["chrome"])
    # Círculos de tráfico (Mac style)
    for i, col in enumerate([(255,95,86),(255,189,46),(39,201,63)]):
        draw.ellipse([22+i*28, 32, 40+i*28, 50], fill=col)
    # URL bar
    draw.rounded_rectangle([90, 25, W-20, 65], radius=12, fill=theme["bg"])
    try:
        f_url = ImageFont.truetype(FONT_REG, 22)
    except: f_url = ImageFont.load_default()
    draw.text((W//2, 45), f"🔒 {theme['url']}", font=f_url,
              fill=(160,165,175), anchor="mm")

    # ── Header de la herramienta ──
    try:
        f_tool = ImageFont.truetype(FONT_BOLD, 28)
        f_msg  = ImageFont.truetype(FONT_REG,  30)
        f_name = ImageFont.truetype(FONT_BOLD, 26)
    except:
        f_tool = f_msg = f_name = ImageFont.load_default()

    draw.text((W//2, bar_h + 32), theme["label"], font=f_tool,
              fill=theme["accent"], anchor="mm")
    draw.line([40, bar_h+60, W-40, bar_h+60], fill=(50,55,65), width=1)

    y = bar_h + 80
    pad_x = 30
    bubble_w = W - pad_x*2

    # ── Burbuja usuario (derecha) ──
    user_lines = _wrap_text(prompt_user, f_msg, bubble_w - 40, draw)
    line_h     = 40
    u_h        = len(user_lines) * line_h + 30
    u_top      = y
    draw.rounded_rectangle([pad_x, u_top, W-pad_x, u_top+u_h],
                            radius=18, fill=theme["user_bubble"])
    # "Tú" label
    draw.text((pad_x+14, u_top+8), "Tú", font=f_name, fill=theme["accent"])
    for i, ln in enumerate(user_lines):
        draw.text((pad_x+14, u_top+34+i*line_h), ln, font=f_msg, fill=theme["text"])
    y = u_top + u_h + 20

    # ── Separador ──
    draw.line([pad_x, y, W-pad_x, y], fill=(50,55,65), width=1)
    y += 20

    # ── Ícono IA ──
    r = 22
    draw.ellipse([pad_x, y, pad_x+r*2, y+r*2], fill=theme["accent"])
    draw.text((pad_x+r, y+r), theme["label"][0], font=f_name,
              fill=(255,255,255), anchor="mm")
    draw.text((pad_x+r*2+12, y+r), theme["label"], font=f_name,
              fill=theme["accent"], anchor="lm")
    y += r*2 + 14

    # ── Respuesta IA (progresiva) ──
    chars_to_show = int(len(response_ai) * response_progress)
    partial       = response_ai[:chars_to_show]
    if show_cursor and response_progress < 1.0:
        partial += "▌"

    ai_lines = _wrap_text(partial, f_msg, bubble_w - 20, draw)
    for ln in ai_lines:
        if y + line_h > H - 350: break
        draw.text((pad_x+14, y), ln, font=f_msg, fill=theme["text"])
        y += line_h

    # ── Thinking indicator si no hay respuesta aún ──
    if response_progress < 0.08:
        for i, col in enumerate([theme["accent"], (100,105,115), (70,75,85)]):
            cx = pad_x + 20 + i*22
            draw.ellipse([cx-8, y-8, cx+8, y+8], fill=col)

    return img


def generate_chat_video(script: dict, duration: float, tmp_dir: str) -> str:
    """Genera video del chat con animación progresiva (8 key frames)."""
    theme     = TOOL_THEMES.get(script.get("tool", "ChatGPT"),
                                TOOL_THEMES[random.choice(TOOLS)])
    prompt    = script.get("prompt_usuario", "")
    response  = script.get("respuesta_ia", "")
    frames_dir = os.path.join(tmp_dir, "chat_frames")
    os.makedirs(frames_dir, exist_ok=True)

    # 8 key frames: progresión de 0% a 100% de la respuesta
    n_frames   = 8
    progressions = [0.0, 0.05, 0.20, 0.40, 0.60, 0.75, 0.90, 1.0]
    secs_per   = duration / n_frames

    frame_paths = []
    for i, prog in enumerate(progressions):
        frame = render_chat_frame(theme, prompt, response, prog, show_cursor=(prog < 1.0))
        fp    = os.path.join(frames_dir, f"frame_{i:02d}.png")
        frame.save(fp)
        frame_paths.append(fp)

    # Crear concat list con duración por frame
    concat_f = os.path.join(tmp_dir, "chat_frames.txt")
    with open(concat_f, "w") as f:
        for fp in frame_paths:
            f.write(f"file '{fp}'\n")
            f.write(f"duration {secs_per:.3f}\n")
        f.write(f"file '{frame_paths[-1]}'\n")

    chat_vid = os.path.join(tmp_dir, "chat.mp4")
    cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_f,
           "-vf", "scale=1080:1920,format=yuv420p",
           "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-r", "25",
           chat_vid]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Chat video error: {r.stderr[-200:]}")
    print("      Chat animado ✓")
    return chat_vid


# ── Paso 5: PIP de reacción (Pexels portrait) ─────────────────────────────────
def get_reaction_clip(tmp_dir: str) -> str:
    headers = {"Authorization": PEXELS_API_KEY}
    queries = ["person shocked computer", "woman amazed laptop", "man screen reaction",
               "person looking phone surprised", "woman working computer"]
    random.shuffle(queries)
    for q in queries:
        try:
            r = requests.get("https://api.pexels.com/videos/search", headers=headers,
                             params={"query":q,"orientation":"portrait","per_page":8}, timeout=10)
            videos = r.json().get("videos", [])
            if not videos: continue
            video = random.choice(videos[:5])
            files = sorted(video["video_files"], key=lambda x: x.get("width",0))
            # Preferir vertical
            vertical = [f for f in files if f.get("width",0) <= f.get("height",0)]
            chosen   = random.choice(vertical) if vertical else files[-1]
            out = os.path.join(tmp_dir, "reaction.mp4")
            dl  = requests.get(chosen["link"], stream=True, timeout=30)
            with open(out, "wb") as f:
                for chunk in dl.iter_content(8192): f.write(chunk)
            if os.path.getsize(out) > 50000:
                print(f"      PIP reacción: '{q}' ✓")
                return out
        except: continue
    return ""


# ── Paso 6: Whisper captions ──────────────────────────────────────────────────
def transcribe_whisper(audio_path: str) -> list:
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("tiny", device="cpu", compute_type="int8",
                             download_root="/tmp/whisper_models")
        segs, _ = model.transcribe(audio_path, language="es", word_timestamps=True)
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

def estimate_word_timestamps(script: str, duration: float) -> list:
    words = script.split()
    tpw   = (duration - 1.0) / max(len(words), 1)
    return [{"word": w, "start": 0.5 + i*tpw, "end": 0.5 + (i+1)*tpw}
            for i, w in enumerate(words)]


# ── Paso 7: Ensamblar final ───────────────────────────────────────────────────
def assemble_final(chat_vid: str, reaction_clip: str, audio_path: str,
                   words: list, hook_text: str, ticker_news: list,
                   music_path: str, output_path: str, duration: float):

    def safe(t):
        return (t.replace("'","").replace('"',"").replace("\\","")
                 .replace("%","").replace(":","").replace("\n"," "))[:45]

    # ── Captions TikTok: UNA palabra a la vez, grande y centrada ──
    cap_filters = []

    # Hook visual — primeros 3.5s
    if hook_text:
        s = safe(hook_text)
        cap_filters.append(
            f"drawtext=fontfile='{FONT_BOLD}':text='{s}'"
            f":fontcolor=white:fontsize=80"
            f":x=(w-text_w)/2:y=h/2-60"
            f":shadowcolor=black@0.95:shadowx=4:shadowy=4"
            f":bordercolor=black:borderw=3"
            f":enable='between(t,0,3.5)'"
        )

    # Palabras individuales (TikTok style)
    for wd in words:
        s = safe(wd["word"])
        if not s: continue
        cap_filters.append(
            f"drawtext=fontfile='{FONT_BOLD}':text='{s}'"
            f":fontcolor=white:fontsize=108"
            f":x=(w-text_w)/2:y=h-380"
            f":shadowcolor=black@0.98:shadowx=5:shadowy=5"
            f":bordercolor=black:borderw=4"
            f":enable='between(t,{wd['start']:.2f},{wd['end']:.2f})'"
        )

    # ── Breaking news banner (top) ──
    today = datetime.now().strftime("%d %b %Y")
    banner_text = safe(f"🔴 EN VIVO  ·  IA al Día  ·  {today}")
    cap_filters.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='{banner_text}'"
        f":fontcolor=white:fontsize=32"
        f":x=(w-text_w)/2:y=16"
        f":box=1:boxcolor=0xCC0000@0.92:boxborderw=14"
    )

    # ── Ticker inferior (scrolling news) ──
    ticker_text = "  ·  ".join([safe(n) for n in (ticker_news or ["IA al Día - Síguenos para más"])]) + "  "
    # Scroll de derecha a izquierda en 20 segundos por ciclo
    cap_filters.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='{ticker_text}'"
        f":fontcolor=white:fontsize=28"
        f":x=w-mod(t*120\\,w+text_w):y=h-52"
        f":box=1:boxcolor=black@0.88:boxborderw=8"
    )

    vf = ",".join(cap_filters)

    # ── Construir comando FFmpeg ──
    inputs  = ["-i", chat_vid, "-i", audio_path]
    n_inputs = 2

    # Agregar música ambient
    has_music = music_path and os.path.exists(music_path)
    if has_music:
        inputs += ["-i", music_path]
        n_inputs += 1

    # Agregar PIP reacción
    has_pip = reaction_clip and os.path.exists(reaction_clip)
    if has_pip:
        inputs += ["-i", reaction_clip]

    if has_pip and has_music:
        # Video + voz + música + PIP
        fc = (
            f"[0:v]scale=1080:1920,{vf}[main];"
            f"[{n_inputs}:v]scale=280:370,format=yuv420p[pip];"
            f"[main][pip]overlay=x=W-w-20:y=H-h-90[vout];"
            f"[2:a]volume='if(gt(t,0),0.10,0.0)':eval=frame[music];"
            f"[1:a][music]amix=inputs=2:duration=first:weights=1 0.5[aout]"
        )
        cmd = [FFMPEG, "-y"] + inputs + [
            "-t", str(duration),
            "-filter_complex", fc,
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart", output_path
        ]
    elif has_pip:
        fc = (
            f"[0:v]scale=1080:1920,{vf}[main];"
            f"[2:v]scale=280:370,format=yuv420p[pip];"
            f"[main][pip]overlay=x=W-w-20:y=H-h-90[vout]"
        )
        cmd = [FFMPEG, "-y"] + inputs + [
            "-t", str(duration),
            "-filter_complex", fc,
            "-map", "[vout]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart", output_path
        ]
    elif has_music:
        fc = (
            f"[0:v]scale=1080:1920,{vf}[vout];"
            f"[2:a]volume=0.08[music];"
            f"[1:a][music]amix=inputs=2:duration=first:weights=1 0.5[aout]"
        )
        cmd = [FFMPEG, "-y"] + inputs + [
            "-t", str(duration),
            "-filter_complex", fc,
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart", output_path
        ]
    else:
        cmd = [FFMPEG, "-y"] + inputs + [
            "-t", str(duration),
            "-vf", f"scale=1080:1920,{vf}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart", output_path
        ]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg ensamble: {r.stderr[-400:]}")
    print("      Video ensamblado ✓")


# ── Música ambient ─────────────────────────────────────────────────────────────
def generate_ambient_music(duration: float, path: str) -> bool:
    try:
        expr = ("aevalsrc=0.05*sin(2*PI*130.8*t)*abs(sin(2*PI*0.2*t))+"
                "0.04*sin(2*PI*196.0*t)*abs(sin(2*PI*0.2*t+1.5)):s=44100")
        cmd = [FFMPEG,"-y","-f","lavfi","-i",expr,"-t",str(duration+1),
               "-af",f"afade=t=in:d=2,afade=t=out:st={duration-2}:d=2",
               "-c:a","aac","-b:a","64k",path]
        return subprocess.run(cmd, capture_output=True).returncode == 0
    except: return False


# ── Miniatura ─────────────────────────────────────────────────────────────────
def create_thumbnail(title: str, tool: str, output_path: str) -> bool:
    if _thumbnail_imagen4(title, tool, output_path): return True
    _thumbnail_pillow(title, tool, output_path); return False

def _thumbnail_imagen4(title: str, tool: str, output_path: str) -> bool:
    try:
        from google.genai import types as gt
        import io
        c     = genai.Client(api_key=GEMINI_API_KEY)
        clean = re.sub(r'[\U0001F000-\U0001FFFF]','',title).strip()
        r     = c.models.generate_images(
            model="imagen-4.0-fast-generate-001",
            prompt=f"YouTube thumbnail, {tool} chat interface on dark screen, neon glow, person amazed, dramatic lighting, cinematic, 16:9, no text",
            config=gt.GenerateImagesConfig(number_of_images=1, aspect_ratio="16:9",
                                           safety_filter_level="BLOCK_LOW_AND_ABOVE")
        )
        base = Image.open(io.BytesIO(r.generated_images[0].image.image_bytes)).resize((1280,720))
        _branding(base, clean, output_path); print("      Miniatura: Imagen 4 ✓"); return True
    except Exception as e:
        if "429" not in str(e) and "quota" not in str(e).lower():
            print(f"      Imagen 4: {str(e)[:60]}")
        return False

def _thumbnail_pillow(title: str, tool: str, output_path: str):
    img = Image.new("RGB",(1280,720),(8,12,28))
    draw = ImageDraw.Draw(img)
    for x in range(1280):
        t = x/1280
        c = tuple(int(a+(b-a)*t) for a,b in zip((8,12,28),(14,22,54)))
        draw.line([(x,0),(x,720)],fill=c)
    theme = TOOL_THEMES.get(tool, TOOL_THEMES["ChatGPT"])
    draw.rounded_rectangle([60,140,820,580],radius=20,fill=theme["chrome"])
    draw.rounded_rectangle([80,160,800,220],radius=10,fill=theme["bg"])
    try:
        furl = ImageFont.truetype(FONT_REG,22)
        draw.text((440,190),f"🔒 {theme['url']}",font=furl,fill=(140,145,155),anchor="mm")
    except: pass
    clean = re.sub(r'[\U0001F000-\U0001FFFF]','',title).strip()
    _branding(img, clean, output_path)

def _branding(img, title, output_path):
    W2,H2 = img.size
    draw  = ImageDraw.Draw(img)
    try:
        fb = ImageFont.truetype(FONT_BOLD,64)
        fl = ImageFont.truetype(FONT_BOLD,30)
        fs = ImageFont.truetype(FONT_REG,26)
    except:
        fb=fl=fs=ImageFont.load_default()
    draw.rectangle([0,0,6,H2],fill=(0,220,255))
    draw.text((24,22),"IA",font=fl,fill=(255,255,255))
    draw.text((66,22),"al Día",font=fl,fill=(0,220,255))
    draw.rectangle([24,68,270,71],fill=(0,220,255))
    words=title.split(); lines,ln=[],[]
    for w in words:
        ln.append(w)
        if len(" ".join(ln))>18: lines.append(" ".join(ln[:-1])); ln=[w]
    if ln: lines.append(" ".join(ln))
    y=H2//2-len(lines[:3])*36
    for ln in lines[:3]:
        draw.text((W2//2+3,y+3),ln,font=fb,fill=(0,0,0),anchor="mm")
        draw.text((W2//2,y),ln,font=fb,fill=(255,255,255),anchor="mm")
        y+=76
    draw.rectangle([24,H2-62,W2-24,H2-59],fill=(0,220,255))
    draw.text((W2//2,H2-36),"Inteligencia Artificial · Todos los días",
              font=fs,fill=(160,175,210),anchor="mm")
    img.save(output_path)


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
    return build("youtube","v3",credentials=creds)

def upload_to_youtube(youtube, video_path, title, description, tags) -> str:
    body = {
        "snippet": {"title":title,"description":description,
                    "tags":tags+["shorts","inteligenciaartificial","tecnologia","ia","iaaldia"],
                    "categoryId":"28","defaultLanguage":"es"},
        "status": {"privacyStatus":"public","selfDeclaredMadeForKids":False},
    }
    media   = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status",body=body,media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status: print(f"  Subiendo... {int(status.progress()*100)}%",end="\r")
    print(); return response["id"]

def upload_thumbnail(youtube, video_id, thumb_path):
    try:
        youtube.thumbnails().set(videoId=video_id,
            media_body=MediaFileUpload(thumb_path,mimetype="image/png")).execute()
        print("      Miniatura subida ✓")
    except Exception as e:
        print(f"      Miniatura omitida: {str(e)[:50]}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*55}")
    print(f"  IA al Día v4.0 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Demo Style: Chat IA + PIP Reacción + Breaking News")
    print(f"{'='*55}\n")

    used_tts = used_imagen = used_pro = False

    with tempfile.TemporaryDirectory() as tmp:
        audio_path  = os.path.join(tmp, "audio.mp3")
        music_path  = os.path.join(tmp, "ambient.aac")
        output_path = os.path.join(tmp, "short.mp4")
        thumb_path  = os.path.join(tmp, "thumbnail.png")

        print("[1/7] RSS + research...")
        headlines = get_headlines()
        topic     = headlines[0] if headlines else "inteligencia artificial 2026"
        research  = research_topic(topic)
        print(f"      {len(headlines)} titulares | {len(research.splitlines())} snippets")

        print("[2/7] Generando script demo (Gemini 2.5 Pro)...")
        result = generate_script(headlines, research)
        script, used_pro = result if isinstance(result, tuple) else (result, False)
        tool   = script.get("tool", random.choice(TOOLS))
        if "tool" not in script: script["tool"] = tool
        print(f"      Herramienta: {tool}")
        print(f"      Título: {script['titulo']}")
        print(f"      Caso de uso: {script.get('caso_uso','')}")

        print("[3/7] Generando voz...")
        used_tts = generate_audio(script["narracion"], audio_path)
        duration = MP3(audio_path).info.length + 0.5
        print(f"      Duración: {duration:.1f}s")

        print("[4/7] Renderizando chat animado...")
        chat_vid = generate_chat_video(script, duration, tmp)

        print("[5/7] Descargando clip de reacción (PIP)...")
        reaction = get_reaction_clip(tmp)

        print("[6/7] Captions word-by-word (Whisper)...")
        words = transcribe_whisper(audio_path)
        if not words:
            words = estimate_word_timestamps(script["narracion"], duration)

        print("[6/7] Música ambient...")
        has_music = generate_ambient_music(duration, music_path)

        print("[6/7] Ensamblando final...")
        ticker = script.get("ticker_noticias", [])
        assemble_final(chat_vid, reaction, audio_path, words,
                       script.get("hook_texto",""), ticker,
                       music_path if has_music else "",
                       output_path, duration)

        print("[6/7] Miniatura...")
        used_imagen = create_thumbnail(script["titulo"], tool, thumb_path)

        descripcion_final = (
            script["descripcion"] + AFFILIATES +
            "\n\n━━━━━━━━━━━━━━━━\n"
            "🤖 IA al Día — demos y noticias de IA para LATAM cada día.\n"
            "⚠️ Contenido creado con asistencia de IA con fines educativos."
        )

        print("[7/7] Subiendo a YouTube...")
        yt       = get_youtube_client()
        video_id = upload_to_youtube(yt, output_path,
                                     script["titulo"], descripcion_final, script["tags"])
        upload_thumbnail(yt, video_id, thumb_path)

        credits = update_credits(used_tts, used_imagen, used_pro)

    remaining = CREDIT_TOTAL - credits["spent"]
    print(f"\n  ✓ https://youtube.com/shorts/{video_id}")
    print(f"  ✓ {script['titulo']}")
    print(f"  ✓ ${remaining:.2f} de crédito restante\n")


if __name__ == "__main__":
    main()
