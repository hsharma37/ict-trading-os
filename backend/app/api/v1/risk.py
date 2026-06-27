from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional
from datetime import date, datetime
from uuid import UUID

from app.database import get_db
from app.models.risk_ledger import DailyRiskLedger
from app.schemas.risk_schemas import RiskValidate, LotSizeRequest, RiskDailyStatus

router = APIRouter()


@router.post("/validate", summary="Validate trade against risk rules")
async def validate_trade(
    request: RiskValidate,
    db: Session = Depends(get_db),
):
    """
    Validate a proposed trade against:
    - Daily loss limit
    - Max trades per day
    - Leverage cap
    - Killzone alignment (future)
    """
    today = date.today()
    ledger = db.exec(
        select(DailyRiskLedger)
        .where(DailyRiskLedger.user_id == request.user_id)
        .where(DailyRiskLedger.date == today)
    ).first()

    if not ledger:
        # Create ledger for today if not exists
        ledger = DailyRiskLedger(user_id=request.user_id, date=today)
        db.add(ledger)
        db.commit()
        db.refresh(ledger)

    errors = []

    if ledger.is_locked:
        errors.append(f"Daily trading is locked: {ledger.lock_reason}")

    if request.risk_amount and ledger.daily_loss_limit:
        projected_loss = ledger.current_loss + request.risk_amount
        if projected_loss >= ledger.daily_loss_limit:
            errors.append(
                f"Risk ${request.risk_amount} would exceed daily loss limit "
                f"(${ledger.daily_loss_limit:.2f}, already lost ${ledger.current_loss:.2f})"
            )

    if ledger.trades_taken >= ledger.max_trades:
        errors.append(
            f"Max trades ({ledger.max_trades}) reached for today"
        )

    if request.leverage > 100:
        errors.append("Leverage exceeds maximum 100x")

    is_valid = len(errors) == 0

    return {
        "is_valid": is_valid,
        "errors": errors,
        "daily_status": {
            "trades_taken": ledger.trades_taken,
            "max_trades": ledger.max_trades,
            "current_loss": ledger.current_loss,
            "daily_loss_limit": ledger.daily_loss_limit,
            "is_locked": ledger.is_locked,
        },
    }


@router.post("/lot-size", summary="Calculate lot size with leverage awareness")
async def calculate_lot_size(request: LotSizeRequest):
    """
    Calculate lot size based on:
    - Account balance
    - Risk percentage (or fixed dollar amount)
    - Stop-loss distance in pips
    - Leverage multiplier
    - Symbol pip value
    """
    balance = request.account_balance
    risk_amount = request.risk_amount

    if not risk_amount and request.risk_percentage:
        risk_amount = balance * (request.risk_percentage / 100.0)

    if not risk_amount:
        raise HTTPException(status_code=400, detail="Provide risk_amount or risk_percentage")

    pip_value = request.pip_value or 1.0  # Default $1/pip for major forex pairs at 1 lot
    sl_pips = request.stop_loss_pips or 1.0

    # Base lot size (before leverage)
    if sl_pips > 0 and pip_value > 0:
        base_lot = risk_amount / (sl_pips * pip_value)
    else:
        base_lot = 0.0

    # Apply leverage
    leveraged_lot = base_lot * request.leverage
    leveraged_risk = risk_amount * request.leverage

    return {
        "account_balance": balance,
        "risk_amount": risk_amount,
        "risk_percentage": (risk_amount / balance * 100) if balance > 0 else 0,
        "stop_loss_pips": sl_pips,
        "leverage": request.leverage,
        "base_lot_size": round(base_lot, 6),
        "leveraged_lot_size": round(leveraged_lot, 6),
        "leveraged_risk_amount": round(leveraged_risk, 2),
        "position_value": round(leveraged_lot * balance, 2) if balance > 0 else 0,
    }


@router.get("/daily-status", summary="Get daily risk ledger status")
async def get_daily_status(user_id: UUID, db: Session = Depends(get_db)):
    today = date.today()
    ledger = db.exec(
        select(DailyRiskLedger)
        .where(DailyRiskLedger.user_id == user_id)
        .where(DailyRiskLedger.date == today)
    ).first()

    if not ledger:
        return {
            "date": today.isoformat(),
            "trades_taken": 0,
            "max_trades": 3,
            "current_loss": 0.0,
            "daily_loss_limit": None,
            "is_locked": False,
            "lock_reason": None,
        }

    return {
        "date": ledger.date.isoformat(),
        "trades_taken": ledger.trades_taken,
        "max_trades": ledger.max_trades,
        "current_loss": ledger.current_loss,
        "daily_loss_limit": ledger.daily_loss_limit,
        "is_locked": ledger.is_locked,
        "lock_reason": ledger.lock_reason,
    }
