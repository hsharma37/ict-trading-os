from fastapi import APIRouter, Depends
from sqlmodel import Session
from uuid import UUID

from app.database import get_db
from app.services.fail_safe_service import (
    validate_daily_risk,
    check_drawdown_halt,
    check_system_health,
    check_mt5_connection_health,
)

router = APIRouter()


@router.get("/daily-risk", summary="Daily risk status")
async def daily_risk_status(
    user_id: UUID,
    db: Session = Depends(get_db),
):
    """Check if user is allowed to trade today (lockout status)."""
    return validate_daily_risk(db, user_id)


@router.get("/drawdown", summary="Drawdown halt check")
async def drawdown_halt(
    user_id: UUID,
    max_drawdown_limit: float = 500.0,
    db: Session = Depends(get_db),
):
    """Check if max drawdown has been breached and trading should be halted."""
    return check_drawdown_halt(db, user_id, max_drawdown_limit)


@router.get("/system", summary="System health check")
async def system_health():
    """Full system health check (Redis, MT5 bridge, database)."""
    return check_system_health()


@router.get("/mt5", summary="MT5 bridge health")
async def mt5_health():
    """MT5 bridge connection status."""
    return check_mt5_connection_health()
