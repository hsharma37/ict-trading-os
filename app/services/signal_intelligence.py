"""News-driven signal intelligence.

Fuses four evidence streams into one reasoned trade signal per instrument:
  1. News sentiment — directional, attributed to the right currency/asset.
  2. Technical read — trend vs SMAs, momentum, level proximity (research_service).
  3. ICT knowledge — relevant concepts from the knowledge base (how to act on the bias).
  4. Live exposure — whether the account already holds the symbol.

Every output carries the factor breakdown, a precise reason, and actionable
suggestions — nothing is a black box.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

_BULLISH = {
    "rise", "rises", "rising", "rose", "gain", "gains", "climb", "climbs", "surge",
    "surges", "jump", "jumps", "rally", "rallies", "firms", "firm", "strengthens",
    "strengthen", "advance", "advances", "boost", "boosts", "higher", "up", "soar",
    "soars", "rebound", "recovers", "hawkish", "hot", "beats", "upbeat", "bullish",
    "spikes", "extends", "outperforms", "supported", "demand",
}
_BEARISH = {
    "fall", "falls", "falling", "fell", "drop", "drops", "slip", "slips", "decline",
    "declines", "plunge", "plunges", "sink", "sinks", "soft", "softer", "weakens",
    "weaken", "subdued", "depressed", "pressured", "pressure", "lower", "down",
    "dovish", "cools", "cool", "misses", "downbeat", "bearish", "tumble", "tumbles",
    "slump", "slumps", "retreat", "retreats", "eases", "ease", "sell-off", "selloff",
}

# word -> currency code, for proximity-based per-currency sentiment.
_WORD_CCY = {
    "gold": "XAU", "bullion": "XAU", "xau": "XAU",
    "dollar": "USD", "greenback": "USD", "usd": "USD", "fed": "USD", "fomc": "USD", "dxy": "USD",
    "euro": "EUR", "eur": "EUR", "ecb": "EUR",
    "pound": "GBP", "sterling": "GBP", "cable": "GBP", "gbp": "GBP", "boe": "GBP",
    "yen": "JPY", "jpy": "JPY", "boj": "JPY",
    "aussie": "AUD", "aud": "AUD", "rba": "AUD",
    "kiwi": "NZD", "nzd": "NZD", "rbnz": "NZD",
    "loonie": "CAD", "cad": "CAD", "boc": "CAD",
}
_WINDOW = 4  # words on each side of a currency mention to attribute sentiment

_IMPACT_WEIGHT = {"high": 2.0, "medium": 1.0, "low": 0.5}


class SignalIntelligence:
    # ── currency helpers ─────────────────────────────────────────────

    @staticmethod
    def _legs(symbol: str):
        s = symbol.upper()
        if s == "XAUUSD":
            return "XAU", "USD"
        return s[:3], s[3:6]

    def _currency_polarities(self, title: str) -> Dict[str, int]:
        """Sentiment per currency, attributed by proximity — the directional word
        nearest a currency mention counts for THAT currency (so 'Gold climbs as
        Dollar slips' scores gold + and USD -, not one blended number)."""
        words = re.findall(r"[a-z\-]+", title.lower())
        pols: Dict[str, int] = {}
        for i, w in enumerate(words):
            ccy = _WORD_CCY.get(w)
            if not ccy:
                continue
            lo, hi = max(0, i - _WINDOW), min(len(words), i + _WINDOW + 1)
            window = words[lo:hi]
            p = sum(1 for x in window if x in _BULLISH) - sum(1 for x in window if x in _BEARISH)
            pols[ccy] = pols.get(ccy, 0) + p
        return pols

    def _recency_weight(self, ts: Optional[str]) -> float:
        if not ts:
            return 0.5
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            hrs = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600
        except Exception:
            return 0.5
        if hrs <= 6:
            return 1.0
        if hrs <= 24:
            return 0.75
        if hrs <= 48:
            return 0.5
        return 0.3

    # ── news sentiment for a pair ────────────────────────────────────

    def news_sentiment(self, symbol: str, news: List[Dict]) -> Dict:
        base, quote = self._legs(symbol)
        num = 0.0
        den = 0.0
        contributors = []
        for item in news:
            title = item.get("title", "")
            pols = self._currency_polarities(title)
            # Strong base OR weak quote => bullish pair (and vice-versa).
            raw = pols.get(base, 0) - pols.get(quote, 0)
            if raw == 0:
                continue
            item_score = max(-1.0, min(1.0, raw / 2.0))  # cap one headline's pull
            w = _IMPACT_WEIGHT.get(item.get("impact", "medium"), 1.0) * self._recency_weight(item.get("timestamp"))
            num += item_score * w
            den += w
            # Which currency drove it (largest |polarity|), for the explanation.
            driver = max(pols.items(), key=lambda kv: abs(kv[1]))[0] if pols else None
            contributors.append({
                "title": title,
                "subject": "Gold" if driver == "XAU" else driver,
                "pair_effect": "bullish" if item_score > 0 else "bearish",
                "impact": item.get("impact", "medium"),
            })
        score = round(num / den, 2) if den else 0.0  # [-1, 1]
        label = "bullish" if score > 0.15 else "bearish" if score < -0.15 else "neutral"
        # Be honest about the method: this is a keyword-polarity tally over
        # headlines, not an NLP sentiment model (no negation/sarcasm handling).
        return {"score": score, "label": label, "items_scored": len(contributors),
                "contributors": contributors[:5], "method": "keyword-polarity"}

    # ── ICT knowledge overlay ────────────────────────────────────────

    # ICT concept vocabulary -> label, for extracting clean concepts from KB text.
    _ICT_CONCEPTS = {
        "fair value gap": "Fair Value Gap", "fvg": "Fair Value Gap",
        "order block": "Order Block", " ob ": "Order Block",
        "market structure shift": "Market Structure Shift", "mss": "Market Structure Shift",
        "break of structure": "Break of Structure", "bos": "Break of Structure",
        "liquidity": "Liquidity", "inducement": "Inducement",
        "optimal trade entry": "Optimal Trade Entry", "ote": "Optimal Trade Entry",
        "premium": "Premium/Discount", "discount": "Premium/Discount",
        "killzone": "Killzone", "silver bullet": "Silver Bullet",
        "displacement": "Displacement", "imbalance": "Imbalance", "mitigation": "Mitigation",
    }

    def _ict_playbook(self, direction: str, tech: Dict) -> Dict:
        """Relevant ICT concepts + how to act, grounded in the KB when available."""
        concepts: List[str] = []
        source = None
        try:
            from app.services.kb_service import kb_service
            query = "bullish order block fair value gap discount entry" if direction == "BUY" else \
                    "bearish order block fair value gap premium entry" if direction == "SELL" else \
                    "market structure liquidity"
            hits = kb_service.search_vectors(query, top_k=2)
            for h in hits:
                text = " " + (h.get("chunk_text") or "").lower() + " "
                for kw, label in self._ICT_CONCEPTS.items():
                    if kw in text and label not in concepts:
                        concepts.append(label)
            if hits:
                source = hits[0].get("title") or hits[0].get("source_title")
        except Exception:
            pass
        concepts = concepts[:5]
        # Deterministic ICT rule to act on the bias (always present).
        if direction == "BUY":
            rule = ("Bias long: wait for price to trade into a discount array (bullish FVG / order block) "
                    "below equilibrium, with a lower-timeframe MSS up, then enter; invalidation below the OB low.")
        elif direction == "SELL":
            rule = ("Bias short: wait for price to rally into a premium array (bearish FVG / order block) "
                    "above equilibrium, with a lower-timeframe MSS down, then enter; invalidation above the OB high.")
        else:
            rule = ("No clean bias: let price take liquidity and confirm a market-structure shift before committing; "
                    "stand aside through the chop.")
        return {"rule": rule, "concepts": concepts, "kb_source": source}

    # ── main ─────────────────────────────────────────────────────────

    def generate(self, symbol: str) -> Dict:
        symbol = symbol.upper()
        from app.services.research_service import research_service
        from app.services.news_service import news_service

        tech = research_service.analyze_instrument(symbol)
        news = news_service.get_news(limit=12, symbol=symbol)
        senti = self.news_sentiment(symbol, news)

        # Data-quality gate: never emit a confident BUY/SELL when the technicals
        # are built on random fallback candles — that would be a signal on noise.
        data_quality = tech.get("data_quality", "live")
        if data_quality == "synthetic":
            return {
                "symbol": symbol, "signal": "NEUTRAL", "confidence": "low", "confidence_score": 0,
                "score": 0.0, "unavailable": True,
                "data_quality": "synthetic", "data_source": tech.get("data_source"), "stale": tech.get("stale", False),
                "news_sentiment": senti,
                "technical": {"trend": "NEUTRAL", "current_price": tech.get("current_price")},
                "ict": self._ict_playbook("NEUTRAL", tech),
                "factors": [],
                "reasoning": ("⚠️ Live market data is unavailable, so no reliable signal can be generated — the "
                              "underlying candles would be simulated. News sentiment below is still real. "
                              "Retry when the price feed is live."),
                "suggestions": [],
                "news": [{"title": n["title"], "impact": n["impact"], "source": n["source"],
                          "timestamp": n.get("timestamp"), "link": n.get("link", "")} for n in news[:5]],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        # Component scores in [-1, 1].
        trend = (tech.get("trend") or "NEUTRAL").upper()
        tech_score = 0.7 if trend == "BULLISH" else -0.7 if trend == "BEARISH" else 0.0
        change_pct = tech.get("change_pct") or 0
        mom_score = max(-1.0, min(1.0, change_pct / 1.0)) if change_pct else 0.0
        news_score = senti["score"]

        # News-weighted fusion (user asked for news-led signals), technicals confirm.
        final = round(0.5 * news_score + 0.35 * tech_score + 0.15 * mom_score, 3)
        direction = "BUY" if final > 0.2 else "SELL" if final < -0.2 else "NEUTRAL"

        # Confidence: magnitude + agreement between news and technicals + evidence.
        agree = (news_score > 0 and tech_score > 0) or (news_score < 0 and tech_score < 0)
        conflict = (news_score > 0.15 and tech_score < 0) or (news_score < -0.15 and tech_score > 0)
        conf = min(95, int(abs(final) * 90) + (10 if agree else 0) + min(10, senti["items_scored"] * 2))
        if conflict:
            conf = min(conf, 40)
        # A stale quote can't support a confident read — cap it.
        if data_quality == "stale":
            conf = min(conf, 45)
        confidence = "high" if conf >= 66 else "medium" if conf >= 40 else "low"

        ict = self._ict_playbook(direction, tech)
        factors = self._factors(symbol, direction, senti, tech, tech_score, news_score, mom_score, change_pct)
        reasoning = self._reasoning(symbol, direction, confidence, senti, tech, agree, conflict, ict)
        suggestions = self._suggestions(symbol, direction, tech, senti, news, ict)

        return {
            "symbol": symbol,
            "signal": direction,
            "confidence": confidence,
            "confidence_score": conf,
            # Be explicit that this is a heuristic fusion, not a backtested model.
            "confidence_basis": "heuristic: 0.5·news + 0.35·trend + 0.15·momentum (not backtested to a hit-rate)",
            "data_quality": data_quality,
            "data_source": tech.get("data_source"),
            "stale": tech.get("stale", False),
            "score": final,
            "news_sentiment": senti,
            "technical": {"trend": trend, "sentiment": tech.get("sentiment"), "change_pct": change_pct,
                          "support": tech.get("support"), "resistance": tech.get("resistance"),
                          "current_price": tech.get("current_price")},
            "ict": ict,
            "factors": factors,
            "reasoning": reasoning,
            "suggestions": suggestions,
            "news": [{"title": n["title"], "impact": n["impact"], "source": n["source"],
                      "timestamp": n.get("timestamp"), "link": n.get("link", "")} for n in news[:5]],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _factors(self, symbol, direction, senti, tech, tech_score, news_score, mom_score, change_pct) -> List[Dict]:
        f = []
        f.append({"name": "News sentiment", "direction": senti["label"],
                  "weight": 0.50, "detail": f"Net news score {senti['score']:+.2f} over {senti['items_scored']} scored headline(s)."})
        f.append({"name": "Technical trend", "direction": "bullish" if tech_score > 0 else "bearish" if tech_score < 0 else "neutral",
                  "weight": 0.35, "detail": f"{tech.get('trend')} structure; price {tech.get('current_price')} vs SMA20 {tech.get('sma20')}."})
        f.append({"name": "Momentum (24h)", "direction": "bullish" if mom_score > 0 else "bearish" if mom_score < 0 else "flat",
                  "weight": 0.15, "detail": f"{change_pct:+.2f}% on the day."})
        sup, res = tech.get("support"), tech.get("resistance")
        if sup or res:
            f.append({"name": "Key levels", "direction": "context", "weight": 0.0,
                      "detail": f"Support {sup} / Resistance {res}."})
        try:
            from app.services.mt5_trades_service import mt5_trades_service
            held = next((p for p in mt5_trades_service.get_open_trades() if p["symbol"] == symbol), None)
            if held:
                f.append({"name": "Live exposure", "direction": held["direction"], "weight": 0.0,
                          "detail": f"You already hold {held['direction']} {held['lot_size']} lots — manage, don't stack blindly."})
        except Exception:
            pass
        return f

    def _reasoning(self, symbol, direction, confidence, senti, tech, agree, conflict, ict) -> str:
        parts = [f"{direction} bias on {symbol} ({confidence} confidence)."]
        # News.
        if senti["items_scored"]:
            top = senti["contributors"][0] if senti["contributors"] else None
            lead = f' e.g. "{top["title"]}"' if top else ""
            parts.append(f"News reads {senti['label']} for the pair (net {senti['score']:+.2f}){lead}.")
        else:
            parts.append("No directional news scored right now.")
        # Technicals.
        parts.append(f"Technically {tech.get('trend','NEUTRAL').lower()} — {(tech.get('reasoning') or '').split('. ')[0]}.")
        # Agreement.
        if conflict:
            parts.append("News and price action DISAGREE, so conviction is capped — treat as a wait, not a trade.")
        elif agree and direction != "NEUTRAL":
            parts.append("News and technicals align, which is what lifts the confidence.")
        # ICT.
        parts.append(ict["rule"])
        return " ".join(p for p in parts if p)

    def _suggestions(self, symbol, direction, tech, senti, news, ict) -> List[str]:
        s = []
        sup, res = tech.get("support"), tech.get("resistance")
        near_sup = f" near support {sup}" if sup else ""
        near_res = f" near resistance {res}" if res else ""
        if direction == "BUY":
            s.append(f"Look for a long entry from a bullish FVG / order block{near_sup} (a discount array); invalidation below that level.")
            if res:
                s.append(f"First objective toward resistance {res}.")
        elif direction == "SELL":
            s.append(f"Look for a short entry from a bearish FVG / order block{near_res} (a premium array); invalidation above that level.")
            if sup:
                s.append(f"First objective toward support {sup}.")
        else:
            s.append("Stand aside until news and structure agree, or a level breaks and holds — then reassess.")
        # High-impact news risk.
        high = next((n for n in news if n.get("impact") == "high"), None)
        if high:
            s.append(f"Event risk: \"{high['title']}\" ({high['source']}) — expect volatility; don't enter right before it.")
        # Confirm in a killzone if concepts suggest timing.
        s.append("Prefer entries during the London or New York killzone; skip low-liquidity chop.")
        # Risk management (ICT discipline).
        s.append("Risk ≤1–2% of the account; size the lot from your stop distance (the app's calculator does this).")
        if ict.get("concepts"):
            s.append(f"Apply these KB concepts to time the entry: {', '.join(ict['concepts'])}.")
        return s


signal_intelligence = SignalIntelligence()
