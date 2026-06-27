"""
Trade (Execution) model — order lifecycle, fills, PnL, and outcome.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field


class Trade(SQLModel, table=True):
    __tablename__ = "trades"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    plan_id: Optional[UUID] = Field(foreign_key="trading_plans.id", default=None, index=True)

    symbol: str = Field(index=True)
    direction: str = Field(index=True)  # long, short

    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None

    lot_size: Optional[float] = None
    leverage: int = Field(default=1)
    risk_amount: Optional[float] = None

    status: str = Field(default="pending", index=True)  # pending, open, closed, cancelled
    outcome: Optional[str] = None  # win, loss, breakeven
    pnl: Optional[float] = None
    pnl_pips: Optional[float] = None
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    entry_time: datetime = Field(default_factory=datetime.utcnow)

    created_at: datetime = Field(default_factory=datetime.utcnow)
