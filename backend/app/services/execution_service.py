"""
Execution service — hardened trade lifecycle with state machine,
pre-trade validation, fill tracking, and audit logging.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlmodel import Session, select

from app.models.trade import Trade
from app.models.audit_log import AuditLog
from app.models.risk_ledger import DailyRiskLedger
from app.models.suggestion import Suggestion
from app.schemas.trade_schemas import TradeCreate
from app.core.event_bus import (
    event_bus,
    TradeOpenedEvent,
    TradeClosedEvent,
)


# ────────────────────────────────────────────────
# Order State Machine
# ────────────────────────────────────────────────
VALID_TRANSITIONS = {
    "pending": ["validated", "cancelled"],
    "validated": ["submitted", "cancelled"],
    "submitted": ["open", "rejected"],
    "open": ["partial_close", "closed"],
    "partial_close": ["partial_close", "closed"],
    "rejected": ["pending"],
    "cancelled": [],
    "closed": [],
}


class ExecutionError(Exception):
    pass


def _can_transition(from_status: str, to_status: str) -> bool:
    return to_status in VALID_TRANSITIONS.get(from_status, [])


def _audit(
    db: Session,
    user_id: UUID,
    entity_type: str,
    entity_id: UUID,
    action: str,
    previous: dict,
    new: dict,
    actor: str = "system",
    reason: Optional[str] = None,
) -> None:
    log = AuditLog(
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        previous_state=previous,
        new_state=new,
        actor=actor,
        reason=reason,
    )
    db.add(log)
    db.commit()


# ────────────────────────────────────────────────
# Pre-trade Validation
# ────────────────────────────────────────────────
def _validate_pre_trade(db: Session, trade: Trade, user_id: UUID) -> List[str]:
    """Return list of errors if trade violates safety rules."""
    errors = []

    # 1. Daily risk ledger check
    from datetime import date
    today = date.today()
    ledger = db.exec(
        select(DailyRiskLedger)
        .where(DailyRiskLedger.user_id == user_id)
        .where(DailyRiskLedger.date == today)
    ).first()

    if ledger:
        if ledger.is_locked:
            errors.append(f"Daily trading locked: {ledger.lock_reason}")
        if ledger.trades_taken >= ledger.max_trades:
            errors.append(f"Max trades ({ledger.max_trades}) reached for today")
        if trade.risk_amount and ledger.daily_loss_limit:
            projected = ledger.current_loss + (trade.risk_amount or 0)
            if projected >= ledger.daily_loss_limit:
                errors.append(
                    f"Risk would exceed daily loss limit (${ledger.daily_loss_limit:.2f})"
                )

    # 2. Stop loss required
    if trade.stop_loss is None or trade.stop_loss <= 0:
        errors.append("Stop loss is required and must be positive")

    # 3. Leverage cap
    if trade.leverage > 100:
        errors.append("Leverage exceeds maximum 100x")

    # 4. Position size validation
    if trade.lot_size is not None and trade.lot_size <= 0:
        errors.append("Lot size must be positive")

    # 5. Direction validation
    if trade.direction not in ("long", "short"):
        errors.append("Direction must be 'long' or 'short'")

    return errors


# ────────────────────────────────────────────────
# Trade Lifecycle
# ────────────────────────────────────────────────
def create_trade(db: Session, trade_create: TradeCreate, user_id: UUID) -> Trade:
    db_trade = Trade(**trade_create.dict(), user_id=user_id, status="pending")

    # Pre-trade validation
    errors = _validate_pre_trade(db, db_trade, user_id)
    if errors:
        raise ExecutionError(f"Pre-trade validation failed: {'; '.join(errors)}")

    # Transition: pending → validated
    db_trade.status = "validated"
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)

    # Audit log
    _audit(
        db=db,
        user_id=user_id,
        entity_type="trade",
        entity_id=db_trade.id,
        action="created",
        previous={},
        new={"status": "validated", **trade_create.dict()},
        actor="user",
    )

    # Publish event
    event_bus.publish_trade_opened(
        TradeOpenedEvent(
            trade_id=str(db_trade.id),
            symbol=db_trade.symbol,
            direction=db_trade.direction,
            entry_price=db_trade.entry_price,
            lot_size=db_trade.lot_size,
            leverage=db_trade.leverage,
            risk_amount=db_trade.risk_amount,
            timestamp=datetime.utcnow().isoformat() + "Z",
            source="manual",
        )
    )

    return db_trade


def submit_trade(db: Session, trade: Trade) -> Trade:
    """Transition validated trade to submitted (sent to MT5 bridge)."""
    if not _can_transition(trade.status, "submitted"):
        raise ExecutionError(f"Cannot transition from {trade.status} to submitted")

    previous = {"status": trade.status}
    trade.status = "submitted"
    db.add(trade)
    db.commit()
    db.refresh(trade)

    _audit(
        db=db,
        user_id=trade.user_id,
        entity_type="trade",
        entity_id=trade.id,
        action="submitted",
        previous=previous,
        new={"status": trade.status},
    )
    return trade


def mark_trade_open(db: Session, trade: Trade) -> Trade:
    """Mark trade as open (fill received from MT5)."""
    if not _can_transition(trade.status, "open"):
        raise ExecutionError(f"Cannot transition from {trade.status} to open")

    previous = {"status": trade.status}
    trade.status = "open"
    db.add(trade)
    db.commit()
    db.refresh(trade)

    _audit(
        db=db,
        user_id=trade.user_id,
        entity_type="trade",
        entity_id=trade.id,
        action="opened",
        previous=previous,
        new={"status": trade.status},
    )
    return trade


def close_trade(
    db: Session,
    trade: Trade,
    exit_price: Optional[float] = None,
    pnl: Optional[float] = None,
    pnl_pips: Optional[float] = None,
    actor: str = "user",
) -> Trade:
    if not _can_transition(trade.status, "closed"):
        raise ExecutionError(f"Cannot transition from {trade.status} to closed")

    previous = {
        "status": trade.status,
        "exit_price": trade.exit_price,
        "pnl": trade.pnl,
    }

    trade.status = "closed"
    trade.exit_price = exit_price
    trade.pnl = pnl
    trade.pnl_pips = pnl_pips
    trade.exit_time = datetime.utcnow()

    if pnl is not None:
        trade.outcome = "win" if pnl > 0 else "loss" if pnl < 0 else "breakeven"

    db.add(trade)
    db.commit()
    db.refresh(trade)

    _audit(
        db=db,
        user_id=trade.user_id,
        entity_type="trade",
        entity_id=trade.id,
        action="closed",
        previous=previous,
        new={
            "status": trade.status,
            "exit_price": trade.exit_price,
            "pnl": trade.pnl,
            "outcome": trade.outcome,
        },
        actor=actor,
    )

    event_bus.publish_trade_closed(
        TradeClosedEvent(
            trade_id=str(trade.id),
            exit_price=exit_price,
            pnl=pnl,
            pnl_pips=pnl_pips,
            outcome=trade.outcome,
            exit_time=trade.exit_time.isoformat() if trade.exit_time else None,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
    )

    return trade


def cancel_trade(db: Session, trade: Trade, reason: Optional[str] = None) -> Trade:
    if not _can_transition(trade.status, "cancelled"):
        raise ExecutionError(f"Cannot transition from {trade.status} to cancelled")

    previous = {"status": trade.status}
    trade.status = "cancelled"
    db.add(trade)
    db.commit()
    db.refresh(trade)

    _audit(
        db=db,
        user_id=trade.user_id,
        entity_type="trade",
        entity_id=trade.id,
        action="cancelled",
        previous=previous,
        new={"status": trade.status},
        reason=reason,
    )
    return trade
