"""
Pydantic schemas for Risk service requests and responses.
"""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RiskValidate(BaseModel):
    user_id: UUID
    risk_amount: Optional[float] = None
    leverage: int = Field(default=1, ge=1, le=100)
    symbol: Optional[str] = None


class LotSizeRequest(BaseModel):
    account_balance: float = Field(..., gt=0)
    risk_amount: Optional[float] = None
    risk_percentage: Optional[float] = Field(None, ge=0, le=100)
    stop_loss_pips: float = Field(..., gt=0)
    leverage: int = Field(default=1, ge=1, le=100)
    pip_value: Optional[float] = Field(default=1.0, gt=0)
    symbol: Optional[str] = None


class RiskDailyStatus(BaseModel):
    date: str
    trades_taken: int
    max_trades: int
    current_loss: float
    daily_loss_limit: Optional[float] = None
    is_locked: bool
    lock_reason: Optional[str] = None
