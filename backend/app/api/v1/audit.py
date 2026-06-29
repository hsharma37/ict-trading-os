from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from uuid import UUID
from datetime import datetime, date

from app.database import get_db
from app.models.audit_log import AuditLog

router = APIRouter()


@router.get("/", summary="Query audit log")
async def list_audit_logs(
    user_id: UUID,
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Query the immutable audit log. All entries are append-only."""
    statement = select(AuditLog).where(AuditLog.user_id == user_id)

    if entity_type:
        statement = statement.where(AuditLog.entity_type == entity_type)
    if action:
        statement = statement.where(AuditLog.action == action)
    if entity_id:
        statement = statement.where(AuditLog.entity_id == entity_id)
    if from_date:
        statement = statement.where(AuditLog.created_at >= datetime.combine(from_date, datetime.min.time()))
    if to_date:
        statement = statement.where(AuditLog.created_at <= datetime.combine(to_date, datetime.max.time()))

    statement = statement.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    return db.exec(statement).all()


@router.get("/{log_id}", summary="Get single audit log entry")
async def get_audit_log(
    log_id: UUID,
    db: Session = Depends(get_db),
):
    log = db.get(AuditLog, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Audit log entry not found")
    return log
