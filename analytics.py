#!/usr/bin/env python3
"""
Analytics — IA al Día [youtube-mcp-server inspired]
Lee YouTube Analytics API y genera reporte de crecimiento.
Corre cada domingo via GitHub Actions (analytics.yml).

Métricas: vistas, watch time, subs ganados, retención, top 10 videos.
"""

import os, json
from pathlib import Path
from datetime import date, timedelta
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BASE_DIR       = Path(__file__).parent
TOKEN_FILE     = BASE_DIR / "token.json"
CLIENT_SECRETS = BASE_DIR / "client_secrets.json"
SCOPES         = [
    "https://www.googleapis.com/auth/youtube",
    ]

def get_creds():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds

def get_channel_id(yt):
    r = yt.channels().list(part="id,statistics,snippet", mine=True).execute()
    items = r.get("items", [])
    if not items: return None, None
    ch = items[0]
    return ch["id"], ch

def get_analytics(channel_id, days=30):
    """Obtiene métricas de los últimos N días via YouTube Analytics API."""
    creds  = get_creds()
    ya     = build("youtubeAnalytics", "v2", credentials=creds)
    end    = date.today()
    start  = end - timedelta(days=days)

    # Métricas globales
    r = ya.reports().query(
        ids         = f"channel=={channel_id}",
        startDate   = str(start),
        endDate     = str(end),
        metrics     = "views,estimatedMinutesWatched,subscribersGained,subscribersLost,likes,comments,shares",
        dimensions  = "day",
        sort        = "day"
    ).execute()

    totals = {"views": 0, "watchMinutes": 0, "subsGained": 0, "subsLost": 0,
              "likes": 0, "comments": 0, "shares": 0}
    rows = r.get("rows", [])
    for row in rows:
        totals["views"]       += row[1]
        totals["watchMinutes"]+= row[2]
        totals["subsGained"]  += row[3]
        totals["subsLost"]    += row[4]
        totals["likes"]       += row[5]
        totals["comments"]    += row[6]
        totals["shares"]      += row[7]

    return totals, rows

def get_top_videos(channel_id, days=30):
    """Top 10 videos por vistas en el período."""
    creds  = get_creds()
    ya     = build("youtubeAnalytics", "v2", credentials=creds)
    end    = date.today()
    start  = end - timedelta(days=days)

    r = ya.reports().query(
        ids        = f"channel=={channel_id}",
        startDate  = str(start),
        endDate    = str(end),
        metrics    = "views,estimatedMinutesWatched,subscribersGained,likes",
        dimensions = "video",
        sort       = "-views",
        maxResults = 10
    ).execute()

    return r.get("rows", [])

def get_video_titles(yt, video_ids):
    """Obtiene títulos de videos por ID."""
    if not video_ids: return {}
    r = yt.videos().list(
        part="snippet",
        id=",".join(video_ids[:50])
    ).execute()
    return {item["id"]: item["snippet"]["title"] for item in r.get("items", [])}

