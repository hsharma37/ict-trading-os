"""
Risk service — business logic for position sizing, daily loss limits, and lockouts.

Core safety layer. All rules are deterministic, hardcoded, and never delegated to AI.
"""
from datetime import date
from sqlmodel import Session, select
from app.models.risk_ledger import DailyRiskLedger


MAX_LEVERAGE = 100
DEFAULT_MAX_TRADES = 3


def get_or_create_ledger(db: Session, user_id: str, ledger_date: date | None = None) -> DailyRiskLedger:
    if ledger_date is None:
        ledger_date = date.today()

    statement = (
        select(DailyRiskLedger)
        .where(DailyRiskLedger.user_id == user_id)
        .where(DailyRiskLedger.date == ledger_date)
    )
    ledger = db.exec(statement).first()

    if not ledger:
        ledger = DailyRiskLedger(
            user_id=user_id,
            date=ledger_date,
            max_trades=DEFAULT_MAX_TRADES,
        )
        db.add(ledger)
        db.commit()
        db.refresh(ledger)

    return ledger


def validate_trade_risk(
    db: Session,
    user_id: str,
    risk_amount: float,
    leverage: int,
) -> dict:
    """
    Validate a proposed trade against all risk rules.
    Returns {"is_valid": bool, "errors": list[str], "daily_status": dict}
    """
    ledger = get_or_create_ledger(db, user_id)
    errors = []

    if ledger.is_locked:
        errors.append(f"Daily trading locked: {ledger.lock_reason}")

    if ledger.daily_loss_limit and risk_amount:
        projected = ledger.current_loss + risk_amount
        if projected >= ledger.daily_loss_limit:
            errors.append(
                f"Risk ${risk_amount:.2f} would exceed limit "
                f"(${ledger.daily_loss_limit:.2f})"
            )

    if ledger.trades_taken >= ledger.max_trades:
        errors.append(f"Max {ledger.max_trades} trades reached for today")

    if leverage > MAX_LEVERAGE:
        errors.append(f"Leverage {leverage}x exceeds max {MAX_LEVERAGE}x")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "daily_status": {
            "trades_taken": ledger.trades_taken,
            "max_trades": ledger.max_trades,
            "current_loss": ledger.current_loss,
            "daily_loss_limit": ledger.daily_loss_limit,
            "is_locked": ledger.is_locked,
        },
    }


def calculate_lot_size(
    account_balance: float,
    risk_amount: float | None,
    risk_percentage: float | None,
    stop_loss_pips: float,
    leverage: int,
    pip_value: float = 1.0,
) -> dict:
    """
    Calculate lot size with leverage awareness.
    """
    if risk_amount is None and risk_percentage:
        risk_amount = account_balance * (risk_percentage / 100.0)
    elif risk_amount is None:
        raise ValueError("Provide risk_amount or risk_percentage")

    base_lot = risk_amount / (stop_loss_pips * pip_value) if stop_loss_pips > 0 and pip_value > 0 else 0.0
    leveraged_lot = base_lot * leverage
    leveraged_risk = risk_amount * leverage

    return {
        "account_balance": account_balance,
        "risk_amount": risk_amount,
        "risk_percentage": round(risk_amount / account_balance * 100, 2) if account_balance > 0 else 0,
        "stop_loss_pips": stop_loss_pips,
        "leverage": leverage,
        "base_lot_size": round(base_lot, 6),
        "leveraged_lot_size": round(leveraged_lot, 6),
        "leveraged_risk_amount": round(leveraged_risk, 2),
        "position_value": round(leveraged_lot * account_balance, 2) if account_balance > 0 else 0,
    }
