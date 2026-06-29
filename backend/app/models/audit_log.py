"""
Audit Log — immutable, replayable record of every state change.

Captures: trade lifecycle, risk rule triggers, alert triggers,
execution decisions, and human overrides. Every entry is append-only
and never mutated or deleted.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)

    # What changed
    entity_type: str = Field(index=True)  # trade, alert, risk_ledger, suggestion, etc.
    entity_id: UUID = Field(index=True)
    action: str = Field(index=True)  # created, updated, closed, triggered, locked, approved, rejected

    # Before/after snapshot (immutable)
    previous_state: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    new_state: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # Who/why
    actor: str = Field(default="system")  # system, user, ai, mt5_bridge
    reason: Optional[str] = None
    ip_address: Optional[str] = None

    # Timestamp (never changes)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
