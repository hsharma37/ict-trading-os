"""ICT Pattern Detection Engine."""
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime

class ICTPatternEngine:
    def analyze(self, candles: List[Dict], symbol: str, timeframe: str) -> Dict:
        if len(candles) < 20:
            return {"patterns": [], "bias": "NEUTRAL", "confluence_score": 0}

        opens = np.array([c["open"] for c in candles])
        highs = np.array([c["high"] for c in candles])
        lows = np.array([c["low"] for c in candles])
        closes = np.array([c["close"] for c in candles])
        times = [c["time"] for c in candles]

        patterns = []
        swings = self._detect_swings(highs, lows, times)
        patterns.extend(self._detect_mss(closes, highs, lows, swings, times))
        patterns.extend(self._detect_fvg(opens, highs, lows, closes, times))
        patterns.extend(self._detect_ob(opens, highs, lows, closes, times))
        patterns.extend(self._detect_liquidity(highs, lows, swings, times))

        bias = self._determine_bias(patterns, closes[-1])
        confluences = self._calculate_confluences(patterns, bias)

        return {
            "symbol": symbol, "timeframe": timeframe, "patterns": patterns,
            "current_bias": bias, "confluence_score": confluences["score"],
            "active_confluences": confluences["checks"], "current_price": float(closes[-1]),
            "premium_discount": self._premium_discount(closes[-1], swings)
        }

    def _detect_swings(self, highs, lows, times, lookback=5):
        swings = []
        for i in range(lookback, len(highs) - lookback):
            if highs[i] == max(highs[i-lookback:i+lookback+1]):
                swings.append({"index": i, "time": times[i], "price": float(highs[i]), "type": "high"})
            elif lows[i] == min(lows[i-lookback:i+lookback+1]):
                swings.append({"index": i, "time": times[i], "price": float(lows[i]), "type": "low"})
        return swings

    def _detect_mss(self, closes, highs, lows, swings, times):
        patterns = []
        if len(swings) < 3: return patterns
        recent = swings[-10:]
        for i in range(2, len(recent)):
            if recent[i-1]["type"] == "high" and recent[i-2]["type"] == "low":
                idx = recent[i]["index"]
                if closes[idx] > recent[i-1]["price"]:
                    candle_size = abs(closes[idx] - closes[idx-1])
                    avg_size = np.mean([abs(closes[j] - closes[j-1]) for j in range(max(0, idx-10), idx)])
                    if candle_size > avg_size * 1.5:
                        patterns.append({"type": "MSS", "direction": "bullish", "price_level": recent[i-1]["price"], "confidence": 0.85})
            elif recent[i-1]["type"] == "low" and recent[i-2]["type"] == "high":
                idx = recent[i]["index"]
                if closes[idx] < recent[i-1]["price"]:
                    candle_size = abs(closes[idx] - closes[idx-1])
                    avg_size = np.mean([abs(closes[j] - closes[j-1]) for j in range(max(0, idx-10), idx)])
                    if candle_size > avg_size * 1.5:
                        patterns.append({"type": "MSS", "direction": "bearish", "price_level": recent[i-1]["price"], "confidence": 0.85})
        return patterns

    def _detect_fvg(self, opens, highs, lows, closes, times):
        patterns = []
        for i in range(2, len(opens)):
            if highs[i-2] < lows[i] and closes[i-1] > opens[i-1]:
                gap = lows[i] - highs[i-2]
                avg_range = np.mean([highs[j] - lows[j] for j in range(max(0, i-10), i)])
                if gap > avg_range * 0.3:
                    patterns.append({"type": "FVG", "direction": "bullish", "price_level": float((highs[i-2] + lows[i]) / 2), "confidence": min(0.95, 0.7 + gap/avg_range*0.2), "metadata": {"top": float(lows[i]), "bottom": float(highs[i-2])}})
            elif lows[i-2] > highs[i] and closes[i-1] < opens[i-1]:
                gap = lows[i-2] - highs[i]
                avg_range = np.mean([highs[j] - lows[j] for j in range(max(0, i-10), i)])
                if gap > avg_range * 0.3:
                    patterns.append({"type": "FVG", "direction": "bearish", "price_level": float((lows[i-2] + highs[i]) / 2), "confidence": min(0.95, 0.7 + gap/avg_range*0.2), "metadata": {"top": float(lows[i-2]), "bottom": float(highs[i])}})
        return patterns

    def _detect_ob(self, opens, highs, lows, closes, times):
        patterns = []
        for i in range(3, len(opens)):
            impulse = abs(closes[i] - opens[i])
            avg = np.mean([abs(closes[j] - opens[j]) for j in range(max(0, i-10), i)])
            if impulse > avg * 2:
                if closes[i] > opens[i]:
                    for j in range(i-1, max(0, i-5), -1):
                        if closes[j] < opens[j]:
                            patterns.append({"type": "OB", "direction": "bullish", "price_level": float((opens[j] + closes[j]) / 2), "confidence": 0.8, "metadata": {"ob_high": float(opens[j]), "ob_low": float(closes[j])}})
                            break
                else:
                    for j in range(i-1, max(0, i-5), -1):
                        if closes[j] > opens[j]:
                            patterns.append({"type": "OB", "direction": "bearish", "price_level": float((opens[j] + closes[j]) / 2), "confidence": 0.8, "metadata": {"ob_high": float(closes[j]), "ob_low": float(opens[j])}})
                            break
        return patterns

    def _detect_liquidity(self, highs, lows, swings, times):
        patterns = []
        if len(swings) < 4: return patterns
        high_swings = [s for s in swings if s["type"] == "high"]
        for i in range(len(high_swings)):
            for j in range(i+1, len(high_swings)):
                if abs(high_swings[i]["price"] - high_swings[j]["price"]) / high_swings[i]["price"] < 0.001:
                    if max(highs[-5:]) > high_swings[i]["price"]:
                        patterns.append({"type": "LIQUIDITY", "direction": "bearish", "price_level": high_swings[i]["price"], "confidence": 0.75})
        return patterns

    def _determine_bias(self, patterns, current_price):
        # Market-structure shift (MSS) is the primary bias driver. NOTE: the old
        # code also counted a "BOS" pattern type that NO detector ever emits, so
        # bias silently rested on MSS alone with a phantom term — removed.
        struct = [p for p in patterns if p["type"] == "MSS"]
        bull_s = sum(1 for p in struct if p["direction"] == "bullish")
        bear_s = sum(1 for p in struct if p["direction"] == "bearish")
        if bull_s != bear_s:
            return "BULLISH" if bull_s > bear_s else "BEARISH"
        # No decisive structure shift → net of all directional arrays (OB/FVG/
        # liquidity), requiring a clear margin so noise doesn't create a bias.
        bull = sum(1 for p in patterns if p["direction"] == "bullish")
        bear = sum(1 for p in patterns if p["direction"] == "bearish")
        if bull > bear + 1: return "BULLISH"
        if bear > bull + 1: return "BEARISH"
        return "NEUTRAL"

    def _calculate_confluences(self, patterns, bias):
        checks = []
        score = 0
        if any(p["type"] == "MSS" for p in patterns): score += 1; checks.append("MSS_Confirmed")
        if any(p["type"] == "FVG" for p in patterns): score += 1; checks.append("FVG_Present")
        if any(p["type"] == "OB" for p in patterns): score += 1; checks.append("OB_Present")
        if any(p["type"] == "LIQUIDITY" for p in patterns): score += 1; checks.append("Liquidity_Swept")
        if bias != "NEUTRAL": score += 1; checks.append("Bias_Aligned")
        return {"score": score, "checks": checks, "max_score": 6}

    def _premium_discount(self, price, swings):
        if len(swings) < 2: return "unknown"
        highs = [s["price"] for s in swings if s["type"] == "high"][-5:]
        lows = [s["price"] for s in swings if s["type"] == "low"][-5:]
        if not highs or not lows: return "unknown"
        mid = (max(highs) + min(lows)) / 2
        return "premium" if price > mid else "discount"

    def calculate_entry(self, patterns, bias, current_price):
        """Calculate entry zone, SL, and TPs from detected patterns.
        
        Fixes: correctly reads OB metadata (ob_high/ob_low) and FVG metadata (top/bottom).
        """
        if bias == "NEUTRAL": return None
        relevant = [p for p in patterns if p["direction"] == bias.lower() and p["type"] in ["FVG", "OB"]]
        if not relevant: return None
        nearest = min(relevant, key=lambda p: abs(p["price_level"] - current_price))
        entry = nearest["price_level"]
        meta = nearest.get("metadata", {})
        
        if bias == "BULLISH":
            # For bullish entry: SL is below the pattern's lower boundary
            # FVG uses "bottom" key, OB uses "ob_low" key
            sl = meta.get("bottom") or meta.get("ob_low") or entry * 0.995
            risk = entry - sl
            if risk <= 0:
                risk = entry * 0.005  # fallback 0.5%
            return {
                "entry": round(entry, 5), "sl": round(sl, 5),
                "tp1": round(entry + risk, 5), "tp2": round(entry + risk * 2, 5), "tp3": round(entry + risk * 3, 5),
                "risk": round(risk, 5)
            }
        else:
            # For bearish entry: SL is above the pattern's upper boundary
            # FVG uses "top" key, OB uses "ob_high" key
            sl = meta.get("top") or meta.get("ob_high") or entry * 1.005
            risk = sl - entry
            if risk <= 0:
                risk = entry * 0.005  # fallback 0.5%
            return {
                "entry": round(entry, 5), "sl": round(sl, 5),
                "tp1": round(entry - risk, 5), "tp2": round(entry - risk * 2, 5), "tp3": round(entry - risk * 3, 5),
                "risk": round(risk, 5)
            }

ict_engine = ICTPatternEngine()
