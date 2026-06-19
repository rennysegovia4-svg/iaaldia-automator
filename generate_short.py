#!/usr/bin/env python3
"""
IA al Día v5.0 — Persona Pexels + Gemini TTS + Captions TikTok word-by-word
"""

import os, json, random, requests, subprocess, tempfile, time, re, base64
import feedparser, shutil, urllib.parse, urllib.request, asyncio
from pathlib import Path
from datetime import datetime, date
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
CLIENT_SECRETS = BASE_DIR / "client_secrets.json"
TOKEN_FILE     = BASE_DIR / "token.json"
CREDITS_FILE   = BASE_DIR / "credits.json"
SCOPES         = ["https://www.googleapis.com/auth/youtube"]
GEMINI_MODELS  = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]

_MAC_FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
_LIN_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_MAC_REG  = "/System/Library/Fonts/Supplemental/Arial.ttf"
_LIN_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = _MAC_FONT if os.path.exists(_MAC_FONT) else _LIN_FONT
FONT_REG  = _MAC_REG  if os.path.exists(_MAC_REG)  else _LIN_REG

COST_PER_VIDEO  = {"gemini_tts": 0.006, "imagen4_thumb": 0.04, "gemini_pro": 0.005}
CREDIT_TOTAL    = 300.0
ALERT_THRESHOLD = 30.0

PRESENTER_QUERIES = [
    "man talking camera professional",
    "woman speaking camera presenter",
    "journalist interview camera portrait",
    "news anchor speaking portrait",
    "person vlog camera talking portrait",
    "man explaining camera close up",
    "woman presenting camera studio",
    "reporter speaking microphone portrait",
    "man interview camera serious",
    "woman news anchor portrait",
]

RSS_FEEDS = [
    "https://venturebeat.com/category/ai/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
]

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


# ── Créditos ──────────────────────────────────────────────────────────────────
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


# ── Paso 1: RSS + research ────────────────────────────────────────────────────
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
    try:
        data = urllib.parse.urlencode({"q": topic + " 2026", "b": ""}).encode()
        req  = urllib.request.Request(
            "https://html.duckduckgo.com/html/", data=data,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)<', html)
        return "\n".join(s.strip()[:200] for s in snippets[:5])
    except: return ""


