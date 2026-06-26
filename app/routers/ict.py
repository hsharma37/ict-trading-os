"""ICT Analysis Router."""
from fastapi import APIRouter
from app.services.market_data import market_service
from app.services.ict_engine import ict_engine

router = APIRouter(prefix="/ict", tags=["ICT Analysis"])

@router.get("/analyze/{symbol}")
def analyze(symbol: str, timeframe: str = "15m"):
    candles = market_service.get_history(symbol, timeframe, 100)
    if not candles:
        return {"error": "No data"}
    return ict_engine.analyze(candles, symbol, timeframe)

@router.get("/analyze/multi/{symbol}")
def analyze_multi(symbol: str):
    result = {"symbol": symbol, "timeframes": {}}
    for tf in ["1h", "15m", "5m"]:
        candles = market_service.get_history(symbol, tf, 100)
        if candles:
            result["timeframes"][tf] = ict_engine.analyze(candles, symbol, tf)

    # Generate recommendation
    htf = result["timeframes"].get("1h", {})
    score = sum(t.get("confluence_score", 0) for t in result["timeframes"].values())
    bias = htf.get("current_bias", "NEUTRAL")
    action = "WAIT"
    reason = "No clear setup"
    if bias == "BULLISH" and score >= 8: action = "CONSIDER_LONG"; reason = "Strong bullish confluence"
    elif bias == "BEARISH" and score >= 8: action = "CONSIDER_SHORT"; reason = "Strong bearish confluence"
    elif score >= 5: action = "WATCH"; reason = "Developing setup"

    result["recommendation"] = {"bias": bias, "total_confluence": score, "action": action, "reason": reason}
    return result

@router.get("/entry-zone/{symbol}")
def entry_zone(symbol: str, bias: str, timeframe: str = "15m"):
    candles = market_service.get_history(symbol, timeframe, 100)
    if not candles: return {"error": "No data"}
    analysis = ict_engine.analyze(candles, symbol, timeframe)
    entry = ict_engine.calculate_entry(analysis["patterns"], bias, analysis["current_price"])
    if not entry: return {"error": "No clear entry zone", "bias": bias}
    return {"symbol": symbol, "bias": bias, "current_price": analysis["current_price"], "entry_zone": entry}
