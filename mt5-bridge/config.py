"""
MT5 Bridge Configuration.

Loads from environment variables. For local development, create a `.env`
file in this directory (see `.env.example`) — it's loaded automatically
if python-dotenv is installed.
"""
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass(frozen=True)
class BridgeConfig:
    bridge_port: int = int(os.getenv("MT5_BRIDGE_PORT", "5000"))
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # MetaTrader5 terminal login. This bridge must run on the same Windows
    # machine as a terminal logged into this account — required for real
    # (non-simulated) execution.
    mt5_login: int = int(os.getenv("MT5_LOGIN", "0") or "0")
    mt5_password: str = os.getenv("MT5_PASSWORD", "")
    mt5_server: str = os.getenv("MT5_SERVER", "")
    # Optional: full path to terminal64.exe if MT5 isn't in its default location.
    mt5_terminal_path: str = os.getenv("MT5_TERMINAL_PATH", "")

    # Shared secret required on every request (except /health) once this
    # bridge is reachable from the internet (e.g. via a tunnel) — otherwise
    # anyone who finds the URL could read the account or place trades. Must
    # match MT5_BRIDGE_API_KEY on the main app.
    bridge_api_key: str = os.getenv("MT5_BRIDGE_API_KEY", "")

    # Hourly Telegram source-channel poll driven from this always-on bridge
    # (Vercel Hobby crons can't run sub-daily). When APP_BASE_URL is set, a
    # background thread calls <APP_BASE_URL>/api/telegram/poll-source every
    # APP_POLL_INTERVAL_MINUTES. CRON_SECRET, if set, is sent as a bearer token
    # and must match the app's CRON_SECRET.
    app_base_url: str = os.getenv("APP_BASE_URL", "").rstrip("/")
    app_poll_interval_minutes: int = int(os.getenv("APP_POLL_INTERVAL_MINUTES", "60") or "60")
    cron_secret: str = os.getenv("CRON_SECRET", "")


config = BridgeConfig()
