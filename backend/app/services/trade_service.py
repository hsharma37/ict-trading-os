"""
Trade service — aggregation helpers for analytics and research.
"""
from typing import List, Optional
from sqlmodel import Session, select
from app.database import get_db
from app.models.trade import Trade


def get_all_trades(db: Session) -> List[Trade]:
    """Return all trades from the database."""
    return db.exec(select(Trade)).all()


def get_trade_by_id(db: Session, trade_id: str) -> Optional[Trade]:
    """Get a single trade by its UUID."""
    return db.get(Trade, trade_id)