def main():
    print("\n" + "="*60)
    print("  IA al Día — Reporte Analytics")
    print(f"  {date.today().strftime('%Y-%m-%d')}")
    print("="*60 + "\n")

    creds = get_creds()
    if not creds:
        print("  ✗ No hay credenciales. Ejecuta primero generate_short.py")
        return

    yt = build("youtube", "v3", credentials=creds)
    channel_id, channel_data = get_channel_id(yt)

    if not channel_id:
        print("  ✗ No se encontró el canal")
        return

    stats   = channel_data.get("statistics", {})
    snippet = channel_data.get("snippet", {})

    total_subs  = int(stats.get("subscriberCount", 0))
    total_views = int(stats.get("viewCount", 0))
    total_vids  = int(stats.get("videoCount", 0))

    print(f"  Canal: {snippet.get('title', 'IA al Día')}")
    print(f"  Suscriptores totales: {total_subs:,}")
    print(f"  Vistas totales:       {total_views:,}")
    print(f"  Videos publicados:    {total_vids}\n")

    # Cuánto falta para monetización
    subs_needed  = max(0, 1000 - total_subs)
    views_needed = max(0, 10_000_000 - total_views)

    print("  ── Meta de Monetización YouTube Shorts ──")
    print(f"  Suscriptores: {total_subs:,} / 1,000 {'✓' if total_subs >= 1000 else f'(faltan {subs_needed:,})'}")
    print(f"  Vistas Shorts: {total_views:,} / 10,000,000 {'✓' if total_views >= 10_000_000 else f'(faltan {views_needed:,})'}")

    if total_subs >= 1000 and total_views >= 10_000_000:
        print("  🎉 LISTO PARA MONETIZAR — aplica en YouTube Studio")
    print()

    # Métricas últimos 30 días
    try:
        totals, daily_rows = get_analytics(channel_id, days=30)

        wh = totals["watchMinutes"] / 60
        net_subs = totals["subsGained"] - totals["subsLost"]

        print("  ── Últimos 30 días ──")
        print(f"  Vistas:          {totals['views']:,}")
        print(f"  Watch time:      {wh:.1f} horas")
        print(f"  Subs ganados:    +{totals['subsGained']:,}")
        print(f"  Subs perdidos:   -{totals['subsLost']:,}")
        print(f"  Subs netos:      {'+' if net_subs >= 0 else ''}{net_subs:,}")
        print(f"  Likes:           {totals['likes']:,}")
        print(f"  Comentarios:     {totals['comments']:,}")
        print(f"  Compartidos:     {totals['shares']:,}")

        # Proyección
        if len(daily_rows) >= 7:
            last_7 = daily_rows[-7:]
            avg_daily_views = sum(r[1] for r in last_7) / 7
            avg_daily_subs  = sum(r[3] - r[4] for r in last_7) / 7
            days_to_subs    = (subs_needed / avg_daily_subs) if avg_daily_subs > 0 and subs_needed > 0 else 0
            days_to_views   = (views_needed / avg_daily_views) if avg_daily_views > 0 and views_needed > 0 else 0

            print(f"\n  ── Proyección (ritmo actual) ──")
            print(f"  Vistas/día (últ. 7d):  {avg_daily_views:,.0f}")
            print(f"  Subs/día   (últ. 7d):  {avg_daily_subs:+.1f}")
            if days_to_subs > 0:
                print(f"  Días para 1,000 subs:  {days_to_subs:.0f} días")
            if days_to_views > 0:
                print(f"  Días para 10M vistas:  {days_to_views:.0f} días")

    except Exception as e:
        print(f"  ! Analytics API: {str(e)[:80]}")
        print("  (Activa YouTube Analytics API en console.cloud.google.com)")

    # Top 10 videos
    try:
        top_rows = get_top_videos(channel_id, days=30)
        if top_rows:
            video_ids = [r[0] for r in top_rows]
            titles    = get_video_titles(yt, video_ids)

            print(f"\n  ── Top 10 Videos (últimos 30 días) ──")
            for i, row in enumerate(top_rows, 1):
                vid_id = row[0]
                views  = int(row[1])
                subs   = int(row[3])
                title  = titles.get(vid_id, vid_id)[:48]
                print(f"  {i:2}. {views:6,} views  +{subs} subs  │ {title}")

    except Exception as e:
        print(f"  ! Top videos: {str(e)[:80]}")

    # Escribir a GitHub Step Summary si está en Actions
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        try:
            with open(summary_path, "a") as f:
                f.write(f"\n## 📊 IA al Día Analytics — {date.today()}\n\n")
                f.write(f"| Métrica | Valor |\n|---------|-------|\n")
                f.write(f"| Suscriptores | {total_subs:,} / 1,000 |\n")
                f.write(f"| Vistas totales | {total_views:,} |\n")
                f.write(f"| Videos publicados | {total_vids} |\n")
                if 'totals' in dir():
                    f.write(f"| Vistas (30d) | {totals['views']:,} |\n")
                    f.write(f"| Subs netos (30d) | {net_subs:+,} |\n")
                f.write(f"\n{'✅ **LISTO PARA MONETIZAR**' if total_subs >= 1000 and total_views >= 10_000_000 else f'⏳ Faltan {subs_needed:,} subs y {views_needed:,} vistas para monetizar'}\n")
            print("\n  Reporte escrito en GitHub Step Summary ✓")
        except Exception as e:
            print(f"  ! Summary: {str(e)[:50]}")

    print()

if __name__ == "__main__":
    main()
