"""Bot Automation Router."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services.bot_engine import bot_engine

router = APIRouter(prefix="/bot", tags=["Bot"])

class BotConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    risk_pct: Optional[float] = None
    account_balance: Optional[float] = None
    max_trades_per_day: Optional[int] = None

@router.get("/status")
def status():
    return bot_engine.status()

@router.post("/config")
def set_config(config: BotConfigUpdate):
    return bot_engine.set_config({k: v for k, v in config.dict().items() if v is not None})

@router.post("/scan")
def scan(auto_execute: Optional[bool] = False):
    return bot_engine.scan(auto_execute=auto_execute)
