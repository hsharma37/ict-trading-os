"""
Enhanced Signal generation engine with detailed ICT criteria breakdown.

Each signal now includes a full checklist of ICT concepts checked,
with pass/fail status so the frontend can visualize what criteria
are met and what's missing.
"""
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from app.services.market_data import market_service
from app.services.ict_engine import ict_engine

# Signal quality thresholds
SIGNAL_THRESHOLD = 2
SIGNAL_QUALITY_STRONG = 5
SIGNAL_QUALITY_MODERATE = 3
SIGNAL_QUALITY_WEAK = 2
SIGNAL_EXPIRY_MINUTES = 60
BIAS_FLIP_COOLDOWN_SECONDS = 60

# ICT criteria definitions for frontend display
ICT_CRITERIA = [
    {"key": "htf_bias", "label": "HTF Bias Defined", "description": "Higher timeframe shows clear directional bias (Bullish/Bearish)"},
    {"key": "mss", "label": "Market Structure Shift", "description": "Price broke previous structure — trend change confirmed"},
    {"key": "fvg", "label": "Fair Value Gap", "description": "Imbalance zone where price may return to fill"},
    {"key": "ob", "label": "Order Block", "description": "Institutional order accumulation zone for entry"},
    {"key": "liquidity", "label": "Liquidity Sweep", "description": "Price swept liquidity before reversing"},
    {"key": "premium_discount", "label": "Premium/Discount Zone", "description": "Price is in favorable Premium/Discount region for the bias"},
    {"key": "killzone", "label": "Killzone Active", "description": "Current session is a high-probability trading window"},
    {"key": "rr_viable", "label": "2R+ Target Viable", "description": "Risk:Reward ratio is at least 2:1"},
    {"key": "mtf_alignment", "label": "Multi-Timeframe Alignment", "description": "HTF, ITF, and LTF all agree on direction"},
]


