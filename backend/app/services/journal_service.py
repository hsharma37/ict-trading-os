"""
Journal service — business logic for trade journaling, grading, and review.
"""
from sqlmodel import Session
from app.models.journal import JournalEntry
from app.schemas.journal_schemas import JournalCreate


def create_entry(db: Session, entry: JournalCreate) -> JournalEntry:
    db_entry = JournalEntry(**entry.dict())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry
