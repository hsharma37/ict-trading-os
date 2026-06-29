"""
Suggestion service — semi-automation: AI/ruler signals → human approval → execution.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from sqlmodel import Session, select

from app.models.suggestion import Suggestion
from app.models.trade import Trade
from app.models.audit_log import AuditLog
from app.schemas.trade_schemas import TradeCreate
from app.services.execution_service import create_trade
from app.core.event_bus import event_bus, SuggestionCreatedEvent

logger = logging.getLogger(__name__)


def create_suggestion(
    db: Session,
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
) -> Suggestion:
    """Create a new trade suggestion from AI or rule-based signal."""
    suggestion = Suggestion(
        user_id=user_id,
        symbol=symbol,
        direction=direction,
        setup_score=setup_score,
        confluence_score=confluence_score,
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
        paper_trade=paper_trade,
        expires_at=datetime.utcnow() + timedelta(minutes=expires_in_minutes),
        status="pending",
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)

    # Audit
    audit = AuditLog(
        user_id=user_id,
        entity_type="suggestion",
        entity_id=suggestion.id,
        action="created",
        previous_state={},
        new_state={"status": "pending", "symbol": symbol, "direction": direction},
        actor="system" if ai_narrative else "rule",
        reason=f"Setup score {setup_score}, confidence {confidence}",
    )
    db.add(audit)
    db.commit()

    # Publish event
    event_bus.publish_suggestion_created(
        SuggestionCreatedEvent(
            suggestion_id=str(suggestion.id),
            trade_id="",
            symbol=symbol,
            setup_score=setup_score,
            confidence=confidence,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
    )

    return suggestion


def approve_suggestion(
    db: Session,
    suggestion: Suggestion,
    approved_by: str = "user",
) -> Suggestion:
    """Approve a suggestion and optionally execute the trade."""
    if suggestion.status != "pending":
        raise ValueError(f"Suggestion must be pending, got {suggestion.status}")

    if suggestion.expires_at and datetime.utcnow() > suggestion.expires_at:
        suggestion.status = "expired"
        db.add(suggestion)
        db.commit()
        raise ValueError("Suggestion has expired")

    previous = {"status": suggestion.status}
    suggestion.status = "approved"
    suggestion.approved_by = approved_by
    suggestion.approved_at = datetime.utcnow()
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)

    # Audit
    audit = AuditLog(
        user_id=suggestion.user_id,
        entity_type="suggestion",
        entity_id=suggestion.id,
        action="approved",
        previous_state=previous,
        new_state={"status": "approved", "approved_by": approved_by},
        actor=approved_by,
    )
    db.add(audit)
    db.commit()

    return suggestion


def execute_approved_suggestion(
    db: Session,
    suggestion: Suggestion,
) -> Trade:
    """Execute the trade from an approved suggestion."""
    if suggestion.status != "approved":
        raise ValueError(f"Suggestion must be approved, got {suggestion.status}")

    trade_create = TradeCreate(
        symbol=suggestion.symbol,
        direction=suggestion.direction,
        entry_price=suggestion.suggested_entry,
        stop_loss=suggestion.suggested_stop,
        take_profit_1=suggestion.suggested_target,
        lot_size=suggestion.suggested_lot_size,
        leverage=1,
        risk_amount=suggestion.risk_amount,
    )

    trade = create_trade(db, trade_create, suggestion.user_id)

    # Link suggestion to trade
    suggestion.trade_id = trade.id
    suggestion.status = "executed"
    db.add(suggestion)
    db.commit()

    # Audit
    audit = AuditLog(
        user_id=suggestion.user_id,
        entity_type="suggestion",
        entity_id=suggestion.id,
        action="executed",
        previous_state={"status": "approved"},
        new_state={"status": "executed", "trade_id": str(trade.id)},
        actor="system",
        reason="Auto-executed from approved suggestion",
    )
    db.add(audit)
    db.commit()

    return trade


def reject_suggestion(
    db: Session,
    suggestion: Suggestion,
    reason: str,
    rejected_by: str = "user",
) -> Suggestion:
    """Reject a suggestion with a reason."""
    if suggestion.status != "pending":
        raise ValueError(f"Suggestion must be pending, got {suggestion.status}")

    previous = {"status": suggestion.status}
    suggestion.status = "rejected"
    suggestion.rejection_reason = reason
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)

    audit = AuditLog(
        user_id=suggestion.user_id,
        entity_type="suggestion",
        entity_id=suggestion.id,
        action="rejected",
        previous_state=previous,
        new_state={"status": "rejected", "reason": reason},
        actor=rejected_by,
        reason=reason,
    )
    db.add(audit)
    db.commit()

    return suggestion


def list_pending_suggestions(
    db: Session,
    user_id: UUID,
) -> List[Suggestion]:
    """List all pending suggestions for a user that haven't expired."""
    now = datetime.utcnow()
    return db.exec(
        select(Suggestion)
        .where(Suggestion.user_id == user_id)
        .where(Suggestion.status == "pending")
        .where((Suggestion.expires_at > now) | (Suggestion.expires_at.is_(None)))
        .order_by(Suggestion.created_at.desc())
    ).all()


def expire_old_suggestions(db: Session) -> int:
    """Mark expired suggestions as expired. Returns count."""
    now = datetime.utcnow()
    expired = db.exec(
        select(Suggestion)
        .where(Suggestion.status == "pending")
        .where(Suggestion.expires_at < now)
    ).all()

    count = 0
    for s in expired:
        s.status = "expired"
        db.add(s)
        count += 1

    if count > 0:
        db.commit()

    return count
