"""
Telegram Bot — IA al Día
Corre cada 10 min desde GitHub Actions (telegram_listener.yml).
Comandos:
  /short [tema]  → dispara publish_short.yml con el tema indicado
  /short         → dispara con detección automática de tema
  /help          → muestra comandos disponibles
"""

import os, time, requests

BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID    = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))
GH_TOKEN   = os.environ.get("GH_PAT", "")
GH_REPO    = os.environ.get("GH_REPO", "")

if not BOT_TOKEN or not CHAT_ID:
    print("TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados. Saliendo.")
    raise SystemExit(0)

BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send(text: str):
    try:
        requests.post(f"{BASE}/sendMessage", json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }, timeout=10)
    except Exception as e:
        print(f"Telegram send error: {e}")


def recent_messages(minutes: int = 12):
    """Devuelve mensajes del CHAT_ID autorizado en los últimos N minutos."""
    cutoff = time.time() - (minutes * 60)
    try:
        r = requests.get(f"{BASE}/getUpdates", params={"limit": 50, "timeout": 3}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"getUpdates error: {e}")
        return []

    return [
        u["message"]
        for u in r.json().get("result", [])
        if "message" in u
        and u["message"].get("date", 0) > cutoff
        and u["message"].get("chat", {}).get("id") == CHAT_ID
    ]


def trigger_short(topic: str = "") -> bool:
    """Dispara publish_short.yml vía GitHub API."""
    if not GH_TOKEN or not GH_REPO:
        print("GH_PAT o GH_REPO no configurados.")
        return False
    url = f"https://api.github.com/repos/{GH_REPO}/actions/workflows/publish_short.yml/dispatches"
    r = requests.post(url, json={
        "ref": "main",
        "inputs": {"tipo": "short", "viral_topic": topic},
    }, headers={
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }, timeout=10)
    print(f"GitHub dispatch → HTTP {r.status_code}")
    return r.status_code == 204


def main():
    messages = recent_messages(minutes=12)
    if not messages:
        print("Sin mensajes nuevos.")
        return

    for msg in messages:
        text = msg.get("text", "").strip()
        print(f"Mensaje recibido: {text!r}")

        lower = text.lower()

        if lower.startswith("/short"):
            topic = text[6:].strip()
            if trigger_short(topic):
                tema_txt = f"<b>{topic}</b>" if topic else "<i>(automático)</i>"
                send(
                    f"✅ <b>Short en camino!</b>\n"
                    f"Tema: {tema_txt}\n\n"
                    f"⏱ Listo en ~5 min. Te mando el link cuando se publique."
                )
            else:
                send(
                    "❌ No se pudo lanzar el workflow.\n"
                    "Revisa que el secret <b>GH_PAT</b> esté bien configurado."
                )

        elif lower in ("/help", "/ayuda", "/start"):
            send(
                "🤖 <b>IA al Día Bot</b>\n\n"
                "📹 /short [tema] — Publica un Short ahora\n"
                "   Ej: <code>/short Terremoto Colombia</code>\n"
                "   Ej: <code>/short</code> (tema automático)\n\n"
                "❓ /help — Esta ayuda\n\n"
                "<i>Tiempo de publicación: ~5 min</i>"
            )

        else:
            # Mensaje libre → tratarlo como tema de Short directo
            if len(text) > 3 and not text.startswith("/"):
                if trigger_short(text):
                    send(
                        f"✅ <b>Short en camino!</b>\n"
                        f"Tema: <b>{text}</b>\n\n"
                        f"⏱ Te mando el link en ~5 min."
                    )


if __name__ == "__main__":
    main()
