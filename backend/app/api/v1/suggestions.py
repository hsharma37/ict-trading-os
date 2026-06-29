from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from app.database import get_db
from app.models.suggestion import Suggestion
from app.models.trade import Trade
from app.services.suggestion_service import (
    create_suggestion,
    approve_suggestion,
    reject_suggestion,
    execute_approved_suggestion,
    list_pending_suggestions,
)
from app.services.fail_safe_service import validate_daily_risk
from app.services.execution_service import ExecutionError

router = APIRouter()


@router.get("/", summary="List suggestions")
async def list_suggestions(
    user_id: UUID,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List suggestions for a user, optionally filtered by status."""
    statement = select(Suggestion).where(Suggestion.user_id == user_id)
    if status:
        statement = statement.where(Suggestion.status == status)
    statement = statement.order_by(Suggestion.created_at.desc())
    return db.exec(statement).all()


@router.get("/pending", summary="List pending suggestions")
async def list_pending(
    user_id: UUID,
    db: Session = Depends(get_db),
):
    """List pending suggestions that haven't expired."""
    return list_pending_suggestions(db, user_id)


@router.post("/", status_code=201, summary="Create a suggestion")
async def create(
    user_id: UUID,
    symbol: str,
    direction: str,
    setup_score: float,
    confidence: float,
    suggested_entry: Optional[float] = None,
    suggested_stop: Optional[float] = None,
    suggested_target: Optional[float] = None,
    suggested_lot_size: Optional[float] = None,
    risk_amount: Optional[float] = None,
    risk_percentage: Optional[float] = None,
    expected_r: Optional[float] = None,
    ai_narrative: Optional[str] = None,
    setup_type: Optional[str] = None,
    confluence_score: int = 0,
    paper_trade: bool = False,
    expires_in_minutes: int = 30,
    db: Session = Depends(get_db),
):
    """Create a new trade suggestion (from AI or rule-based signal)."""
    return create_suggestion(
        db=db,
        user_id=user_id,
        symbol=symbol,
        direction=direction,
        setup_score=setup_score,
        confidence=confidence,
        suggested_entry=suggested_entry,
        suggested_stop=suggested_stop,
        suggested_target=suggested_target,
        suggested_lot_size=suggested_lot_size,
        risk_amount=risk_amount,
        risk_percentage=risk_percentage,
        expected_r=expected_r,
        ai_narrative=ai_narrative,
        setup_type=setup_type,
        confluence_score=confluence_score,
        paper_trade=paper_trade,
        expires_in_minutes=expires_in_minutes,
    )


@router.post("/{suggestion_id}/approve", summary="Approve a suggestion")
async def approve(
    suggestion_id: UUID,
    approved_by: str = "user",
    db: Session = Depends(get_db),
):
    """Approve a pending suggestion. After approval, it can be executed."""
    suggestion = db.get(Suggestion, suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    try:
        return approve_suggestion(db, suggestion, approved_by=approved_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{suggestion_id}/execute", summary="Execute approved suggestion")
async def execute(
    suggestion_id: UUID,
    db: Session = Depends(get_db),
):
    """Execute an approved suggestion as a real trade."""
    suggestion = db.get(Suggestion, suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    # Check daily risk before executing
    risk_check = validate_daily_risk(db, suggestion.user_id)
    if not risk_check["can_trade"]:
        raise HTTPException(status_code=403, detail=risk_check["lock_reason"])

    try:
        trade = execute_approved_suggestion(db, suggestion)
        return {
            "status": "executed",
            "suggestion_id": suggestion_id,
            "trade_id": trade.id,
            "paper_trade": suggestion.paper_trade,
        }
    except (ValueError, ExecutionError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{suggestion_id}/reject", summary="Reject a suggestion")
async def reject(
    suggestion_id: UUID,
    reason: str,
    rejected_by: str = "user",
    db: Session = Depends(get_db),
):
    """Reject a pending suggestion with a reason."""
    suggestion = db.get(Suggestion, suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    try:
        return reject_suggestion(db, suggestion, reason=reason, rejected_by=rejected_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
