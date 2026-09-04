"""
cTrader Bridge Configuration.

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
    bridge_port: int = int(os.getenv("CTRADER_BRIDGE_PORT", os.getenv("MT5_BRIDGE_PORT", "5000")))
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Transport: "openapi" (protobuf, needs client id/secret/access token)
    # or "fix" (FIX 4.4 sessions, needs only the account's FIX password).
    ct_transport: str = os.getenv("CT_TRANSPORT", "fix").lower()

    # cTrader Open API credentials (only used when CT_TRANSPORT=openapi).
    ct_client_id: str = os.getenv("CT_CLIENT_ID", "")
    ct_client_secret: str = os.getenv("CT_CLIENT_SECRET", "")
    ct_access_token: str = os.getenv("CT_ACCESS_TOKEN", "")
    ct_account_id: int = int(os.getenv("CT_ACCOUNT_ID", "0") or "0")
    # "demo" or "live" — picks Spotware's protobuf host.
    ct_host_type: str = os.getenv("CT_HOST_TYPE", "demo").lower()

    # FIX 4.4 connection (only used when CT_TRANSPORT=fix). Values come from
    # the broker's cTrader FIX credentials sheet.
    ct_fix_host: str = os.getenv("CT_FIX_HOST", "")
    ct_fix_ssl_port: int = int(os.getenv("CT_FIX_SSL_PORT", "5211") or "5211")
    ct_fix_plain_port: int = int(os.getenv("CT_FIX_PLAIN_PORT", "5201") or "5201")
    ct_fix_use_ssl: bool = os.getenv("CT_FIX_USE_SSL", "1").lower() not in ("0", "false", "no")
    ct_fix_sender_comp_id: str = os.getenv("CT_FIX_SENDER_COMP_ID", "")
    ct_fix_password: str = os.getenv("CT_FIX_PASSWORD", "")

    # Shared secret required on every request (except /health) once this
    # bridge is reachable from the internet. Must match MT5_BRIDGE_API_KEY
    # on the main app (the env var name is shared across bridge providers so
    # the app needs no provider-specific secrets plumbing).
    bridge_api_key: str = os.getenv("MT5_BRIDGE_API_KEY", "")

    # Hourly Telegram source-channel poll + planner run-due driven from this
    # always-on bridge (same generic sidecar duties as the MT5 bridge).
    app_base_url: str = os.getenv("APP_BASE_URL", "").rstrip("/")
    app_poll_interval_minutes: int = int(os.getenv("APP_POLL_INTERVAL_MINUTES", "60") or "60")
    cron_secret: str = os.getenv("CRON_SECRET", "")


config = BridgeConfig()
