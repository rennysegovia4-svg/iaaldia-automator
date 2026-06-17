#!/usr/bin/env python3
"""
Configura el canal de YouTube: nombre, descripción y banner.
"""

import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE_DIR    = Path(__file__).parent
CLIENT_FILE = BASE_DIR / "client_secrets.json"
TOKEN_FILE  = BASE_DIR / "token_canal.json"
LOGO_FILE   = BASE_DIR / "logo_iaaldia.png"
BANNER_FILE = BASE_DIR / "banner_iaaldia.png"

SCOPES = ["https://www.googleapis.com/auth/youtube"]

CHANNEL_NAME = "IA al Día"
DESCRIPTION = """🤖 Todo sobre Inteligencia Artificial en menos de 60 segundos.

Herramientas de IA, trucos de ChatGPT, tendencias tecnológicas y todo lo que necesitas saber para no quedarte atrás en la era digital.

📲 Nuevo Short cada día
💡 Contenido en español para toda Latinoamérica

#IA #InteligenciaArtificial #ChatGPT #Tecnología #Shorts"""


def get_youtube():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def get_channel_id(yt):
    r = yt.channels().list(part="id", mine=True).execute()
    return r["items"][0]["id"]


def update_nombre_descripcion(yt, channel_id):
    print("[1/3] Actualizando nombre y descripción...")
    yt.channels().update(
        part="brandingSettings",
        body={
            "id": channel_id,
            "brandingSettings": {
                "channel": {
                    "title": CHANNEL_NAME,
                    "description": DESCRIPTION,
                    "country": "CL",
                    "keywords": "inteligencia artificial ia chatgpt tecnologia shorts latam",
                }
            }
        }
    ).execute()
    print(f"      Nombre: {CHANNEL_NAME} ✓")


def upload_banner(yt):
    print("[2/3] Subiendo banner (2560x1440)...")
    media = MediaFileUpload(str(BANNER_FILE), mimetype="image/png", resumable=True)
    response = yt.channelBanners().insert(media_body=media).execute()
    banner_url = response["url"]
    print(f"      Banner subido ✓")
    return banner_url


def set_banner(yt, channel_id, banner_url):
    yt.channels().update(
        part="brandingSettings",
        body={
            "id": channel_id,
            "brandingSettings": {
                "channel": {
                    "title": CHANNEL_NAME,
                    "description": DESCRIPTION,
                    "country": "CL",
                    "keywords": "inteligencia artificial ia chatgpt tecnologia shorts latam",
                },
                "image": {"bannerExternalUrl": banner_url}
            }
        }
    ).execute()
    print("      Banner aplicado al canal ✓")


def main():
    print("\n" + "="*50)
    print("  Setup Canal: IA al Día")
    print("="*50 + "\n")

    yt = get_youtube()
    channel_id = get_channel_id(yt)
    print(f"  Canal ID: {channel_id}\n")

    update_nombre_descripcion(yt, channel_id)
    banner_url = upload_banner(yt)
    set_banner(yt, channel_id, banner_url)

    print("\n[3/3] Listo. Pendiente manual (2 min en YouTube Studio):")
    print("  → Foto de perfil: sube logo_iaaldia.png")
    print("  → Handle: cambia a @iaaldia")
    print("\n  Abre: https://studio.youtube.com/channel/" + channel_id + "/editing/images\n")


if __name__ == "__main__":
    main()
