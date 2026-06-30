"""Quant Lab Router."""
from fastapi import APIRouter, HTTPException
from app.core.database import db
from app.services.quant_service import quant_service
from app.services.research_service import research_service
from app.services.market_data import market_service
from datetime import datetime
import statistics

router = APIRouter(prefix="/quant", tags=["Quant Lab"])

@router.get("/metrics")
def get_metrics():
    trades = db.find("trades", status="CLOSED")
    trade_dicts = [{"realized_pnl": t.get("realized_pnl", 0), "symbol": t.get("symbol", "")} for t in trades]
    return quant_service.compute_metrics(trade_dicts)

@router.get("/kelly")
def get_kelly():
    trades = db.find("trades", status="CLOSED")
    trade_dicts = [{"realized_pnl": t.get("realized_pnl", 0)} for t in trades]
    kelly = quant_service.compute_kelly(trade_dicts)
    if not kelly: return {"error": "Need 5+ closed trades with wins and losses"}
    return kelly

@router.post("/monte-carlo")
def monte_carlo(n_simulations: int = 1000, n_trades: int = 100):
    trades = db.find("trades", status="CLOSED")
    trade_dicts = [{"realized_pnl": t.get("realized_pnl", 0)} for t in trades]
    return quant_service.monte_carlo(trade_dicts, n_simulations, n_trades)

@router.get("/coach")
def get_coach():
    trades = db.find("trades", status="CLOSED")
    trade_dicts = [{"realized_pnl": t.get("realized_pnl", 0), "symbol": t.get("symbol", "")} for t in trades]
    from datetime import datetime
    return {
        "recommendations": quant_service.coach(trade_dicts),
        "summary": "Performance coaching active.",
        "last_updated": datetime.utcnow().isoformat()
    }


