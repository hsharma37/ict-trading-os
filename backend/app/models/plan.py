"""
Trading Plan model — daily/weekly bias, killzones, confluence, and rules.
"""
from datetime import date, datetime
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import SQLModel, Field


class TradingPlan(SQLModel, table=True):
    __tablename__ = "trading_plans"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)

    date: date = Field(index=True)
    session: str = Field(default="combined", index=True)  # london, ny, asia, combined
    bias_direction: str = Field(default="neutral")  # bullish, bearish, neutral
    narrative: Optional[str] = None
    confluence_tags: List[str] = Field(sa_column=ARRAY(str), default_factory=list)
    killzones: List[str] = Field(sa_column=ARRAY(str), default_factory=list)

    max_trades: int = Field(default=3)
    daily_loss_limit: Optional[float] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
