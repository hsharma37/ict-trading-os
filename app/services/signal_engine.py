"""Signal generation engine."""
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from app.services.market_data import market_service
from app.services.ict_engine import ict_engine

# Signal quality thresholds
SIGNAL_THRESHOLD = 2        # Minimum score to generate a signal (was 4)
SIGNAL_QUALITY_STRONG = 5  # Score >= 5 = STRONG
SIGNAL_QUALITY_MODERATE = 3 # Score >= 3 = MODERATE
SIGNAL_QUALITY_WEAK = 2     # Score >= 2 = WEAK
SIGNAL_EXPIRY_MINUTES = 60  # Signal validity (was 5)
BIAS_FLIP_COOLDOWN_SECONDS = 60  # Cooldown after bias flip (was 300)

class SignalEngine:
    def __init__(self):
        self.active_signals = {}
        self.signal_history = []
        self.symbol_states = {}

    def get_state(self, symbol: str):
        if symbol not in self.symbol_states:
            self.symbol_states[symbol] = {"bias": "NEUTRAL", "last_flip": datetime.utcnow() - timedelta(hours=1), "count": 0}
        return self.symbol_states[symbol]

    def analyze(self, symbol: str) -> Optional[Dict]:
        timeframes = ["1h", "15m", "5m"]
        analyses = {}
        for tf in timeframes:
            candles = market_service.get_history(symbol, tf, 100)
            if candles:
                analyses[tf] = ict_engine.analyze(candles, symbol, tf)

        if not analyses: return None

        htf_bias = analyses.get("1h", {}).get("current_bias", "NEUTRAL")
        itf_patterns = analyses.get("15m", {}).get("patterns", [])
        ltf_patterns = analyses.get("5m", {}).get("patterns", [])

        score = 0
        confluences = []
        if htf_bias != "NEUTRAL": score += 1; confluences.append("HTF_Bias_Aligned")
        if any(p["type"] == "MSS" for p in itf_patterns): score += 1; confluences.append("ITF_MSS")
        if any(p["type"] in ["FVG", "OB"] for p in ltf_patterns): score += 1; confluences.append("LTF_Entry_POI")
        if any(p["type"] == "LIQUIDITY" for p in itf_patterns + ltf_patterns): score += 1; confluences.append("Liquidity_Swept")

        pd = analyses.get("15m", {}).get("premium_discount", "unknown")
        if (htf_bias == "BULLISH" and pd == "discount") or (htf_bias == "BEARISH" and pd == "premium"):
            score += 1; confluences.append("Premium_Discount")

        current_price = analyses.get("5m", {}).get("current_price", 0)
        entry_zone = ict_engine.calculate_entry(itf_patterns + ltf_patterns, htf_bias, current_price)
        if entry_zone and entry_zone.get("tp3"):
            risk = entry_zone["risk"]
            reward = abs(entry_zone["tp3"] - entry_zone["entry"])
            if risk > 0 and reward / risk >= 2:
                score += 1; confluences.append("2R_Target_Viable")

        # Determine signal quality even if below threshold
        if score >= SIGNAL_QUALITY_STRONG:
            quality = "STRONG"
        elif score >= SIGNAL_QUALITY_MODERATE:
            quality = "MODERATE"
        elif score >= SIGNAL_QUALITY_WEAK:
            quality = "WEAK"
        else:
            quality = "NONE"

        # Build partial breakdown for frontend visibility
        breakdown = {
            "symbol": symbol,
            "sentiment": htf_bias.lower(),
            "score": score,
            "max_score": 6,
            "quality": quality,
            "confluences": confluences,
            "entry_zone": entry_zone.get("entry") if entry_zone else None,
            "stop_loss": entry_zone.get("sl") if entry_zone else None,
            "targets": [entry_zone.get("tp1"), entry_zone.get("tp2"), entry_zone.get("tp3")] if entry_zone else [],
            "confidence": round(score / 6, 2),
            "session": self._get_session(),
            "executed": False,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(minutes=SIGNAL_EXPIRY_MINUTES)).isoformat(),
            "htf_bias": htf_bias,
            "itf_patterns": [{"type": p["type"], "direction": p["direction"]} for p in itf_patterns[:3]],
            "ltf_patterns": [{"type": p["type"], "direction": p["direction"]} for p in ltf_patterns[:3]],
        }

        # Below threshold: return partial breakdown so UI can show "why no signal"
        if score < SIGNAL_THRESHOLD:
            return {**breakdown, "signal": None, "message": f"Score {score} below threshold {SIGNAL_THRESHOLD}. Confluences detected: {', '.join(confluences) or 'none'}."}

        # Bias flip cooldown (reduced from 300s to 60s)
        state = self.get_state(symbol)
        now = datetime.utcnow()
        if state["bias"] != htf_bias and state["bias"] != "NEUTRAL":
            if (now - state["last_flip"]).total_seconds() < BIAS_FLIP_COOLDOWN_SECONDS:
                return {**breakdown, "signal": None, "message": "Bias recently flipped. Cooling down."}

        state["bias"] = htf_bias
        state["last_flip"] = now
        state["count"] += 1

        signal = {
            "id": f"SIG-{int(now.timestamp()*1000)}",
            "symbol": symbol,
            "sentiment": htf_bias.lower(),
            "score": score,
            "max_score": 6,
            "quality": quality,
            "confluences": confluences,
            "entry_zone": entry_zone.get("entry") if entry_zone else None,
            "stop_loss": entry_zone.get("sl") if entry_zone else None,
            "targets": [entry_zone.get("tp1"), entry_zone.get("tp2"), entry_zone.get("tp3")] if entry_zone else [],
            "confidence": round(score / 6, 2),
            "session": self._get_session(),
            "executed": False,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=SIGNAL_EXPIRY_MINUTES)).isoformat(),
            "htf_bias": htf_bias,
            "itf_patterns": [{"type": p["type"], "direction": p["direction"]} for p in itf_patterns[:3]],
            "ltf_patterns": [{"type": p["type"], "direction": p["direction"]} for p in ltf_patterns[:3]],
        }

        self.active_signals[symbol] = signal
        self.signal_history.append(signal)
        return signal

    def _get_session(self):
        hour = datetime.utcnow().hour
        if 7 <= hour < 10: return "London Open"
        elif 12 <= hour < 15: return "NY AM"
        elif 15 <= hour < 17: return "NY Lunch"
        elif 17 <= hour < 21: return "NY PM"
        elif 21 <= hour or hour < 8: return "Asian"
        return "London Close"

    def get_active(self, symbol: Optional[str] = None):
        now = datetime.utcnow()
        expired = [s for s, sig in self.active_signals.items() if datetime.fromisoformat(sig["expires_at"]) < now]
        for s in expired: del self.active_signals[s]
        if symbol: return [self.active_signals.get(symbol)] if symbol in self.active_signals else []
        return list(self.active_signals.values())

    def get_stats(self, symbol: str):
        hist = [s for s in self.signal_history if s["symbol"] == symbol]
        bullish = sum(1 for s in hist if s["sentiment"] == "bullish")
        bearish = sum(1 for s in hist if s["sentiment"] == "bearish")
        return {"symbol": symbol, "bullish": bullish, "bearish": bearish, "total": bullish + bearish, "active": len([s for s in self.active_signals.values() if s["symbol"] == symbol])}

signal_engine = SignalEngine()
