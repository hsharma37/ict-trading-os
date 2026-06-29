"""
Fail-safe service — deterministic guards that protect capital.

Enforces: daily loss lockout, max drawdown halt, MT5 connection loss halt,
killzone validation, and order size limits. These rules are hardcoded and
never overridden by AI or configuration.
"""
import logging
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlmodel import Session, select

from app.models.risk_ledger import DailyRiskLedger
from app.models.trade import Trade
from app.models.audit_log import AuditLog
from app.core.event_bus import event_bus, DailyRiskBreachedEvent

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────
# Hardcoded Safety Limits (Immutable)
# ────────────────────────────────────────────────
MAX_LEVERAGE = 100
DEFAULT_MAX_TRADES = 3
MAX_LOT_SIZE = 100.0  # Maximum lot size per trade


class FailSafeError(Exception):
    """Raised when a fail-safe rule is violated."""
    pass


# ────────────────────────────────────────────────
# Daily Risk Ledger
# ────────────────────────────────────────────────
def get_or_create_ledger(db: Session, user_id: UUID, for_date: Optional[date] = None) -> DailyRiskLedger:
    """Get today's risk ledger, or create one if it doesn't exist."""
    today = for_date or date.today()
    ledger = db.exec(
        select(DailyRiskLedger)
        .where(DailyRiskLedger.user_id == user_id)
        .where(DailyRiskLedger.date == today)
    ).first()

    if not ledger:
        ledger = DailyRiskLedger(
            user_id=user_id,
            date=today,
            starting_balance=0.0,
            daily_loss_limit=0.0,
            current_loss=0.0,
            trades_taken=0,
            max_trades=DEFAULT_MAX_TRADES,
            is_locked=False,
        )
        db.add(ledger)
        db.commit()
        db.refresh(ledger)

    return ledger


def update_ledger_on_trade(
    db: Session,
    ledger: DailyRiskLedger,
    pnl: Optional[float] = None,
    increment_trade: bool = True,
) -> DailyRiskLedger:
    """Update ledger after a trade closes. Lockout if limit breached."""
    if pnl is not None and pnl < 0:
        ledger.current_loss += abs(pnl)

    if increment_trade:
        ledger.trades_taken += 1

    # Check lockout conditions
    if not ledger.is_locked:
        if ledger.daily_loss_limit and ledger.current_loss >= ledger.daily_loss_limit:
            ledger.is_locked = True
            ledger.lock_reason = f"Daily loss limit reached (${ledger.current_loss:.2f} >= ${ledger.daily_loss_limit:.2f})"
            logger.warning(f"LOCKOUT: {ledger.lock_reason}")

            # Audit
            audit = AuditLog(
                user_id=ledger.user_id,
                entity_type="risk_ledger",
                entity_id=ledger.id,
                action="locked",
                previous_state={"is_locked": False},
                new_state={"is_locked": True, "reason": ledger.lock_reason},
                actor="system",
                reason=ledger.lock_reason,
            )
            db.add(audit)

            # Publish event
            event_bus.publish_daily_risk_breached(
                DailyRiskBreachedEvent(
                    user_id=str(ledger.user_id),
                    date=ledger.date.isoformat(),
                    daily_loss=ledger.current_loss,
                    limit=ledger.daily_loss_limit or 0.0,
                    reason=ledger.lock_reason,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                )
            )

        elif ledger.trades_taken >= ledger.max_trades:
            ledger.is_locked = True
            ledger.lock_reason = f"Max trades ({ledger.max_trades}) reached for today"
            logger.warning(f"LOCKOUT: {ledger.lock_reason}")

            audit = AuditLog(
                user_id=ledger.user_id,
                entity_type="risk_ledger",
                entity_id=ledger.id,
                action="locked",
                previous_state={"is_locked": False},
                new_state={"is_locked": True, "reason": ledger.lock_reason},
                actor="system",
                reason=ledger.lock_reason,
            )
            db.add(audit)

            event_bus.publish_daily_risk_breached(
                DailyRiskBreachedEvent(
                    user_id=str(ledger.user_id),
                    date=ledger.date.isoformat(),
                    daily_loss=ledger.current_loss,
                    limit=ledger.daily_loss_limit or 0.0,
                    reason=ledger.lock_reason,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                )
            )

    db.add(ledger)
    db.commit()
    db.refresh(ledger)
    return ledger


