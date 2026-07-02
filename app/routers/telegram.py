"""Telegram Router — API endpoints for signal polling and management."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.services.telegram_service import telegram_service

router = APIRouter(prefix="/telegram", tags=["Telegram"])


class ConfigureRequest(BaseModel):
    token: str = Field(..., description="Telegram Bot API token")
    channel_id: str = Field(..., description="Telegram channel/chat ID")


class AutoTradeRequest(BaseModel):
    account_balance: float = Field(default=10000.0, description="Account balance for lot sizing")
    risk_pct: float = Field(default=1.0, description="Risk percentage per trade")


@router.get("/status")
def get_status():
    """Return Telegram bot status and last poll info."""
    try:
        stats = telegram_service.get_stats()
        return {
            "configured": stats.get("configured"),
            "channel_id": stats.get("channel_id"),
            "last_poll_time": stats.get("last_poll_time"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals")
def list_signals(limit: int = 50, acknowledged: Optional[bool] = None, auto_traded: Optional[bool] = None):
    """List parsed and raw Telegram signals with optional filters."""
    try:
        signals = telegram_service.get_signals(limit=limit, acknowledged=acknowledged, auto_traded=auto_traded)
        return {"signals": signals, "count": len(signals)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/poll")
def manual_poll():
    """Manually trigger a Telegram poll."""
    try:
        result = telegram_service.poll()
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Poll failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/acknowledge/{signal_id}")
def acknowledge(signal_id: str):
    """Mark a signal as acknowledged."""
    try:
        result = telegram_service.acknowledge(signal_id)
        if result.get("error"):
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto-trade/{signal_id}")
def auto_trade(signal_id: str, request: Optional[AutoTradeRequest] = None):
    """Auto-trade a signal via the trade lifecycle service."""
    try:
        req = request or AutoTradeRequest()
        result = telegram_service.auto_trade(signal_id, req.account_balance, req.risk_pct)
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
def get_stats():
    """Return signal statistics."""
    try:
        return telegram_service.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/configure")
def configure(request: ConfigureRequest):
    """Set Telegram bot token and channel ID at runtime."""
    try:
        result = telegram_service.configure(request.token, request.channel_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
