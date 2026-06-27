"""
Pydantic schemas for Journal requests and responses.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class JournalBase(BaseModel):
    user_id: UUID
    trade_id: Optional[UUID] = None
    pre_trade_notes: Optional[str] = None
    post_trade_notes: Optional[str] = None
    emotion_score: Optional[int] = Field(None, ge=1, le=10)
    setup_grade: Optional[int] = Field(None, ge=1, le=10)
    execution_grade: Optional[int] = Field(None, ge=1, le=10)
    management_grade: Optional[int] = Field(None, ge=1, le=10)
    tags: List[str] = []
    lessons: Optional[str] = None


class JournalCreate(JournalBase):
    pass


class JournalRead(JournalBase):
    id: UUID
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JournalUpdate(BaseModel):
    pre_trade_notes: Optional[str] = None
    post_trade_notes: Optional[str] = None
    emotion_score: Optional[int] = Field(None, ge=1, le=10)
    setup_grade: Optional[int] = Field(None, ge=1, le=10)
    execution_grade: Optional[int] = Field(None, ge=1, le=10)
    management_grade: Optional[int] = Field(None, ge=1, le=10)
    tags: Optional[List[str]] = None
    lessons: Optional[str] = None
