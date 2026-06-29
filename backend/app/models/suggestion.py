"""
Suggestion Queue — semi-automation: signal → suggestion → approval → execution.

AI or rule-based signals generate suggestions. Human must approve
before execution. Paper trading mode creates suggestions that execute
without real money.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field


class Suggestion(SQLModel, table=True):
    __tablename__ = "suggestions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)

    # Signal source
    symbol: str = Field(index=True)
    direction: str = Field(index=True)  # long, short
    setup_type: Optional[str] = None  # MSS, FVG, OB, etc.
    timeframes: Optional[list] = Field(default=None, sa_column=Column(JSON))

    # Scoring
    setup_score: float = Field(default=0.0)  # 0-100
    confluence_score: int = Field(default=0)  # number of aligned concepts
    confidence: float = Field(default=0.0)  # 0-1

    # Suggested parameters
    suggested_entry: Optional[float] = None
    suggested_stop: Optional[float] = None
    suggested_target: Optional[float] = None
    suggested_lot_size: Optional[float] = None

    # Risk preview
    risk_amount: Optional[float] = None
    risk_percentage: Optional[float] = None
    expected_r: Optional[float] = None

    # Workflow state
    status: str = Field(default="pending", index=True)  # pending, approved, rejected, expired, executed
    paper_trade: bool = Field(default=False)  # True = execute without real money

    # Approval
    approved_by: Optional[str] = None  # user_id or "system"
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    # Link to executed trade (if approved)
    trade_id: Optional[UUID] = Field(foreign_key="trades.id", default=None)

    # AI narrative
    ai_narrative: Optional[str] = None

    # Expiry
    expires_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
