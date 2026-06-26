"""Signals Router."""
from fastapi import APIRouter
from app.services.signal_engine import signal_engine

router = APIRouter(prefix="/signals", tags=["Signals"])

@router.get("/analyze/{symbol}")
def analyze_signal(symbol: str):
    signal = signal_engine.analyze(symbol)
    if not signal:
        return {"symbol": symbol, "signal": None, "message": "No valid signal. Setup below confluence threshold."}
    return {"symbol": symbol, "signal": signal}

@router.get("/active")
def active_signals(symbol: str = None):
    return {"signals": signal_engine.get_active(symbol), "count": len(signal_engine.get_active(symbol))}

@router.get("/stats/{symbol}")
def signal_stats(symbol: str):
    return signal_engine.get_stats(symbol)

@router.post("/scan")
def scan_all():
    symbols = ["NQ1!", "ES1!", "EURUSD", "GBPUSD", "XAUUSD", "USDJPY", "BTCUSD", "CL1!"]
    results = []
    for sym in symbols:
        sig = signal_engine.analyze(sym)
        if sig: results.append(sig)
    return {"scanned": len(symbols), "signals_found": len(results), "signals": results}
