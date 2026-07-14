"""Settings Router — User preferences and app configuration."""
import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.core.database import db
from app.core.config import settings as app_settings
from app.services.bridge_config import (
    get_bridge_url,
    get_bridge_api_key,
    set_bridge_url,
    _normalize,
)

router = APIRouter(prefix="/settings", tags=["Settings"])

class SettingsUpdate(BaseModel):
    theme: Optional[str] = None
    default_symbol: Optional[str] = None
    risk_pct: Optional[float] = None
    account_balance: Optional[float] = None
    auto_trade: Optional[bool] = None
    notifications: Optional[bool] = None
    layout: Optional[str] = None


class BridgeUrlUpdate(BaseModel):
    url: str = ""


def _bridge_config() -> dict:
    """Current effective bridge URL and where it came from."""
    override = _normalize((db.find_one("settings", "global") or {}).get("mt5_bridge_url") or "")
    env_url = _normalize(app_settings.MT5_BRIDGE_URL)
    effective = get_bridge_url(force_refresh=True)
    return {
        "mt5_bridge_url": effective,
        "mt5_bridge_url_override": override,
        "mt5_bridge_env_url": env_url,
        "mt5_bridge_url_source": "override" if override else "env",
    }


@router.get("")
def get_settings():
    """Get current user settings."""
    settings = db.find_one("settings", "global")
    base = {
        "id": "global",
        "theme": "dark",
        "default_symbol": "EURUSD",
        "risk_pct": 1.0,
        "account_balance": 10000.0,
        "auto_trade": False,
        "notifications": True,
        "layout": "default",
    }
    if settings:
        base = settings
    return {**base, **_bridge_config()}

@router.post("")
def update_settings(update: SettingsUpdate):
    """Update user settings."""
    settings = db.find_one("settings", "global")
    if not settings:
        settings = db.insert("settings", {"id": "global"})

    updates = {k: v for k, v in update.dict().items() if v is not None}
    db.update("settings", "global", updates)
    return {**db.find_one("settings", "global"), **_bridge_config()}


@router.get("/mt5-bridge-url", summary="Current MT5 bridge URL config")
def get_bridge_url_config():
    return _bridge_config()


@router.post("/mt5-bridge-url", summary="Set the MT5 bridge URL and test it")
async def set_bridge_url_config(payload: BridgeUrlUpdate):
    """Persist a runtime override for the MT5 bridge URL (no redeploy needed),
    then probe it so the UI can confirm the tunnel is actually reachable.

    An empty ``url`` clears the override and falls back to the env value.
    """
    effective = set_bridge_url(payload.url)
    result = {**_bridge_config(), "reachable": False, "mt5_connected": None, "error": None}
    if not effective:
        result["error"] = "No bridge URL set (cleared to empty and no env fallback)."
        return result

    headers = {"ngrok-skip-browser-warning": "true"}
    key = get_bridge_api_key()
    if key:
        headers["X-Bridge-Key"] = key
    last = None
    for _ in range(3):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{effective}/", headers=headers, timeout=12)
            result["reachable"] = resp.status_code == 200
            if resp.status_code == 200:
                body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                result["mt5_connected"] = body.get("mt5_connected")
                result["bridge_response"] = body
            return result
        except Exception as e:  # noqa: BLE001
            last = e
    result["error"] = f"{type(last).__name__}: {last}" if last else "unreachable"
    return result

@router.get("/export")
def export_settings():
    """Export all app settings as JSON."""
    return {
        "settings": db.find_one("settings", "global") or {},
        "database_stats": db.get_stats()
    }