# ── Paso 2: Script Gemini 2.5 Pro ────────────────────────────────────────────
def generate_script(headlines, research):
    client  = genai.Client(api_key=GEMINI_API_KEY)
    h_block = "\n".join(f"- {h}" for h in headlines) if headlines else "tendencias IA 2026"
    r_block = f"\nHECHOS VERIFICADOS:\n{research}\n" if research else ""

    prompt = f"""Eres el creador de contenido de IA más viral de habla hispana en YouTube.

NOTICIAS DEL DÍA:
{h_block}
{r_block}
Crea un guión de YouTube Short de 58-62 segundos (155-170 palabras).

ESTRUCTURA:
[0-5s]   GANCHO — para el scroll. Una fórmula:
  "Nadie te dijo que [verdad incómoda sobre IA]"
  "[N] de cada 10 personas [error que cometen con IA]"
  "La IA acaba de [hacer algo que cambia todo]"
[5-20s]  TENSIÓN — el problema real con un dato numérico.
[20-38s] EVIDENCIA — caso real, empresa, persona. Específico.
[38-50s] GIRO — el ángulo que nadie menciona.
[50-62s] CIERRE — consecuencia para el espectador + "Sígueme para más IA al Día."

REGLAS:
- Máximo 9 palabras por oración
- Voz humana: "yo lo vi", "me preocupa", "te juro que"
- Mínimo 2 datos numéricos (%, millones, días)
- Sin: "increíble", "revolucionario", "impresionante"
- Español latinoamericano natural

RESPONDE JSON sin markdown:
{{
  "titulo": "Título SEO keyword al inicio, max 52 chars, emoji al final",
  "descripcion": "2 oraciones con keyword. #Shorts #IA #InteligenciaArtificial #ChatGPT #Tecnologia #IaAlDia",
  "tags": ["ia 2026","inteligencia artificial noticias","chatgpt novedades","ia herramientas","ia al dia","shorts ia","tecnologia latina","ia trabajo","futuro ia","automatizacion","ia español","ia impacto"],
  "guion": "guión completo 155-170 palabras",
  "hook_texto": "primeras 6-8 palabras exactas"
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
        return json.loads(text), used_pro
    except:
        return _fallback_script(), False

def _fallback_script():
    return {
        "titulo": "IA 2026: lo que nadie te cuenta 🤖",
        "descripcion": "Todo sobre inteligencia artificial en 2026. #Shorts #IA #InteligenciaArtificial #IaAlDia",
        "tags": ["ia 2026","inteligencia artificial noticias","chatgpt novedades","ia herramientas","ia al dia","shorts ia","tecnologia latina","ia trabajo","futuro ia","automatizacion","ia español","ia impacto"],
        "guion": "Nadie te dijo esto sobre la inteligencia artificial. El 40% de los empleos actuales van a cambiar en los próximos 3 años según la ONU. Yo lo veo cada semana. Una empresa que conozco despidió 30 personas el mes pasado. Contrató un solo modelo de IA. Lo que nadie menciona es que aún puedes adaptarte. Pero sí es tarde para ignorarlo. La pregunta no es si te va a afectar. La pregunta es qué vas a hacer antes de que llegue. Sígueme para más IA al Día.",
        "hook_texto": "Nadie te dijo esto sobre la IA",
    }


# ── Paso 3: TTS — Gemini Charon (natural) con fallback Edge ──────────────────
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
        os.remove(rp)
        if ok and os.path.getsize(path) > 1000:
            print("      Voz: Gemini TTS Charon ✓"); return True
    except Exception as e:
        if "429" not in str(e) and "quota" not in str(e).lower():
            print(f"      Gemini TTS: {str(e)[:50]}")
    return False

async def _edge_tts_async(text, path):
    await edge_tts.Communicate(
        text, "es-CL-LorenzoNeural",
        rate="-8%", pitch="-3Hz", volume="+15%"
    ).save(path)

def generate_audio(text, path):
    if _gemini_tts(text, path): return True
    print("      Voz: Edge-TTS Lorenzo (fallback)")
    asyncio.run(_edge_tts_async(text, path))
    return False


# ── Paso 4: Presentador Pexels ────────────────────────────────────────────────
def get_presenter_video(tmp_dir, duration):
    headers = {"Authorization": PEXELS_API_KEY}
    queries = PRESENTER_QUERIES.copy()
    random.shuffle(queries)

    for query in queries:
        try:
            r = requests.get(
                "https://api.pexels.com/videos/search", headers=headers,
                params={"query": query, "orientation": "portrait",
                        "per_page": 15, "size": "medium"}, timeout=12
            )
            videos = r.json().get("videos", [])
            usable = [v for v in videos if v.get("duration", 0) >= 5]
            if not usable: continue

            video = random.choice(usable[:8])
            files = sorted(video["video_files"], key=lambda x: x.get("width", 0))
            portrait = [f for f in files if f.get("width", 999) <= f.get("height", 1)]
            chosen   = random.choice(portrait) if portrait else files[min(1, len(files)-1)]

            raw = os.path.join(tmp_dir, "presenter_raw.mp4")
            dl  = requests.get(chosen["link"], stream=True, timeout=45)
            with open(raw, "wb") as f:
                for chunk in dl.iter_content(8192): f.write(chunk)
            if os.path.getsize(raw) < 50000: continue

            # Escalar y recortar a 1080x1920
            scaled = os.path.join(tmp_dir, "presenter_scaled.mp4")
            subprocess.run([
                FFMPEG, "-y", "-i", raw,
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an",
                scaled
            ], capture_output=True)
            if not os.path.exists(scaled) or os.path.getsize(scaled) < 10000: continue

            # Loop hasta cubrir la duración
            looped = os.path.join(tmp_dir, "presenter_loop.mp4")
            subprocess.run([
                FFMPEG, "-y",
                "-stream_loop", "-1", "-i", scaled,
                "-t", str(duration + 1),
                "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an",
                looped
            ], capture_output=True)
            if os.path.exists(looped) and os.path.getsize(looped) > 10000:
                print(f"      Presentador: '{query}' ✓")
                return looped
        except: continue
    return None


# ── Paso 5: Whisper captions ──────────────────────────────────────────────────
def transcribe_whisper(audio_path):
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

def estimate_words(script, duration):
    words = script.split()
    tpw   = (duration - 1.0) / max(len(words), 1)
    return [{"word": w, "start": 0.5 + i*tpw, "end": 0.5 + (i+1)*tpw}
            for i, w in enumerate(words)]


# ── Paso 6: Música ambient ────────────────────────────────────────────────────
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


# ── Paso 7: Ensamblar ─────────────────────────────────────────────────────────
def assemble(presenter_vid, audio_path, music_path,
             words, hook_text, output_path, duration):

    def sf(t):
        for old, new in [("'",""),("\"",""),("\\",""),("%","pct"),(":",""),
                         ("¿",""),("¡",""),("\n"," "),
                         ("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n")]:
            t = t.replace(old, new)
        return t[:44]

    caps = []

    # Gradiente negro en zona captions (abajo)
    caps.append("drawbox=x=0:y=1560:w=1080:h=360:color=black@0.60:t=fill")

    # Hook grande centrado — primeros 4s
    if hook_text:
        h = sf(hook_text)
        caps.append(
            f"drawtext=fontfile='{FONT_BOLD}':text='{h}'"
            f":fontcolor=white:fontsize=88"
            f":x=(w-text_w)/2:y=(h/2)-80"
            f":shadowcolor=black@0.99:shadowx=5:shadowy=5"
            f":bordercolor=black:borderw=4"
            f":enable='between(t,0,4.0)'"
        )

    # Captions TikTok: una palabra a la vez, grande, abajo
    for wd in words:
        w = sf(wd["word"])
        if not w: continue
        caps.append(
            f"drawtext=fontfile='{FONT_BOLD}':text='{w}'"
            f":fontcolor=white:fontsize=112"
            f":x=(w-text_w)/2:y=h-310"
            f":shadowcolor=black@0.99:shadowx=6:shadowy=6"
            f":bordercolor=black:borderw=5"
            f":enable='between(t,{wd['start']:.2f},{wd['end']:.2f})'"
        )

    # Branding minimal arriba izquierda
    caps.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='IA al Dia'"
        f":fontcolor=white:fontsize=38:x=36:y=30"
        f":shadowcolor=black@0.9:shadowx=3:shadowy=3"
    )
    caps.append("drawbox=x=36:y=78:w=165:h=4:color=0x00DCFF:t=fill")

    vf = "eq=contrast=1.10:brightness=0.02:saturation=1.20,format=yuv420p," + ",".join(caps)

    has_music = music_path and os.path.exists(music_path)

    if has_music:
        fc = (
            f"[0:v]{vf}[vout];"
            f"[2:a]volume=0.07[music];"
            f"[1:a][music]amix=inputs=2:duration=first:weights=1 0.5[aout]"
        )
        cmd = [FFMPEG, "-y",
               "-i", presenter_vid, "-i", audio_path, "-i", music_path,
               "-t", str(duration),
               "-filter_complex", fc,
               "-map", "[vout]", "-map", "[aout]",
               "-c:v", "libx264", "-preset", "fast", "-crf", "19",
               "-c:a", "aac", "-b:a", "192k",
               "-shortest", "-movflags", "+faststart", output_path]
    else:
        cmd = [FFMPEG, "-y",
               "-i", presenter_vid, "-i", audio_path,
               "-t", str(duration),
               "-vf", vf,
               "-c:v", "libx264", "-preset", "fast", "-crf", "19",
               "-c:a", "aac", "-b:a", "192k",
               "-shortest", "-movflags", "+faststart", output_path]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg: {r.stderr[-400:]}")
    print("      Video ensamblado ✓")


# ── Miniatura ─────────────────────────────────────────────────────────────────
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


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*55}")
    print(f"  IA al Día v5.0 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Presentador Pexels + Gemini TTS + Captions TikTok")
    print(f"{'='*55}\n")

    used_tts = used_imagen = used_pro = False

    with tempfile.TemporaryDirectory() as tmp:
        audio_path  = os.path.join(tmp, "audio.mp3")
        music_path  = os.path.join(tmp, "ambient.aac")
        output_path = os.path.join(tmp, "short.mp4")
        thumb_path  = os.path.join(tmp, "thumbnail.png")

        print("[1/6] RSS + research...")
        headlines = get_headlines()
        topic     = headlines[0] if headlines else "inteligencia artificial 2026"
        research  = research_topic(topic)
        print(f"      {len(headlines)} titulares | research: {bool(research)}")

        print("[2/6] Script (Gemini 2.5 Pro)...")
        script, used_pro = generate_script(headlines, research)
        print(f"      Título: {script['titulo']}")

        print("[3/6] Voz (Gemini TTS Charon)...")
        used_tts = generate_audio(script["guion"], audio_path)
        duration  = MP3(audio_path).info.length + 0.5
        print(f"      Duración: {duration:.1f}s")

        print("[4/6] Presentador (Pexels portrait)...")
        presenter = get_presenter_video(tmp, duration)
        if not presenter:
            raise RuntimeError("No se pudo obtener video de Pexels.")

        print("[5/6] Captions (Whisper)...")
        words = transcribe_whisper(audio_path) or estimate_words(script["guion"], duration)

        print("[5/6] Música ambient...")
        has_music = make_ambient(duration, music_path)

        print("[5/6] Ensamblando...")
        assemble(presenter, audio_path,
                 music_path if has_music else "",
                 words, script.get("hook_texto", ""),
                 output_path, duration)

        print("[5/6] Miniatura...")
        used_imagen = create_thumbnail(script["titulo"], thumb_path)

        desc_final = (
            script["descripcion"] + AFFILIATES +
            "\n\n━━━━━━━━━━━━━━━━\n"
            "🤖 IA al Día — Inteligencia Artificial para LATAM, todos los días.\n"
            "⚠️ Contenido creado con asistencia de IA con fines educativos."
        )

        print("[6/6] Subiendo a YouTube...")
        yt       = get_youtube()
        video_id = upload_video(yt, output_path, script["titulo"], desc_final, script["tags"])
        upload_thumb(yt, video_id, thumb_path)

        credits   = update_credits(used_tts, used_imagen, used_pro)
        remaining = CREDIT_TOTAL - credits["spent"]

    print(f"\n  ✓ https://youtube.com/shorts/{video_id}")
    print(f"  ✓ {script['titulo']}")
    print(f"  ✓ ${remaining:.2f} de crédito restante\n")


if __name__ == "__main__":
    main()
