"""Market Data Router."""
from fastapi import APIRouter
from app.services.market_data import market_service

router = APIRouter(prefix="/market", tags=["Market Data"])

@router.get("/price/{symbol}")
def get_price(symbol: str):
    return market_service.get_price(symbol)

@router.get("/prices")
def get_prices(symbols: str = "NQ1!,ES1!,EURUSD,XAUUSD,BTCUSD"):
    syms = [s.strip() for s in symbols.split(",")]
    return {"prices": {s: market_service.get_price(s) for s in syms}}

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
