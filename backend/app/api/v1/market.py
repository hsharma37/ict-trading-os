from fastapi import APIRouter, HTTPException
import httpx
from typing import Optional

from app.config import settings

router = APIRouter()


@router.get("/price/{symbol}", summary="Get live price from Yahoo Finance")
async def get_price(symbol: str):
    """
    Fetch live price data for a symbol via Yahoo Finance.
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol.upper())
        info = ticker.info
        hist = ticker.history(period="1d")
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No data for symbol {symbol}")
        latest = hist.iloc[-1]
        return {
            "symbol": symbol.upper(),
            "price": latest["Close"],
            "open": latest["Open"],
            "high": latest["High"],
            "low": latest["Low"],
            "volume": int(latest["Volume"]),
            "timestamp": str(latest.name),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Price fetch error: {str(e)}")


@router.get("/history/{symbol}", summary="Get candle history")
async def get_history(
    symbol: str,
    timeframe: str = "1d",
    period: str = "1mo",
):
    """
    Fetch candlestick history for a symbol.
    timeframe: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol.upper())
        hist = ticker.history(period=period, interval=timeframe)
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No history for {symbol}")
        candles = []
        for idx, row in hist.iterrows():
            candles.append({
                "timestamp": str(idx),
                "open": round(row["Open"], 5),
                "high": round(row["High"], 5),
                "low": round(row["Low"], 5),
                "close": round(row["Close"], 5),
                "volume": int(row["Volume"]),
            })
        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "period": period,
            "candles": candles,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"History fetch error: {str(e)}")
