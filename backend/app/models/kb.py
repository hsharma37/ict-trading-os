"""
Knowledge Base models — sources and chunks for RAG.

Uses pgvector for embedding storage (VECTOR column).
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from pgvector.sqlalchemy import Vector  # type: ignore
from sqlmodel import SQLModel, Field


class KBSource(SQLModel, table=True):
    __tablename__ = "kb_sources"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)

    source_type: str = Field(index=True)  # youtube, transcript, pdf, note
    title: str
    url: Optional[str] = None
    content: Optional[str] = None
    metadata: Optional[dict] = Field(sa_column=Column(JSONB), default=None)
    chunk_count: int = Field(default=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class KBChunk(SQLModel, table=True):
    __tablename__ = "kb_chunks"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_id: UUID = Field(foreign_key="kb_sources.id", index=True)

    chunk_index: int = Field(index=True)
    content: str

    # pgvector embedding (768 dims for Nomic Embed)
    embedding: Optional[List[float]] = Field(sa_column=Column(Vector(768)), default=None)
    metadata: Optional[dict] = Field(sa_column=Column(JSONB), default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
