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
    # The price feed is restricted to the instruments the app supports — any
    # requested symbol outside the configured list is ignored, so the feed never
    # fetches arbitrary (or non-broker) symbols.
    allowed = list(get_all_instruments().keys())
    if symbols:
        requested = [s.strip().upper() for s in symbols.split(",")]
        syms = [s for s in requested if s in allowed]
    else:
        syms = allowed
    quotes = [market_service.get_price(s) for s in syms]
    return {"prices": quotes, "timestamp": quotes[0]["timestamp"] if quotes else None}

@router.post("/manual-price/{symbol}")
def set_manual_price(symbol: str, price: float, bid: float = None, ask: float = None):
    """Set a manual price override (e.g., from MT5 broker feed). Expires after 5 minutes."""
    return market_service.set_manual_price(symbol, price, bid, ask)

@router.delete("/manual-price/{symbol}")
def clear_manual_price(symbol: str):
    """Clear manual price override and return to the MT5 bridge feed."""
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
    """Debug endpoint: the MT5 bridge is the single price/candle source."""
    from app.services.bridge_config import get_bridge_url
    from app.services.mt5_price_service import mt5_price_service

    symbol = symbol.upper()
    config = get_instrument(symbol)
    return {
        "symbol": symbol,
        "provider": "mt5-bridge (single source — no Yahoo/OANDA fallback)",
        "bridge_configured": bool(get_bridge_url()),
        "mt5_symbol": mt5_price_service._mt5_symbol(symbol),
        "instrument_config": {
            "label": config.get("label") if config else None,
            "digits": config.get("digits") if config else None,
            "kind": config.get("kind") if config else None,
            "leverage": config.get("leverage") if config else None,
        },
        "manual_override": market_service.get_manual_price(symbol),
        "current_live": market_service.get_price(symbol),
    }

@router.get("/instruments")
def get_instruments():
    # Derived from the single instrument config so it never drifts from the feed.
    return {"instruments": [
        {"symbol": sym, "name": cfg.get("label", sym), "category": cfg.get("kind", "")}
        for sym, cfg in get_all_instruments().items()
    ]}