class SignalEngine:
    def __init__(self):
        self.active_signals = {}
        self.signal_history = []
        self.symbol_states = {}

    def get_state(self, symbol: str):
        if symbol not in self.symbol_states:
            self.symbol_states[symbol] = {"bias": "NEUTRAL", "last_flip": datetime.utcnow() - timedelta(hours=1), "count": 0}
        return self.symbol_states[symbol]

    def analyze(self, symbol: str, target_r: float = 2.0) -> Optional[Dict]:
        timeframes = ["1h", "15m", "5m"]
        analyses = {}
        for tf in timeframes:
            candles = market_service.get_history(symbol, tf, 100)
            if candles:
                analyses[tf] = ict_engine.analyze(candles, symbol, tf)

        if not analyses:
            return self._build_response(symbol, None, None, None, None, None, [], "No market data available")

        htf = analyses.get("1h", {})
        itf = analyses.get("15m", {})
        ltf = analyses.get("5m", {})

        # Direction comes from the fused Signal Intelligence read (news + technical
        # trend + momentum + ICT playbook) — the same logic that calls direction
        # correctly — with the ICT structural HTF bias as fallback when the fused
        # read is NEUTRAL. The ICT confluence checklist below then confirms/scores
        # that direction rather than deriving its own.
        ict_bias = htf.get("current_bias", "NEUTRAL")
        bias_source = "ict_structure"
        try:
            from app.services.signal_intelligence import signal_intelligence
            si = signal_intelligence.generate(symbol)
            si_dir = si.get("signal", "NEUTRAL")
            si_bias = {"BUY": "BULLISH", "SELL": "BEARISH"}.get(si_dir, "NEUTRAL")
            if si_bias != "NEUTRAL":
                htf_bias = si_bias
                bias_source = "signal_intelligence"
            else:
                htf_bias = ict_bias
        except Exception:
            htf_bias = ict_bias

        itf_patterns = itf.get("patterns", [])
        ltf_patterns = ltf.get("patterns", [])
        all_patterns = itf_patterns + ltf_patterns

        current_price = ltf.get("current_price", 0) or itf.get("current_price", 0) or htf.get("current_price", 0)
        pd = itf.get("premium_discount", "unknown")
        session = self._get_session()

        # Build detailed criteria checklist
        checklist = []
        score = 0
        confluences = []

        # 1. HTF Bias
        htf_bias_ok = htf_bias != "NEUTRAL"
        if htf_bias_ok:
            score += 1
            confluences.append("HTF_Bias_Aligned")
        checklist.append({
            "key": "htf_bias",
            "label": "Directional Bias Defined",
            "passed": htf_bias_ok,
            "value": htf_bias,
            "description": ("Direction from Signal Intelligence (news+technical+momentum+ICT)"
                            if bias_source == "signal_intelligence"
                            else "Higher-timeframe ICT structural bias")
        })

        # 2. Market Structure Shift
        mss_found = any(p["type"] == "MSS" for p in itf_patterns)
        if mss_found:
            score += 1
            confluences.append("ITF_MSS")
        checklist.append({
            "key": "mss",
            "label": "Market Structure Shift",
            "passed": mss_found,
            "description": "Price broke previous structure — trend change confirmed"
        })

        # 3. Fair Value Gap
        fvg_found = any(p["type"] == "FVG" for p in ltf_patterns)
        if fvg_found:
            score += 1
            confluences.append("LTF_FVG")
        checklist.append({
            "key": "fvg",
            "label": "Fair Value Gap",
            "passed": fvg_found,
            "description": "Imbalance zone where price may return to fill"
        })

        # 4. Order Block
        ob_found = any(p["type"] == "OB" for p in ltf_patterns)
        if ob_found:
            score += 1
            confluences.append("LTF_OB")
        checklist.append({
            "key": "ob",
            "label": "Order Block",
            "passed": ob_found,
            "description": "Institutional order accumulation zone for entry"
        })

        # 5. Liquidity Sweep
        liq_found = any(p["type"] == "LIQUIDITY" for p in all_patterns)
        if liq_found:
            score += 1
            confluences.append("Liquidity_Swept")
        checklist.append({
            "key": "liquidity",
            "label": "Liquidity Sweep",
            "passed": liq_found,
            "description": "Price swept liquidity before reversing"
        })

        # 6. Premium/Discount
        pd_ok = (htf_bias == "BULLISH" and pd == "discount") or (htf_bias == "BEARISH" and pd == "premium")
        if pd_ok:
            score += 1
            confluences.append("Premium_Discount")
        checklist.append({
            "key": "premium_discount",
            "label": "Premium/Discount Zone",
            "passed": pd_ok,
            "value": pd,
            "description": "Price is in favorable zone for the bias"
        })

        # 7. Killzone
        killzone_active = session in ["London Open", "NY AM", "NY PM"]
        if killzone_active:
            score += 1
            confluences.append("Killzone_Active")
        checklist.append({
            "key": "killzone",
            "label": "Killzone Active",
            "passed": killzone_active,
            "value": session,
            "description": "Current session is a high-probability trading window"
        })

        # 8. Entry zone and R:R
        entry_zone = ict_engine.calculate_entry(all_patterns, htf_bias, current_price, target_r=target_r)
        rr_ok = False
        if entry_zone and entry_zone.get("tp3"):
            risk = entry_zone["risk"]
            reward = abs(entry_zone["tp3"] - entry_zone["entry"])
            if risk > 0 and reward / risk >= 2:
                rr_ok = True
                score += 1
                confluences.append("2R_Target_Viable")
        checklist.append({
            "key": "rr_viable",
            "label": "2R+ Target Viable",
            "passed": rr_ok,
            "description": "Risk:Reward ratio is at least 2:1"
        })

        # 9. Multi-timeframe alignment — actually compare directions across TFs,
        # not just "HTF isn't neutral and some pattern exists" (which claimed
        # agreement it never checked). Require an ITF *and* an LTF pattern whose
        # direction matches the HTF bias.
        htf_dir = "bullish" if htf_bias == "BULLISH" else "bearish" if htf_bias == "BEARISH" else None
        itf_agree = bool(htf_dir) and any(p.get("direction") == htf_dir for p in itf_patterns)
        ltf_agree = bool(htf_dir) and any(p.get("direction") == htf_dir for p in ltf_patterns)
        mtf_ok = bool(htf_dir) and itf_agree and ltf_agree
        if mtf_ok:
            score += 1
            confluences.append("MTF_Alignment")
        checklist.append({
            "key": "mtf_alignment",
            "label": "Multi-Timeframe Alignment",
            "passed": mtf_ok,
            "description": "HTF bias confirmed by a same-direction pattern on BOTH the intermediate and lower timeframe"
        })

        # Determine quality
        if score >= SIGNAL_QUALITY_STRONG:
            quality = "STRONG"
        elif score >= SIGNAL_QUALITY_MODERATE:
            quality = "MODERATE"
        elif score >= SIGNAL_QUALITY_WEAK:
            quality = "WEAK"
        else:
            quality = "NONE"

        now = datetime.utcnow()

        # Build response
        breakdown = {
            "symbol": symbol,
            "sentiment": htf_bias.lower(),
            "score": score,
            "max_score": len(checklist),
            "quality": quality,
            "confluences": confluences,
            "checklist": checklist,
            "entry_zone": entry_zone.get("entry") if entry_zone else None,
            "stop_loss": entry_zone.get("sl") if entry_zone else None,
            "targets": [entry_zone.get("tp1"), entry_zone.get("tp2"), entry_zone.get("tp3")] if entry_zone else [],
            "confidence": round(score / len(checklist), 2),
            "confidence_basis": f"{score}/{len(checklist)} ICT confluence checks passed (not a win-probability)",
            "bias_source": bias_source,
            "target_r": target_r,
            "session": session,
            "executed": False,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=SIGNAL_EXPIRY_MINUTES)).isoformat(),
            "htf_bias": htf_bias,
            "itf_patterns": [{"type": p["type"], "direction": p["direction"]} for p in itf_patterns[:3]],
            "ltf_patterns": [{"type": p["type"], "direction": p["direction"]} for p in ltf_patterns[:3]],
        }

        # Below threshold: return partial breakdown
        if score < SIGNAL_THRESHOLD:
            passed_count = sum(1 for c in checklist if c["passed"])
            failed = [c for c in checklist if not c["passed"]]
            return {
                **breakdown,
                "signal": None,
                "message": f"Score {score}/{len(checklist)} below threshold {SIGNAL_THRESHOLD}. {passed_count} of {len(checklist)} criteria met. Missing: {', '.join(c['label'] for c in failed[:3])}{'...' if len(failed) > 3 else ''}."
            }

        # Bias flip cooldown
        state = self.get_state(symbol)
        if state["bias"] != htf_bias and state["bias"] != "NEUTRAL":
            if (now - state["last_flip"]).total_seconds() < BIAS_FLIP_COOLDOWN_SECONDS:
                return {
                    **breakdown,
                    "signal": None,
                    "message": "Bias recently flipped. Cooling down for 60s."
                }

        state["bias"] = htf_bias
        state["last_flip"] = now
        state["count"] += 1

        signal = {**breakdown, "id": f"SIG-{int(now.timestamp()*1000)}"}
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
