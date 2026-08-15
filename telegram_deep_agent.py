"""
Deep Agent — IA al Día
Recibe instrucciones detalladas de Telegram y ejecuta el pipeline completo:
  1. Gemini investiga el tema con Google Search
  2. Descarga imágenes reales de artículos de noticias
  3. Construye slideshow Ken Burns con ffmpeg
  4. Redacta guion periodístico profesional
  5. Publica el Short y notifica el link por Telegram
"""

import os, sys, re, json, time, subprocess, requests
from pathlib import Path
from google import genai
from google.genai import types as gt

# ─── Config ───────────────────────────────────────────────────────────────────
PIPELINE  = Path(__file__).parent / "generate_short.py"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))
BASE_TG   = f"https://api.telegram.org/bot{BOT_TOKEN}"

def tg(text):
    if not BOT_TOKEN or not CHAT_ID:
        print(f"[TG] {text}")
        return
    try:
        requests.post(f"{BASE_TG}/sendMessage", json={
            "chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"TG error: {e}")

def bash(cmd, timeout=180):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    out = (r.stdout + r.stderr)
    if out:
        print(out[:2000])
    return out

# ─── Fase 1: Investigación con Gemini + Google Search ─────────────────────────
def research(instruction):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    prompt = f"""
Eres un periodista investigador. El usuario pide: {instruction}

TAREA:
1. Investiga el tema usando fuentes verificadas y actualizadas de noticias.
2. Recopila datos precisos: cifras, fechas, nombres, lugares.
3. Identifica 4-6 artículos de noticias en español que tengan imágenes del tema
   (preferir: infobae.com, elespectador.com, cooperativa.cl, elmundo.es, cnn.com/es, univision.com, elpais.com).
4. Redacta un guion periodístico profesional de exactamente 300-340 palabras.
   - Tono directo, contundente, sin filtros (estilo "provocador").
   - Empieza fuerte con el hecho más impactante, sin saludos ni presentaciones.
   - Incluye cifras reales, nombres concretos, contexto.
   - Cierra con una pregunta o reflexión que genere comentarios.

Responde ÚNICAMENTE con este JSON (sin bloques de código, sin markdown):
{{
  "titulo": "Título corto para YouTube con palabras clave de búsqueda local (máx 70 chars)",
  "guion": "Guion completo aquí... (300-340 palabras)",
  "articulos": ["url_articulo_1", "url_articulo_2", "url_articulo_3", "url_articulo_4"],
  "resumen": "Resumen del tema en 2 líneas"
}}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=gt.GenerateContentConfig(
            tools=[gt.Tool(google_search=gt.GoogleSearch())]
        )
    )
    raw = response.text.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    return json.loads(raw)


# ─── Fase 2: Extraer imágenes de artículos ────────────────────────────────────
def extract_images_from_article(url, out_dir, prefix, max_imgs=3):
    """Fetch article HTML, extract image URLs with auth tokens, download them."""
    try:
        r = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Referer": url,
        }, timeout=15)
        html = r.text[:60000]
    except Exception as e:
        print(f"  Fetch error {url}: {e}")
        return []

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = f"""Del siguiente HTML de un artículo de noticias, extrae las URLs COMPLETAS
de imágenes de contenido (no logos, no iconos, no avatares).
Incluye los parámetros ?auth= exactamente como aparecen en el HTML.
Prioriza imágenes grandes (width >= 600px si se menciona).
Devuelve solo las URLs, una por línea, máximo {max_imgs}.

HTML (primeros 50000 chars):
{html[:50000]}"""

    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        img_urls = [u.strip() for u in resp.text.strip().splitlines()
                    if u.strip().startswith("http") and any(
                        ext in u.lower() for ext in [".jpg", ".jpeg", ".png", ".webp", ".jfif"]
                    )]
    except Exception as e:
        print(f"  Gemini extract error: {e}")
        return []

    downloaded = []
    for i, img_url in enumerate(img_urls[:max_imgs]):
        # Request higher resolution
        img_url_hires = re.sub(r'width=\d+', 'width=1200', img_url)
        img_url_hires = re.sub(r'height=\d+', 'height=800', img_url_hires)
        out = f"{out_dir}/{prefix}_{i}.jpg"
        code = bash(
            f'curl -s -o "{out}" -w "%{{http_code}}" --max-time 20 '
            f'-H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" '
            f'-H "Referer: {url}" '
            f'"{img_url_hires}"'
        )
        if "200" in code:
            try:
                size = Path(out).stat().st_size
                if size > 15000:
                    print(f"  ✓ {Path(out).name}: {size//1024}KB")
                    downloaded.append(out)
                else:
                    print(f"  ✗ {Path(out).name}: muy pequeña ({size}B)")
                    Path(out).unlink(missing_ok=True)
            except Exception:
                pass
        else:
            print(f"  ✗ HTTP {code.strip()} para {img_url[:60]}")
    return downloaded


# ─── Fase 3: Ken Burns slideshow ──────────────────────────────────────────────
def build_slideshow(images, output="/tmp/deep_slideshow.mp4"):
    if not images:
        return None

    seg_dir = Path("/tmp/deep_segments")
    bash(f"rm -rf {seg_dir} && mkdir -p {seg_dir}")

    segments = []
    for i, img in enumerate(images[:12]):
        out = str(seg_dir / f"seg_{i:02d}.mp4")
        pan = 1 if i % 2 == 0 else -1
        pan_expr = f"max(0, min(iw-ow, (iw-1080)/2 + {pan}*(iw-1080)/3 * sin(t/4)))"
        result = bash(
            f'ffmpeg -y -loop 1 -t 8 -i "{img}" '
            f'-vf "scale=-1:1920,crop=1080:1920:\'{pan_expr}\':0,setsar=1" '
            f'-c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p -an "{out}" 2>&1'
        )
        p = Path(out)
        if p.exists() and p.stat().st_size > 5000:
            segments.append(out)
            print(f"  ✓ seg_{i:02d}: {p.stat().st_size//1024}KB")
        else:
            print(f"  ✗ seg_{i:02d} falló")

    if not segments:
        return None

    concat_f = "/tmp/deep_concat.txt"
    Path(concat_f).write_text("\n".join(f"file '{s}'" for s in segments))
    bash(f'ffmpeg -y -f concat -safe 0 -i "{concat_f}" '
         f'-c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p "{output}"')

    if Path(output).exists():
        dur = float(bash(
            f'ffprobe -v quiet -show_entries format=duration -of csv=p=0 "{output}"'
        ).strip() or 0)
        print(f"  ✓ Slideshow: {Path(output).stat().st_size//1024}KB | {dur:.1f}s")
        return output
    return None


# ─── Fase 4: Publicar ─────────────────────────────────────────────────────────
def publish(guion, titulo, slideshow_path):
    env = {
        **os.environ,
        "MAX_GUION_WORDS": "500",
        "LANG_CODE": "es",
        "FORCE_PERSONA": "provocador",
        "VIRAL_GUION": guion,
        "VIRAL_TOPIC": titulo,
    }
    if slideshow_path and Path(slideshow_path).exists():
        env["PRESENTER_VIDEO_PATH"] = slideshow_path

    r = subprocess.run(
        [sys.executable, "-W", "ignore", str(PIPELINE)],
        env=env, capture_output=True, text=True, timeout=600,
        cwd=str(PIPELINE.parent)
    )
    output = r.stdout + r.stderr
    print(output[-3000:])

    urls = re.findall(r'https://youtube\.com/shorts/[a-zA-Z0-9_-]+', output)
    return urls[-1] if urls else None


# ─── Orquestador principal ────────────────────────────────────────────────────
def run(instruction):
    tg(f"🔍 <b>Investigando...</b>\n<i>{instruction[:120]}</i>")

    # 1. Research
    print("\n=== FASE 1: Investigación ===")
    try:
        data = research(instruction)
    except Exception as e:
        tg(f"❌ Error en investigación: {e}")
        raise

    guion  = data["guion"]
    titulo = data["titulo"]
    articulos = data.get("articulos", [])
    print(f"Título: {titulo}")
    print(f"Guion: {len(guion.split())} palabras")
    print(f"Artículos: {len(articulos)}")

    tg(f"📰 Investigación lista.\nTema: <b>{titulo}</b>\nBuscando imágenes en {len(articulos)} fuentes...")

    # 2. Download images
    print("\n=== FASE 2: Imágenes ===")
    img_dir = "/tmp/deep_imgs"
    bash(f"rm -rf {img_dir} && mkdir -p {img_dir}")

    all_images = []
    for i, url in enumerate(articulos[:5]):
        print(f"  Artículo {i+1}: {url[:80]}")
        imgs = extract_images_from_article(url, img_dir, f"src{i}", max_imgs=3)
        all_images.extend(imgs)
        if len(all_images) >= 10:
            break

    print(f"Total imágenes: {len(all_images)}")
    tg(f"🖼️ {len(all_images)} imágenes conseguidas. Construyendo video...")

    # 3. Slideshow
    print("\n=== FASE 3: Slideshow ===")
    slideshow = build_slideshow(all_images) if all_images else None
    if not slideshow:
        tg("⚠️ Sin imágenes — publicando con video automático de Pexels.")

    # 4. Publish
    print("\n=== FASE 4: Publicando ===")
    tg("🎬 Publicando Short...")
    yt_url = publish(guion, titulo, slideshow)

    if yt_url:
        tg(f"✅ <b>Short publicado!</b>\n\n📺 <b>{titulo}</b>\n\n{yt_url}")
        print(f"\n✓ URL: {yt_url}")
    else:
        tg("⚠️ Publicado pero no se encontró el URL. Revisa YouTube Studio.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 telegram_deep_agent.py 'instrucción del usuario'")
        sys.exit(1)
    instruction = " ".join(sys.argv[1:])
    print(f"Instrucción: {instruction}")
    run(instruction)
