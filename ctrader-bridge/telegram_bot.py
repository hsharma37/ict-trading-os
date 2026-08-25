"""
Telegram notification handler for the cTrader Bridge.

Provides message sending with retry logic and structured logging.
"""
import logging
import requests
import time
from typing import Optional

from config import config

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or config.telegram_bot_token
        self.chat_id = chat_id or config.telegram_chat_id
        self._configured = bool(self.token and self.chat_id)

    def is_configured(self) -> bool:
        return self._configured

    def send(self, message: str, max_retries: int = 3, retry_delay: float = 2.0) -> dict:
        """
        Send a Telegram message with retry logic.
        """
        if not self._configured:
            logger.warning("Telegram not configured. Skipping notification.")
            return {"status": "skipped", "reason": "not_configured"}

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }

        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(url, json=payload, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                if data.get("ok"):
                    logger.info("Telegram message sent successfully")
                    return {"status": "sent", "message_id": data.get("result", {}).get("message_id")}
                else:
                    logger.warning(f"Telegram API error: {data.get('description')}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Telegram send attempt {attempt} failed: {e}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    logger.error(f"All {max_retries} Telegram send attempts failed")
                    return {"status": "error", "error": str(e)}

        return {"status": "error", "error": "max_retries_exceeded"}

    def send_trade_notification(self, symbol: str, direction: str, lot_size: float, entry_price: float, sl: float, tp: float) -> dict:
        """
        Send a formatted trade execution notification.
        """
        message = (
            f"📊 *Trade Executed*\n\n"
            f"*Symbol:* {symbol}\n"
            f"*Direction:* {direction.upper()}\n"
            f"*Lot Size:* {lot_size}\n"
            f"*Entry:* {entry_price}\n"
            f"*SL:* {sl}\n"
            f"*TP:* {tp}\n"
        )
        return self.send(message)

    def send_trade_close_notification(self, symbol: str, pnl: float, pnl_pips: float) -> dict:
        """
        Send a formatted trade close notification.
        """
        emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
        message = (
            f"{emoji} *Trade Closed*\n\n"
            f"*Symbol:* {symbol}\n"
            f"*PnL:* ${pnl:.2f} ({pnl_pips:.1f} pips)\n"
        )
        return self.send(message)

    def test(self) -> dict:
        """
        Send a test message to verify connectivity.
        """
        return self.send("🧪 cTrader Bridge — Test notification from ICT Trading OS")