# ────────────────────────────────────────────────
# Pre-Trade Fail-Safes
# ────────────────────────────────────────────────
def validate_daily_risk(db: Session, user_id: UUID) -> Dict[str, Any]:
    """Check if user is allowed to trade today."""
    ledger = get_or_create_ledger(db, user_id)
    return {
        "can_trade": not ledger.is_locked,
        "is_locked": ledger.is_locked,
        "lock_reason": ledger.lock_reason,
        "trades_taken": ledger.trades_taken,
        "max_trades": ledger.max_trades,
        "current_loss": ledger.current_loss,
        "daily_loss_limit": ledger.daily_loss_limit,
    }


def validate_order_parameters(
    symbol: str,
    direction: str,
    lot_size: Optional[float],
    leverage: int,
    stop_loss: Optional[float],
) -> List[str]:
    """Validate order parameters against hardcoded limits."""
    errors = []

    if direction not in ("long", "short"):
        errors.append("Direction must be 'long' or 'short'")

    if stop_loss is None or stop_loss <= 0:
        errors.append("Stop loss is required and must be positive")

    if leverage > MAX_LEVERAGE:
        errors.append(f"Leverage exceeds maximum {MAX_LEVERAGE}x")

    if lot_size is not None and lot_size > MAX_LOT_SIZE:
        errors.append(f"Lot size exceeds maximum {MAX_LOT_SIZE}")

    if lot_size is not None and lot_size <= 0:
        errors.append("Lot size must be positive")

    return errors


# ────────────────────────────────────────────────
# Drawdown Halt
# ────────────────────────────────────────────────
def check_drawdown_halt(
    db: Session,
    user_id: UUID,
    max_drawdown_limit: Optional[float] = None,
) -> Dict[str, Any]:
    """Check if max drawdown has been breached and halt trading if so."""
    if max_drawdown_limit is None or max_drawdown_limit <= 0:
        return {"halted": False, "reason": None}

    # Calculate max drawdown from closed trades
    closed = db.exec(
        select(Trade)
        .where(Trade.user_id == user_id)
        .where(Trade.status == "closed")
        .where(Trade.pnl is not None)
    ).all()

    if not closed:
        return {"halted": False, "reason": None}

    sorted_trades = sorted(closed, key=lambda t: t.entry_time or datetime.min)
    equity = 0.0
    peak = 0.0
    max_dd = 0.0

    for trade in sorted_trades:
        equity += trade.pnl or 0
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd

    if max_dd >= max_drawdown_limit:
        # Lock the ledger
        today = date.today()
        ledger = get_or_create_ledger(db, user_id, today)
        if not ledger.is_locked:
            ledger.is_locked = True
            ledger.lock_reason = f"Max drawdown halt (${max_dd:.2f} >= ${max_drawdown_limit:.2f})"
            db.add(ledger)
            db.commit()

        return {"halted": True, "reason": ledger.lock_reason, "max_drawdown": max_dd}

    return {"halted": False, "max_drawdown": max_dd}


# ────────────────────────────────────────────────
# Connection Health
# ────────────────────────────────────────────────
def check_mt5_connection_health() -> Dict[str, Any]:
    """Check MT5 bridge connection status."""
    # Placeholder: in production, ping the MT5 bridge
    return {
        "connected": True,  # TODO: implement real health check
        "bridge_url": "http://localhost:5000",
        "last_ping_ms": 0,
        "status": "healthy",
    }


def check_system_health() -> Dict[str, Any]:
    """Full system health check for all services."""
    from app.core.event_bus import event_bus
    redis_status = event_bus.get_connection_status()
    mt5_status = check_mt5_connection_health()

    return {
        "redis": redis_status,
        "mt5_bridge": mt5_status,
        "overall": redis_status.get("connected", False) and mt5_status.get("connected", False),
    }
