"""
Execution service — business logic for trade lifecycle, MT5 integration, and fills.

Currently a thin wrapper. Will expand with:
- Order state machine
- Pre-trade validation hooks
- Fill tracking and slippage recording
- Event publishing for downstream services
"""
from datetime import datetime
from sqlmodel import Session
from app.models.trade import Trade
from app.schemas.trade_schemas import TradeCreate


def create_trade(db: Session, trade: TradeCreate) -> Trade:
    db_trade = Trade(**trade.dict())
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)
    return db_trade


def close_trade(
    db: Session,
    trade: Trade,
    exit_price: float | None,
    pnl: float | None,
    pnl_pips: float | None,
) -> Trade:
    trade.status = "closed"
    trade.exit_price = exit_price
    trade.pnl = pnl
    trade.pnl_pips = pnl_pips
    trade.exit_time = datetime.utcnow()

    if pnl is not None:
        trade.outcome = "win" if pnl > 0 else "loss" if pnl < 0 else "breakeven"

    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade
