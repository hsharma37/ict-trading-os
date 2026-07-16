"""ICT Analysis Router."""
from fastapi import APIRouter
from app.services.market_data import market_service, history_is_synthetic
from app.services.ict_engine import ict_engine
from app.services.backtest_service import _pip_size

router = APIRouter(prefix="/ict", tags=["ICT Analysis"])


@router.get("/levels/{symbol}")
def levels(symbol: str, timeframes: str = "1h,15m,5m"):
    """Live ICT price zones for the symbol — every detected order block, FVG,
    liquidity pool and structure level projected against the current price, with
    distance and whether price is above / below / inside each zone. This is the
    'what are the actual tradeable levels right now' view."""
    symbol = symbol.upper()
    tfs = [t.strip() for t in timeframes.split(",") if t.strip()]
    pip = _pip_size(symbol)
    price = None
    synthetic = False
    zones = []
    dealing_range = None
    for tf in tfs:
        candles = market_service.get_history(symbol, tf, 150)
        if not candles:
            continue
        if history_is_synthetic(candles):
            synthetic = True
        a = ict_engine.analyze(candles, symbol, tf)
        price = a.get("current_price") or price
        if tf == tfs[0]:
            dealing_range = ict_engine.range_levels(candles)
        for p in a.get("patterns", []):
            meta = p.get("metadata", {})
            typ = p["type"]
            if typ == "FVG":
                hi, lo = meta.get("top"), meta.get("bottom")
                kind = "zone"
            elif typ == "OB":
                hi, lo = meta.get("ob_high"), meta.get("ob_low")
                kind = "zone"
            else:  # MSS / LIQUIDITY are single price lines
                hi = lo = p.get("price_level")
                kind = "line"
            if hi is None or lo is None:
                continue
            if hi < lo:
                hi, lo = lo, hi
            zones.append({"type": typ, "kind": kind, "direction": p["direction"], "timeframe": tf,
                          "high": round(float(hi), 5), "low": round(float(lo), 5),
                          "mid": round(float((hi + lo) / 2), 5), "confidence": p.get("confidence")})

    # De-duplicate near-identical zones (same type/dir within ~half a pip on the mid).
    tol = pip * 0.5
    deduped = []
    for z in sorted(zones, key=lambda z: z["mid"]):
        if any(d["type"] == z["type"] and d["direction"] == z["direction"]
               and abs(d["mid"] - z["mid"]) <= tol for d in deduped):
            continue
        deduped.append(z)

    # Annotate each zone vs the live price.
    for z in deduped:
        if price is None:
            continue
        if z["low"] <= price <= z["high"]:
            z["position"], z["distance_pips"] = "inside", 0.0
        elif z["low"] > price:
            z["position"], z["distance_pips"] = "above", round((z["low"] - price) / pip, 1)
        else:
            z["position"], z["distance_pips"] = "below", round((price - z["high"]) / pip, 1)
        z["distance_pct"] = round(abs(z["mid"] - price) / price * 100, 3) if price else None

    deduped.sort(key=lambda z: z.get("distance_pips", 9e9))
    total = len(deduped)
    nearest = deduped[:18]  # keep it actionable — nearest zones on each side
    return {
        "symbol": symbol, "current_price": price, "synthetic": synthetic,
        "dealing_range": dealing_range,
        "premium_discount": ("premium" if dealing_range and price and price > dealing_range["equilibrium"]
                             else "discount" if dealing_range and price else "unknown"),
        "zones": nearest, "count": len(nearest), "total_detected": total,
    }

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
