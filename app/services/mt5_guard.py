"""Validation guardrails for MT5 trade execution.

The MT5 proxy forwards orders to a local bridge that can place real trades, so
every order intent must pass deterministic safety checks first: known symbol,
sane lot size, valid direction, and (when a reference price is known)
correctly-sided stop-loss / take-profit.
"""
from typing import Optional

from app.core.config import settings
from app.services.instrument_config import get_all_instruments, get_instrument


class Mt5ValidationError(ValueError):
    """Raised when a trade intent fails a safety check."""


def allowed_symbols() -> set:
    """Symbols permitted for MT5 execution (config allowlist, else all configured)."""
    raw = (settings.MT5_ALLOWED_SYMBOLS or "").strip()
    if raw:
        return {s.strip().upper() for s in raw.split(",") if s.strip()}
    return {s.upper() for s in get_all_instruments().keys()}


def validate_trade(
    symbol: str,
    direction: str,
    lot_size,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    reference_price: Optional[float] = None,
) -> dict:
    """Validate a trade intent and return a normalized payload.

    Raises Mt5ValidationError with a human-readable message on any violation.
    Symbol/direction/lot checks are network-free; SL/TP side checks apply only
    when reference_price (the current market price) is provided.
    """
    symbol = (symbol or "").upper()

    allowed = allowed_symbols()
    if symbol not in allowed:
        raise Mt5ValidationError(
            f"Symbol '{symbol}' is not allowed for MT5 execution. "
            f"Allowed: {', '.join(sorted(allowed))}."
        )

    d = (direction or "").strip().lower()
    if d not in {"long", "short", "buy", "sell"}:
        raise Mt5ValidationError(f"Invalid direction '{direction}'. Use long/short (or buy/sell).")
    is_buy = d in {"long", "buy"}

    try:
        lot = float(lot_size)
    except (TypeError, ValueError):
        raise Mt5ValidationError("lot_size must be a number.")
    if lot <= 0:
        raise Mt5ValidationError("lot_size must be greater than 0.")
    if lot > settings.MT5_MAX_LOT:
        raise Mt5ValidationError(f"lot_size {lot} exceeds the maximum allowed lot {settings.MT5_MAX_LOT}.")

    config = get_instrument(symbol) or {}
    min_qty = config.get("min_qty", 0.01)
    if lot < min_qty:
        raise Mt5ValidationError(f"lot_size {lot} is below the minimum {min_qty} for {symbol}.")

    if stop_loss is not None and stop_loss <= 0:
        raise Mt5ValidationError("stop_loss must be a positive price.")
    if take_profit is not None and take_profit <= 0:
        raise Mt5ValidationError("take_profit must be a positive price.")

    if settings.MT5_REQUIRE_SL and stop_loss is None:
        raise Mt5ValidationError("A stop_loss is required for MT5 orders (MT5_REQUIRE_SL is enabled).")

    # Side-aware SL/TP validation relative to the current price.
    if reference_price and reference_price > 0:
        if is_buy:
            if stop_loss is not None and stop_loss >= reference_price:
                raise Mt5ValidationError("For a long, stop_loss must be below the current price.")
            if take_profit is not None and take_profit <= reference_price:
                raise Mt5ValidationError("For a long, take_profit must be above the current price.")
        else:
            if stop_loss is not None and stop_loss <= reference_price:
                raise Mt5ValidationError("For a short, stop_loss must be above the current price.")
            if take_profit is not None and take_profit >= reference_price:
                raise Mt5ValidationError("For a short, take_profit must be below the current price.")

    return {
        "symbol": symbol,
        "direction": "long" if is_buy else "short",
        "lot_size": lot,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
    }
