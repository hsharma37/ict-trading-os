"""
Telegram service — notification delivery, bot commands, and alert routing.
"""
import httpx
from app.config import settings


def send_telegram_message(message: str, chat_id: str | None = None) -> dict:
    """
    Send a message via the configured Telegram bot.
    """
    token = settings.telegram_bot_token
    target = chat_id or settings.telegram_chat_id

    if not token or not target:
        return {"error": "Telegram not configured"}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": target,
        "text": message,
        "parse_mode": "Markdown",
    }

    import httpx
    resp = httpx.post(url, json=payload, timeout=30)

    if resp.status_code == 200 and resp.json().get("ok"):
        return {"status": "sent", "chat_id": target}
    else:
        return {"error": f"Telegram API error: {resp.text}"}
