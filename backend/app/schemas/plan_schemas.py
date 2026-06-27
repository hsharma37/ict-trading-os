"""
Pydantic schemas for TradingPlan requests and responses.
"""
from datetime import date
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel


class PlanBase(BaseModel):
    user_id: UUID
    date: date
    session: str = "combined"
    bias_direction: str = "neutral"
    narrative: Optional[str] = None
    confluence_tags: List[str] = []
    killzones: List[str] = []
    max_trades: int = 3
    daily_loss_limit: Optional[float] = None


class PlanCreate(PlanBase):
    pass


class PlanRead(PlanBase):
    id: UUID
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class PlanUpdate(BaseModel):
    session: Optional[str] = None
    bias_direction: Optional[str] = None
    narrative: Optional[str] = None
    confluence_tags: Optional[List[str]] = None
    killzones: Optional[List[str]] = None
    max_trades: Optional[int] = None
    daily_loss_limit: Optional[float] = None
