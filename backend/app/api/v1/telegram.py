from fastapi import APIRouter, HTTPException
import httpx
from typing import Optional

from app.config import settings

router = APIRouter()


@router.post("/send", summary="Send a Telegram message")
async def send_message(message: str, chat_id: Optional[str] = None):
    """
    Send a text message via the configured Telegram bot.
    """
    token = settings.telegram_bot_token
    target_chat_id = chat_id or settings.telegram_chat_id

    if not token or not target_chat_id:
        raise HTTPException(status_code=400, detail="Telegram not configured")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": target_chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, timeout=30)

    if resp.status_code != 200 or not resp.json().get("ok"):
        raise HTTPException(
            status_code=500,
            detail=f"Telegram API error: {resp.text}",
        )

    return {"status": "sent", "chat_id": target_chat_id}


@router.post("/test", summary="Test Telegram connection")
async def test_telegram():
    """
    Send a test message to verify Telegram connectivity.
    """
    return await send_message("🧪 ICT Trading OS — Test message from backend")


@router.get("/status", summary="Telegram configuration status")
async def telegram_status():
    return {
        "configured": bool(settings.telegram_bot_token and settings.telegram_chat_id),
        "bot_token_set": bool(settings.telegram_bot_token),
        "chat_id_set": bool(settings.telegram_chat_id),
    }
