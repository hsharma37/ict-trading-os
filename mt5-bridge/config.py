"""
MT5 Bridge Configuration.

Loads from environment variables. For local development,
create a `.env` file in the mt5-bridge directory.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BridgeConfig:
    bridge_port: int = int(os.getenv("MT5_BRIDGE_PORT", "5000"))
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


config = BridgeConfig()
