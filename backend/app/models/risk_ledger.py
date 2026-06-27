"""
Daily Risk Ledger model — per-day loss tracking, trade counting, and lockout.
"""
from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field


class DailyRiskLedger(SQLModel, table=True):
    __tablename__ = "daily_risk_ledger"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    date: date = Field(index=True)

    starting_balance: Optional[float] = None
    daily_loss_limit: Optional[float] = None
    current_loss: float = Field(default=0.0)
    trades_taken: int = Field(default=0)
    max_trades: int = Field(default=3)
    is_locked: bool = Field(default=False, index=True)
    lock_reason: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
