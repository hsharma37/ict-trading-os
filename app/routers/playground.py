"""
Playground Router — Live market data, price charts, and instrument analysis.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.services.price_service import price_service
from app.services.quote_service import get_quote
from app.services.instrument_config import get_all_instruments, get_instrument, INSTRUMENTS

router = APIRouter(prefix="/playground", tags=["Playground"])

# Prices older than this are flagged stale so the UI never shows them as live.
STALE_AFTER_SECONDS = 120


def derive_source(label: str) -> str:
    """Classify a price's provenance from its label suffix.

    "synthetic" is demo/fallback data and must never be shown as live;
    "scraped" is a best-effort alternate source; otherwise it's the Yahoo feed.
    """
    l = (label or "").lower()
    if "(synthetic)" in l:
        return "synthetic"
    if any(s in l for s in ("(kitco)", "(gold.org)", "(investing.com)", "(scraped)")):
        return "scraped"
    return "yahoo"


def is_stale(timestamp: str, max_age_s: int = STALE_AFTER_SECONDS) -> bool:
    """True when the price timestamp is older than max_age_s."""
    try:
        ts = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        now = datetime.now(ts.tzinfo) if ts.tzinfo else datetime.utcnow()
        return (now - ts).total_seconds() > max_age_s
    except (ValueError, TypeError):
        return False


class PriceResponse(BaseModel):
    symbol: str
    label: str
    price: float
    change: float
    change_percent: float
    high: float
    low: float
    open: float
    volume: int
    prev_close: float
    timestamp: str
    kind: str
    digits: int
    source: str = "yahoo"
    stale: bool = False


class AllPricesResponse(BaseModel):
    prices: List[PriceResponse]
    timestamp: str


class InstrumentInfo(BaseModel):
    symbol: str
    ticker: str
    label: str
    kind: str
    digits: int
    pip_digits: int
    pip_val: float
    mult: int
    leverage: int
    contract_size: int
    tick_size: float
    tick_value: float
    unit: str


# ────────────────────────────────────────────────
# Endpoints
# ────────────────────────────────────────────────

def _price_response_from_quote(q: dict) -> PriceResponse:
    """Adapt a canonical quote_service quote into the playground PriceResponse."""
    return PriceResponse(
        symbol=q["symbol"],
        label=q.get("label", q["symbol"]),
        price=q.get("price", 0),
        change=q.get("change", 0),
        change_percent=q.get("change_percent", 0),
        high=q.get("high", q.get("price", 0)),
        low=q.get("low", q.get("price", 0)),
        open=q.get("open", q.get("price", 0)),
        volume=q.get("volume", 0),
        prev_close=q.get("prev_close", q.get("price", 0)),
        timestamp=q.get("timestamp") or "",
        kind=q.get("kind", ""),
        digits=q.get("digits", 5),
        source=q.get("source", "unavailable"),
        stale=bool(q.get("stale", False)),
    )


@router.get("/prices", response_model=AllPricesResponse)
def get_all_prices():
    """Fetch live prices for all configured instruments (single source of truth)."""
    responses = [
        _price_response_from_quote(get_quote(symbol))
        for symbol in get_all_instruments().keys()
    ]
    return AllPricesResponse(
        prices=responses,
        timestamp=responses[0].timestamp if responses else "",
    )


@router.get("/price/{symbol}", response_model=PriceResponse)
def get_price(symbol: str):
    """Fetch live price for a specific instrument (single source of truth)."""
    symbol = symbol.upper()
    if not get_instrument(symbol):
        raise HTTPException(status_code=404, detail=f"Instrument {symbol} not found")
    return _price_response_from_quote(get_quote(symbol))


@router.get("/instruments", response_model=List[InstrumentInfo])
def get_instruments():
    """List all available instruments with their configuration."""
    instruments = get_all_instruments()
    return [
        InstrumentInfo(
            symbol=symbol,
            ticker=config.get("ticker", ""),
            label=config.get("label", ""),
            kind=config.get("kind", ""),
            digits=config.get("digits", 5),
            pip_digits=config.get("pip_digits", 4),
            pip_val=config.get("pip_val", 1.0),
            mult=config.get("mult", 1),
            leverage=config.get("leverage", 100),
            contract_size=config.get("contract_size", 1),
            tick_size=config.get("tick_size", 0.00001),
            tick_value=config.get("tick_value", 1.0),
            unit=config.get("unit", "lot"),
        )
        for symbol, config in instruments.items()
    ]
