"""
Database layer: SQLModel engine, session management, and table creation.

Uses PostgreSQL as the primary database with pgvector for embeddings.
"""
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Session

from app.config import settings

# ────────────────────────────────────────────────
# Engine
# ────────────────────────────────────────────────
engine: Engine = create_engine(
    settings.database_url,
    echo=False,  # Set True for SQL query logging
    pool_pre_ping=True,
    pool_recycle=300,
)

# ────────────────────────────────────────────────
# Session factory
# ────────────────────────────────────────────────
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
)


# ────────────────────────────────────────────────
# Dependency for FastAPI routes
# ────────────────────────────────────────────────
def get_db() -> Session:
    """
    FastAPI dependency that yields a database session and
    automatically closes it when the request is done.
    """
    with SessionLocal() as session:
        yield session


# ────────────────────────────────────────────────
# Table initialization (for dev, not for Alembic-managed prod)
# ────────────────────────────────────────────────
def init_db() -> None:
    """
    Create all tables defined by SQLModel subclasses.
    In production, use Alembic migrations instead.
    """
    # Import models so they register with SQLModel metadata
    from app.models import (  # noqa: F401
        user, plan, trade, journal, kb, alert, risk_ledger,
        audit_log, alert_history, suggestion,
    )

    SQLModel.metadata.create_all(engine)