@router.get("/trend/{symbol}", summary="Trend analysis: SMA, momentum")
def trend_analysis(symbol: str):
    """Return SMA crossover and momentum indicators."""
    candles = market_service.get_history(symbol, "1h", 100)
    if not candles:
        raise HTTPException(status_code=404, detail="No data available")
    closes = [c["close"] for c in candles if c.get("close")]
    if len(closes) < 50:
        raise HTTPException(status_code=404, detail="Insufficient data")
    sma20 = sum(closes[-20:]) / 20
    sma50 = sum(closes[-50:]) / 50
    momentum = ((closes[-1] - closes[-10]) / closes[-10] * 100) if closes[-10] > 0 else 0
    trend = "BULLISH" if sma20 > sma50 * 1.001 else "BEARISH" if sma20 < sma50 * 0.999 else "NEUTRAL"
    return {
        "symbol": symbol,
        "trend": trend,
        "sma20": round(sma20, 5),
        "sma50": round(sma50, 5),
        "momentum_10h": round(momentum, 3),
        "price": round(closes[-1], 5),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/volatility/{symbol}", summary="Volatility analysis: ATR, Bollinger Bands")
def volatility_analysis(symbol: str):
    """Return ATR and Bollinger Bands for a symbol."""
    candles = market_service.get_history(symbol, "1h", 50)
    if not candles or len(candles) < 20:
        raise HTTPException(status_code=404, detail="No data available")
    closes = [c["close"] for c in candles if c.get("close")]
    highs = [c["high"] for c in candles if c.get("high")]
    lows = [c["low"] for c in candles if c.get("low")]
    if len(closes) < 20:
        raise HTTPException(status_code=404, detail="Insufficient data")
    # SMA 20
    sma20 = sum(closes[-20:]) / 20
    # Std dev
    variance = sum((c - sma20) ** 2 for c in closes[-20:]) / 20
    std = variance ** 0.5
    upper = sma20 + 2 * std
    lower = sma20 - 2 * std
    # ATR 14
    trs = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    atr = sum(trs[-14:]) / 14 if len(trs) >= 14 else sum(trs) / len(trs)
    current = closes[-1]
    dist_to_upper = round((upper - current) / current * 100, 3) if current > 0 else 0
    dist_to_lower = round((current - lower) / current * 100, 3) if current > 0 else 0
    regime = "EXTREME" if atr > sma20 * 0.02 else "HIGH" if atr > sma20 * 0.01 else "NORMAL"
    return {
        "symbol": symbol,
        "atr": round(atr, 5),
        "sma20": round(sma20, 5),
        "upper_band": round(upper, 5),
        "lower_band": round(lower, 5),
        "current_price": round(current, 5),
        "dist_to_upper_pct": dist_to_upper,
        "dist_to_lower_pct": dist_to_lower,
        "regime": regime,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/levels/{symbol}", summary="Support / Resistance levels")
def levels_analysis(symbol: str):
    """Return swing high/low based support and resistance."""
    candles = market_service.get_history(symbol, "1h", 50)
    if not candles or len(candles) < 20:
        raise HTTPException(status_code=404, detail="No data available")
    recent = candles[-20:]
    highs = [c["high"] for c in recent]
    lows = [c["low"] for c in recent]
    swing_highs = []
    swing_lows = []
    for i in range(1, len(recent) - 1):
        if recent[i]["high"] > recent[i - 1]["high"] and recent[i]["high"] > recent[i + 1]["high"]:
            swing_highs.append(recent[i]["high"])
        if recent[i]["low"] < recent[i - 1]["low"] and recent[i]["low"] < recent[i + 1]["low"]:
            swing_lows.append(recent[i]["low"])
    resistance = max(swing_highs) if swing_highs else max(highs)
    support = min(swing_lows) if swing_lows else min(lows)
    current = candles[-1]["close"]
    return {
        "symbol": symbol,
        "support": round(support, 5),
        "resistance": round(resistance, 5),
        "current_price": round(current, 5),
        "dist_to_support_pct": round((current - support) / current * 100, 3) if current > 0 else 0,
        "dist_to_resistance_pct": round((resistance - current) / current * 100, 3) if current > 0 else 0,
        "swing_highs": swing_highs[:5],
        "swing_lows": swing_lows[:5],
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/session/{symbol}", summary="Session analysis for symbol")
def session_analysis(symbol: str):
    """Return best trading hours and session timing."""
    # Simulated session data based on symbol kind
    kind = "fx"
    if symbol in ["NQ1!", "ES1!"]:
        kind = "index"
    elif symbol in ["XAUUSD", "CL1!"]:
        kind = "commodity"
    elif symbol == "BTCUSD":
        kind = "crypto"
    now = datetime.utcnow()
    hour = now.hour
    # Determine if in a kill zone
    in_london = 7 <= hour <= 10
    in_ny_am = 13 <= hour <= 15
    in_ny_pm = 17 <= hour <= 19
    in_killzone = in_london or in_ny_am or in_ny_pm
    if kind == "crypto":
        in_killzone = True  # Crypto trades 24/7
    elif kind == "index":
        in_killzone = 13 <= hour <= 16  # US cash open
    best_sessions = []
    if in_london: best_sessions.append("London Open")
    if in_ny_am: best_sessions.append("NY AM")
    if in_ny_pm: best_sessions.append("NY PM")
    if not best_sessions:
        best_sessions = ["Asian Range (lower probability)"]
    return {
        "symbol": symbol,
        "kind": kind,
        "utc_hour": hour,
        "in_killzone": in_killzone,
        "best_sessions": best_sessions,
        "recommendation": "OPTIMAL" if in_killzone else "CAUTION",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/decision/{symbol}", summary="Should I trade? Decision helper")
def decision_helper(symbol: str, direction: str = "long"):
    """Aggregate analysis and give a trade recommendation."""
    try:
        trend = trend_analysis(symbol)
    except Exception:
        trend = {"trend": "NEUTRAL", "momentum_10h": 0}
    try:
        vol = volatility_analysis(symbol)
    except Exception:
        vol = {"regime": "NORMAL", "dist_to_upper_pct": 0, "dist_to_lower_pct": 0}
    try:
        levels = levels_analysis(symbol)
    except Exception:
        levels = {"support": None, "resistance": None, "dist_to_support_pct": 0, "dist_to_resistance_pct": 0}
    try:
        sess = session_analysis(symbol)
    except Exception:
        sess = {"in_killzone": False, "recommendation": "CAUTION"}
    direction = direction.lower()
    # Trend alignment
    trend_aligned = False
    if direction == "long" and trend["trend"] in ("BULLISH", "NEUTRAL"):
        trend_aligned = True
    elif direction == "short" and trend["trend"] in ("BEARISH", "NEUTRAL"):
        trend_aligned = True
    # SR proximity
    sr_proximity = 0
    if direction == "long":
        sr_proximity = levels.get("dist_to_support_pct", 0)
    else:
        sr_proximity = levels.get("dist_to_resistance_pct", 0)
    sr_good = sr_proximity < 2.0
    # Volatility
    vol_regime = vol.get("regime", "NORMAL")
    vol_safe = vol_regime == "NORMAL"
    # Session
    session_good = sess.get("in_killzone", False)
    # Score
    score = 0
    if trend_aligned: score += 2
    if sr_good: score += 2
    if vol_safe: score += 1
    if session_good: score += 2
    recommendation = "AVOID"
    if score >= 6:
        recommendation = "STRONG"
    elif score >= 4:
        recommendation = "MODERATE"
    elif score >= 2:
        recommendation = "WEAK"
    return {
        "symbol": symbol,
        "direction": direction,
        "recommendation": recommendation,
        "score": score,
        "max_score": 7,
        "trend_alignment": "ALIGNED" if trend_aligned else "MISALIGNED",
        "trend": trend["trend"],
        "sr_proximity_pct": sr_proximity,
        "sr_assessment": "CLOSE" if sr_good else "FAR",
        "volatility_regime": vol_regime,
        "volatility_assessment": "SAFE" if vol_safe else "ELEVATED",
        "session": sess.get("recommendation", "CAUTION"),
        "session_optimal": session_good,
        "timestamp": datetime.utcnow().isoformat(),
    }
