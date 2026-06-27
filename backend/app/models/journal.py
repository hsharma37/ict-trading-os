"""
Journal Entry model — pre/post trade notes, self-grading, tags, and lessons.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import SQLModel, Field


class JournalEntry(SQLModel, table=True):
    __tablename__ = "journal_entries"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    trade_id: Optional[UUID] = Field(foreign_key="trades.id", default=None, index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)

    pre_trade_notes: Optional[str] = None
    post_trade_notes: Optional[str] = None

    emotion_score: Optional[int] = None
    setup_grade: Optional[int] = None
    execution_grade: Optional[int] = None
    management_grade: Optional[int] = None

    tags: List[str] = Field(sa_column=ARRAY(str), default_factory=list)
    lessons: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
