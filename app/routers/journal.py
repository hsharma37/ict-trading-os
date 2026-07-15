"""Journal Router — durable per-instrument closed-trade journal."""
from fastapi import APIRouter
from typing import Optional

from app.services.trade_journal_service import trade_journal_service

router = APIRouter(prefix="/journal", tags=["Journal"])


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
