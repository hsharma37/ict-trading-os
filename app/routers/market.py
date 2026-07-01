"""Market Data Router."""
from fastapi import APIRouter
from app.services.market_data import market_service
from app.services.instrument_config import get_all_instruments, get_instrument

router = APIRouter(prefix="/market", tags=["Market Data"])

@router.get("/price/{symbol}")
def get_price(symbol: str):
    return market_service.get_price(symbol)

@router.get("/prices")
def get_prices(symbols: str = None):
    if symbols:
        syms = [s.strip() for s in symbols.split(",")]
    else:
        syms = list(get_all_instruments().keys())
    return {"prices": {s: market_service.get_price(s) for s in syms}}

@router.post("/manual-price/{symbol}")
def set_manual_price(symbol: str, price: float, bid: float = None, ask: float = None):
    """Set a manual price override (e.g., from MT5 broker feed). Expires after 5 minutes."""
    return market_service.set_manual_price(symbol, price, bid, ask)

@router.delete("/manual-price/{symbol}")
def clear_manual_price(symbol: str):
    """Clear manual price override and return to Yahoo Finance."""
    market_service.clear_manual_price(symbol)
    return {"symbol": symbol, "status": "cleared"}

@router.get("/manual-price/{symbol}")
def get_manual_price(symbol: str):
    """Get manual price if set."""
    price = market_service.get_manual_price(symbol)
    if price:
        return price
    return {"symbol": symbol, "price": None, "source": "auto"}

@router.get("/history/{symbol}")
def get_history(symbol: str, timeframe: str = "1h", limit: int = 200):
    return {"symbol": symbol, "timeframe": timeframe, "candles": market_service.get_history(symbol, timeframe, limit)}

@router.get("/price-debug/{symbol}")
def price_debug(symbol: str):
    """Debug endpoint showing price chain and data source."""
    from app.services.price_service import price_service
    from app.services.market_data import market_service

    symbol = symbol.upper()
    config = get_instrument(symbol)
    yahoo_ticker = config.get("yahoo", config.get("ticker", symbol)) if config else symbol

    # Check manual override
    manual = market_service.get_manual_price(symbol)

    # Check persistent cache
    persistent = price_service._get_from_persistent(symbol)

    # Check in-memory cache
    mem_cached = price_service.cache.get(symbol)

    return {
        "symbol": symbol,
        "yahoo_ticker": yahoo_ticker,
        "instrument_config": {
            "label": config.get("label") if config else None,
            "digits": config.get("digits") if config else None,
            "kind": config.get("kind") if config else None,
            "leverage": config.get("leverage") if config else None,
        },
        "manual_override": manual,
        "persistent_cache": {
            "price": persistent.price if persistent else None,
            "timestamp": persistent.timestamp if persistent else None,
            "label": persistent.label if persistent else None,
        },
        "memory_cache": {
            "price": mem_cached.price if mem_cached else None,
            "timestamp": mem_cached.timestamp if mem_cached else None,
            "label": mem_cached.label if mem_cached else None,
        },
        "synthetic_base": price_service.SYNTHETIC_BASE.get(symbol),
        "current_live": market_service.get_price(symbol),
    }

@router.get("/instruments")
def get_instruments():
    return {"instruments": [
        {"symbol": "NQ1!", "name": "Nasdaq-100 Futures (E-mini)", "category": "index"},
        {"symbol": "ES1!", "name": "S&P 500 Futures (E-mini)", "category": "index"},
        {"symbol": "EURUSD", "name": "EUR/USD", "category": "forex"},
        {"symbol": "GBPUSD", "name": "GBP/USD", "category": "forex"},
        {"symbol": "XAUUSD", "name": "Gold Spot", "category": "metal"},
        {"symbol": "USDJPY", "name": "USD/JPY", "category": "forex"},
        {"symbol": "BTCUSD", "name": "Bitcoin", "category": "crypto"},
        {"symbol": "CL1!", "name": "Crude Oil Futures", "category": "commodity"}
    ]}
