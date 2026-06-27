from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.database import get_db
from app.models.trade import Trade
from app.schemas.trade_schemas import TradeCreate, TradeRead, TradeUpdate

router = APIRouter()


@router.get("/", response_model=List[TradeRead])
async def list_trades(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(Trade)
    if status:
        statement = statement.where(Trade.status == status)
    statement = statement.offset(skip).limit(limit)
    return db.exec(statement).all()


@router.get("/{trade_id}", response_model=TradeRead)
async def get_trade(trade_id: UUID, db: Session = Depends(get_db)):
    trade = db.get(Trade, trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.post("/", response_model=TradeRead, status_code=201)
async def create_trade(trade: TradeCreate, db: Session = Depends(get_db)):
    db_trade = Trade(**trade.dict())
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)
    return db_trade


@router.post("/{trade_id}/close", response_model=TradeRead)
async def close_trade(
    trade_id: UUID,
    exit_price: Optional[float] = None,
    pnl: Optional[float] = None,
    pnl_pips: Optional[float] = None,
    db: Session = Depends(get_db),
):
    trade = db.get(Trade, trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.status == "closed":
        raise HTTPException(status_code=400, detail="Trade already closed")

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


@router.patch("/{trade_id}", response_model=TradeRead)
async def update_trade(trade_id: UUID, trade_update: TradeUpdate, db: Session = Depends(get_db)):
    trade = db.get(Trade, trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    trade_data = trade_update.dict(exclude_unset=True)
    for key, value in trade_data.items():
        setattr(trade, key, value)
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


@router.delete("/{trade_id}", status_code=204)
async def delete_trade(trade_id: UUID, db: Session = Depends(get_db)):
    trade = db.get(Trade, trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    db.delete(trade)
    db.commit()
