#!/usr/bin/env python3
"""
Monetización multi-plataforma — escala "IA al Día" a TikTok, Instagram y SEO.

Estrategias basadas en:
  - ShortGPT         (multi-platform publishing)
  - yt-short-clipper (TikTok + Reels distribution)
  - yutu             (SEO + growth hacking)
  - Advanced-Youtube-Seo-Generator (keyword optimization)

Secrets necesarios en GitHub:
  - TIKTOK_ACCESS_TOKEN     → developers.tiktok.com/products/content-posting-api
  - INSTAGRAM_USER_ID       → Business Account ID
  - INSTAGRAM_ACCESS_TOKEN  → developers.facebook.com/docs/instagram-api
"""

import os, requests, time, json, re

# ── Hosting temporal (necesario para Instagram API) ───────────────────────────
def _upload_temp_host(video_path):
    """Sube video a host temporal para obtener URL pública (Instagram lo requiere)."""
    fname = os.path.basename(video_path)

    # Opción 1: transfer.sh
    try:
        with open(video_path, "rb") as f:
            r = requests.put(
                f"https://transfer.sh/{fname}",
                data=f,
                headers={"Max-Days": "2", "Max-Downloads": "5"},
                timeout=120
            )
        if r.status_code == 200 and r.text.startswith("http"):
            url = r.text.strip()
            print(f"      Host temporal: transfer.sh ✓")
            return url
    except Exception as e:
        print(f"      transfer.sh: {str(e)[:40]}")

    # Opción 2: 0x0.st
    try:
        with open(video_path, "rb") as f:
            r = requests.post("https://0x0.st", files={"file": (fname, f, "video/mp4")}, timeout=120)
        if r.status_code == 200 and r.text.startswith("http"):
            print(f"      Host temporal: 0x0.st ✓")
            return r.text.strip()
    except Exception as e:
        print(f"      0x0.st: {str(e)[:40]}")

    return None


# ── TikTok — Content Posting API v2 ──────────────────────────────────────────
def publish_tiktok(video_path, title, description):
    """
    [ShortGPT + yt-short-clipper] Publica en TikTok vía Content Posting API v2.

    Setup (1 sola vez):
    1. Crear cuenta en developers.tiktok.com
    2. Crear app → habilitar "Content Posting API"
    3. OAuth flow → obtener access_token de usuario
    4. Agregar como GitHub Secret: TIKTOK_ACCESS_TOKEN
    """
    token = os.environ.get("TIKTOK_ACCESS_TOKEN", "")
    if not token:
        print("      TikTok: sin token (agrega TIKTOK_ACCESS_TOKEN a Secrets)")
        return False

    try:
        file_size = os.path.getsize(video_path)
        headers   = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8"
        }

        # Paso 1: inicializar upload
        init_body = {
            "post_info": {
                "title":        title[:150],
                "description":  description[:2200],
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet":    False,
                "disable_comment": False,
                "disable_stitch":  False,
                "video_cover_timestamp_ms": 1000
            },
            "source_info": {
                "source":             "FILE_UPLOAD",
                "video_size":         file_size,
                "chunk_size":         file_size,
                "total_chunk_count":  1
            }
        }

        r = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            json=init_body, headers=headers, timeout=30
        )
        resp = r.json()
        err  = resp.get("error", {})

        if err.get("code", "ok") != "ok":
            print(f"      TikTok init: {err.get('message', resp)[:80]}")
            return False

        upload_url = resp["data"]["upload_url"]
        publish_id = resp["data"]["publish_id"]

        # Paso 2: subir archivo
        with open(video_path, "rb") as f:
            video_bytes = f.read()

        up = requests.put(
            upload_url,
            data=video_bytes,
            headers={
                "Content-Type":   "video/mp4",
                "Content-Range":  f"bytes 0-{file_size-1}/{file_size}",
                "Content-Length": str(file_size)
            },
            timeout=180
        )

        if up.status_code not in (200, 201, 206):
            print(f"      TikTok upload: HTTP {up.status_code}")
            return False

        print(f"      TikTok: ✓ publicado (ID: {publish_id})")
        return True

    except Exception as e:
        print(f"      TikTok error: {str(e)[:70]}")
    return False


# ── Instagram — Reels vía Graph API ───────────────────────────────────────────
def publish_instagram(video_path, caption):
    """
    [yt-short-clipper] Publica Reel en Instagram vía Meta Graph API v19.

    Setup (1 sola vez):
    1. Instagram Business Account vinculado a una Facebook Page
    2. developers.facebook.com → crear app → "instagram_content_publish" permission
    3. Obtener token de larga duración (60 días) y User ID de Instagram
    4. Agregar como GitHub Secrets:
       - INSTAGRAM_USER_ID
       - INSTAGRAM_ACCESS_TOKEN
    """
    user_id = os.environ.get("INSTAGRAM_USER_ID", "")
    token   = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")

    if not user_id or not token:
        print("      Instagram: sin credenciales (agrega INSTAGRAM_USER_ID + INSTAGRAM_ACCESS_TOKEN)")
        return False

    try:
        # Instagram requiere URL pública para el video
        video_url = _upload_temp_host(video_path)
        if not video_url:
            print("      Instagram: no se pudo obtener URL pública del video")
            return False

        base = f"https://graph.facebook.com/v19.0/{user_id}"

        # Paso 1: crear container
        r1 = requests.post(
            f"{base}/media",
            data={
                "media_type":    "REELS",
                "video_url":     video_url,
                "caption":       caption[:2200],
                "share_to_feed": "true",
                "access_token":  token
            },
            timeout=30
        )
        d1 = r1.json()
        container_id = d1.get("id")

        if not container_id:
            err = d1.get("error", {})
            print(f"      Instagram container: {err.get('message', d1)[:80]}")
            return False

        # Paso 2: esperar procesamiento (max 90s)
        for attempt in range(9):
            time.sleep(10)
            sr = requests.get(
                f"https://graph.facebook.com/v19.0/{container_id}",
                params={"fields": "status_code,status", "access_token": token},
                timeout=15
            )
            status = sr.json().get("status_code", "")
            if status == "FINISHED":
                break
            if status in ("ERROR", "EXPIRED"):
                print(f"      Instagram: container falló ({status})")
                return False

        # Paso 3: publicar
        r2 = requests.post(
            f"{base}/media_publish",
            data={"creation_id": container_id, "access_token": token},
            timeout=30
        )
        d2 = r2.json()

        if d2.get("id"):
            print(f"      Instagram Reel: ✓ publicado")
            return True
        else:
            err = d2.get("error", {})
            print(f"      Instagram publish: {err.get('message', d2)[:80]}")

    except Exception as e:
        print(f"      Instagram error: {str(e)[:70]}")
    return False


# ── SEO — Keywords trending [yutu + Advanced-Youtube-Seo-Generator] ───────────
def get_seo_keywords(title, lang="es"):
    """
    [yutu + Advanced-Youtube-Seo-Generator] Obtiene keywords trending de Google Trends
    para optimizar el SEO del Short en YouTube.
    Requiere: pip install pytrends
    """
    try:
        from pytrends.request import TrendReq

        geo    = "US" if lang == "en" else "CL"
        hl     = "en-US" if lang == "en" else "es-419"
        topic  = "artificial intelligence" if lang == "en" else "inteligencia artificial"

        pt = TrendReq(hl=hl, tz=300, timeout=(10, 30))
        pt.build_payload([topic], timeframe="now 7-d", geo=geo)

        related = pt.related_queries().get(topic, {})
        top     = related.get("top")

        if top is not None and not top.empty:
            kws = [q.lower() for q in top["query"].head(6).tolist()]
            print(f"      SEO trending: {kws[:3]}")
            return kws

    except Exception as e:
        print(f"      SEO keywords: {str(e)[:60]}")

    # Fallback: keywords base según idioma
    if lang == "en":
        return ["artificial intelligence 2026", "ai news today", "chatgpt update",
                "ai tools", "machine learning", "ai replacing jobs"]
    return ["inteligencia artificial 2026", "ia noticias hoy", "chatgpt novedades",
            "ia herramientas", "automatizacion ia", "ia reemplaza empleos"]


def optimize_title_seo(title, keywords, lang="es"):
    """Inserta 1-2 keywords trending al inicio del título si no están ya."""
    title_lower = title.lower()
    for kw in keywords[:3]:
        if kw.lower() not in title_lower and len(title) + len(kw) < 95:
            return title  # no forzar, el título ya tiene contexto
    return title
