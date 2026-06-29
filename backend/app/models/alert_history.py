"""
Alert History — record of every alert trigger and delivery attempt.

Separate from the Alert rule table; this is append-only history.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field


class AlertHistory(SQLModel, table=True):
    __tablename__ = "alert_history"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    alert_id: UUID = Field(foreign_key="alerts.id", index=True)

    symbol: str = Field(index=True)
    alert_type: str = Field(index=True)
    message: Optional[str] = None
    severity: str = Field(default="info")  # info, warning, critical

    # Delivery tracking
    delivered_to: Optional[dict] = Field(default=None, sa_column=Column(JSON))  # telegram, websocket, email
    delivery_status: str = Field(default="pending")  # pending, delivered, failed

    # Context at trigger time
    trigger_price: Optional[float] = None
    trigger_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    triggered_at: datetime = Field(default_factory=datetime.utcnow, index=True)
