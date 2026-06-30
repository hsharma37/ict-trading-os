"""Settings Router — User preferences and app configuration."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.core.database import db

router = APIRouter(prefix="/settings", tags=["Settings"])

class SettingsUpdate(BaseModel):
    theme: Optional[str] = None
    default_symbol: Optional[str] = None
    risk_pct: Optional[float] = None
    account_balance: Optional[float] = None
    auto_trade: Optional[bool] = None
    notifications: Optional[bool] = None
    layout: Optional[str] = None

@router.get("")
def get_settings():
    """Get current user settings."""
    settings = db.find_one("settings", "global")
    if not settings:
        return {
            "id": "global",
            "theme": "dark",
            "default_symbol": "EURUSD",
            "risk_pct": 1.0,
            "account_balance": 10000.0,
            "auto_trade": False,
            "notifications": True,
            "layout": "default",
        }
    return settings

@router.post("")
def update_settings(update: SettingsUpdate):
    """Update user settings."""
    settings = db.find_one("settings", "global")
    if not settings:
        settings = db.insert("settings", {"id": "global"})
    
    updates = {k: v for k, v in update.dict().items() if v is not None}
    db.update("settings", "global", updates)
    return db.find_one("settings", "global")

@router.get("/export")
def export_settings():
    """Export all app settings as JSON."""
    return {
        "settings": db.find_one("settings", "global") or {},
        "database_stats": db.get_stats()
    }
