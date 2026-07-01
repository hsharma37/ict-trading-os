"""Market Data Router."""
from fastapi import APIRouter
from app.services.market_data import market_service
from app.services.instrument_config import get_all_instruments

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

@router.get("/instruments")
def get_instruments():
    return {"instruments": [
        {"symbol": "NQ1!", "name": "Nasdaq Futures", "category": "index"},
        {"symbol": "ES1!", "name": "S&P Futures", "category": "index"},
        {"symbol": "EURUSD", "name": "EUR/USD", "category": "forex"},
        {"symbol": "GBPUSD", "name": "GBP/USD", "category": "forex"},
        {"symbol": "XAUUSD", "name": "Gold", "category": "metal"},
        {"symbol": "USDJPY", "name": "USD/JPY", "category": "forex"},
        {"symbol": "BTCUSD", "name": "Bitcoin", "category": "crypto"},
        {"symbol": "CL1!", "name": "Crude Oil", "category": "commodity"}
    ]}
