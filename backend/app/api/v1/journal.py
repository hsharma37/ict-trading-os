from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.models.journal import JournalEntry
from app.schemas.journal_schemas import JournalCreate, JournalRead, JournalUpdate

router = APIRouter()


@router.get("/", response_model=List[JournalRead])
async def list_entries(
    trade_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(JournalEntry)
    if trade_id:
        statement = statement.where(JournalEntry.trade_id == trade_id)
    statement = statement.offset(skip).limit(limit)
    return db.exec(statement).all()


@router.get("/{entry_id}", response_model=JournalRead)
async def get_entry(entry_id: UUID, db: Session = Depends(get_db)):
    entry = db.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return entry


@router.post("/", response_model=JournalRead, status_code=201)
async def create_entry(entry: JournalCreate, db: Session = Depends(get_db)):
    db_entry = JournalEntry(**entry.dict())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@router.patch("/{entry_id}", response_model=JournalRead)
async def update_entry(entry_id: UUID, entry_update: JournalUpdate, db: Session = Depends(get_db)):
    entry = db.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    entry_data = entry_update.dict(exclude_unset=True)
    for key, value in entry_data.items():
        setattr(entry, key, value)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(entry_id: UUID, db: Session = Depends(get_db)):
    entry = db.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    db.delete(entry)
    db.commit()
