"""Journal Router — durable per-instrument closed-trade journal."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.trade_journal_service import trade_journal_service

router = APIRouter(prefix="/journal", tags=["Journal"])


class RiskFill(BaseModel):
    sl: Optional[float] = None
    r: Optional[float] = None


@router.get("")
def list_journal(symbol: Optional[str] = None, limit: int = 200):
    """Closed trades, optionally for one instrument, newest first."""
    trades = trade_journal_service.list_trades(symbol, limit)
    return {"trades": trades, "count": len(trades),
            "summary": trade_journal_service.summary(symbol)}


@router.get("/symbols")
def journal_symbols():
    """Instruments that have journaled trades, with counts + net P&L."""
    return {"symbols": trade_journal_service.symbols()}


@router.get("/summary")
def journal_summary(symbol: Optional[str] = None):
    return trade_journal_service.summary(symbol)


@router.post("/sync", summary="Fetch MT5 closed-trade history and store it")
def sync_journal():
    """Pull the broker's history into the durable journal on demand."""
    return trade_journal_service.sync_from_mt5()


@router.post("/{ticket:path}/risk", summary="Manually fill R (via SL or directly)")
def set_risk(ticket: str, body: RiskFill):
    result = trade_journal_service.set_risk(ticket, sl=body.sl, r=body.r)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result
