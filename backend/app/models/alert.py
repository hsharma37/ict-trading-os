"""
Alert model — rule-based alerts with conditions and routing.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field


class Alert(SQLModel, table=True):
    __tablename__ = "alerts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)

    symbol: str = Field(index=True)
    alert_type: str = Field(index=True)  # price, ict_pattern, sentiment, risk, custom
    condition: dict = Field(sa_column=Column(JSONB))
    message: Optional[str] = None
    is_active: bool = Field(default=True, index=True)
    triggered_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
