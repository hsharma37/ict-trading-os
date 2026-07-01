"""Trades Router — Full trade lifecycle with partial closes and R-tracking."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from app.services.trade_lifecycle_service import trade_lifecycle_service

router = APIRouter(prefix="/trades", tags=["Trades"])


class TradeCreate(BaseModel):
    symbol: str
    side: str = Field(default="BUY", description="BUY or SELL")
    entry_price: Optional[float] = None
    stop_loss: float = Field(default=0, description="Stop loss price (required for auto lot)")
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    quantity: Optional[float] = None
    account_balance: float = 10000.0
    risk_pct: float = 1.0
    strategy: Optional[str] = None
    notes: Optional[str] = None
    plan_id: Optional[str] = None


class PartialClose(BaseModel):
    fraction: float = Field(default=0.3, ge=0.01, le=1.0, description="Fraction of remaining position to close")
    exit_price: float
    label: str = "TP"


class FullClose(BaseModel):
    exit_price: float


@router.post("")
def create_trade(trade: TradeCreate):
    """Create a new trade. Auto-calculates lot size if not provided and SL is set."""
    try:
        result = trade_lifecycle_service.create_trade(
            symbol=trade.symbol,
            side=trade.side,
            entry_price=trade.entry_price,
            stop_loss=trade.stop_loss,
            take_profit_1=trade.take_profit_1,
            take_profit_2=trade.take_profit_2,
            take_profit_3=trade.take_profit_3,
            quantity=trade.quantity,
            account_balance=trade.account_balance,
            risk_pct=trade.risk_pct,
            strategy=trade.strategy,
            notes=trade.notes,
            plan_id=trade.plan_id,
        )
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/open")
def get_open_trades():
    """Get all open trades with live unrealized PnL."""
    try:
        return {"trades": trade_lifecycle_service.get_open_trades()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary")
def get_stats():
    """Get comprehensive trade statistics."""
    try:
        return trade_lifecycle_service.get_trade_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/kelly")
def get_kelly():
    """Get Kelly criterion."""
    try:
        return trade_lifecycle_service.get_kelly_criterion()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent")
def get_recent(limit: int = 10):
    """Get recent closed trades."""
    try:
        return {"trades": trade_lifecycle_service.get_recent_trades(limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def list_trades(status: Optional[str] = None, symbol: Optional[str] = None):
    """List all trades."""
    try:
        return {"trades": trade_lifecycle_service.list_trades(status, symbol)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{trade_id}")
def get_trade(trade_id: str):
    """Get a single trade with current PnL."""
    try:
        trade = trade_lifecycle_service.get_trade(trade_id)
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")
        return trade
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{trade_id}/partial")
def partial_close(trade_id: str, request: PartialClose):
    """Partially close a trade (e.g., 30% at TP1)."""
    try:
        result = trade_lifecycle_service.partial_close(trade_id, request.fraction, request.exit_price, request.label)
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{trade_id}/close")
def full_close(trade_id: str, request: FullClose):
    """Fully close a trade."""
    try:
        result = trade_lifecycle_service.full_close(trade_id, request.exit_price)
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{trade_id}/move-sl-be")
def move_sl_to_breakeven(trade_id: str):
    """Move stop loss to entry price (breakeven)."""
    try:
        result = trade_lifecycle_service.move_sl_to_breakeven(trade_id)
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
