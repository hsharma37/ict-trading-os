"""
Pydantic schemas for Trade requests and responses.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class TradeBase(BaseModel):
    user_id: UUID
    plan_id: Optional[UUID] = None
    symbol: str
    direction: str  # long, short
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    lot_size: Optional[float] = None
    leverage: int = 1
    risk_amount: Optional[float] = None


class TradeCreate(TradeBase):
    pass


class TradeRead(TradeBase):
    id: UUID
    status: str
    outcome: Optional[str] = None
    pnl: Optional[float] = None
    pnl_pips: Optional[float] = None
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    entry_time: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TradeUpdate(BaseModel):
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    lot_size: Optional[float] = None
    leverage: Optional[int] = None
    risk_amount: Optional[float] = None
    status: Optional[str] = None
