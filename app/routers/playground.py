"""
Playground Router — Live market data, price charts, and instrument analysis.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.services.price_service import price_service
from app.services.instrument_config import get_all_instruments, INSTRUMENTS

router = APIRouter(prefix="/playground", tags=["Playground"])


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

@router.get("/prices", response_model=AllPricesResponse)
def get_all_prices():
    """Fetch live prices for all configured instruments."""
    prices = price_service.fetch_all_prices()
    return AllPricesResponse(
        prices=[
            PriceResponse(
                symbol=p.symbol,
                label=p.label,
                price=p.price,
                change=p.change,
                change_percent=p.change_percent,
                high=p.high,
                low=p.low,
                open=p.open,
                volume=p.volume,
                prev_close=p.prev_close,
                timestamp=p.timestamp,
                kind=p.kind,
                digits=p.digits,
            )
            for p in prices.values()
        ],
        timestamp=prices[list(prices.keys())[0]].timestamp if prices else 0,
    )


@router.get("/price/{symbol}", response_model=PriceResponse)
def get_price(symbol: str):
    """Fetch live price for a specific instrument."""
    data = price_service.fetch_price(symbol.upper())
    if not data:
        raise HTTPException(status_code=404, detail=f"Instrument {symbol} not found")
    return PriceResponse(
        symbol=data.symbol,
        label=data.label,
        price=data.price,
        change=data.change,
        change_percent=data.change_percent,
        high=data.high,
        low=data.low,
        open=data.open,
        volume=data.volume,
        prev_close=data.prev_close,
        timestamp=data.timestamp,
        kind=data.kind,
        digits=data.digits,
    )


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
