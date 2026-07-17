"""Research service for instrument analysis and market sentiment."""
from typing import Dict, List, Optional
from datetime import datetime
import statistics
from app.services.market_data import market_service
from app.services.instrument_config import get_instrument, get_all_instruments


class ResearchService:
    """Analyze instruments with technical indicators."""

    def _sma(self, data: List[float], period: int) -> Optional[float]:
        """Calculate simple moving average."""
        if len(data) < period:
            return None
        return sum(data[-period:]) / period

    def _atr(self, candles: List[Dict], period: int = 14) -> Optional[float]:
        """Calculate Average True Range."""
        if len(candles) < period + 1:
            return None
        trs = []
        for i in range(1, len(candles)):
            high = candles[i]["high"]
            low = candles[i]["low"]
            prev_close = candles[i - 1]["close"]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        if len(trs) < period:
            return None
        return sum(trs[-period:]) / period

    def _support_resistance(self, candles: List[Dict], lookback: int = 20) -> Dict:
        """Find support and resistance levels."""
        if len(candles) < lookback:
            return {"support": None, "resistance": None, "levels": []}

        recent = candles[-lookback:]
        highs = [c["high"] for c in recent]
        lows = [c["low"] for c in recent]

        # Simple approach: find swing highs and lows
        swing_highs = []
        swing_lows = []
        for i in range(1, len(recent) - 1):
            if recent[i]["high"] > recent[i - 1]["high"] and recent[i]["high"] > recent[i + 1]["high"]:
                swing_highs.append(recent[i]["high"])
            if recent[i]["low"] < recent[i - 1]["low"] and recent[i]["low"] < recent[i + 1]["low"]:
                swing_lows.append(recent[i]["low"])

        resistance = max(swing_highs) if swing_highs else max(highs)
        support = min(swing_lows) if swing_lows else min(lows)

        # Key levels: recent swing points + round numbers
        levels = sorted(set(swing_highs + swing_lows))
        if len(levels) > 5:
            levels = levels[:5]

        return {"support": support, "resistance": resistance, "levels": levels}

    def _trend(self, candles: List[Dict]) -> str:
        """Determine trend based on SMA crossover."""
        closes = [c["close"] for c in candles if c.get("close")]
        if len(closes) < 50:
            return "NEUTRAL"
        sma20 = self._sma(closes, 20)
        sma50 = self._sma(closes, 50)
        if sma20 and sma50:
            if sma20 > sma50 * 1.001:
                return "BULLISH"
            elif sma20 < sma50 * 0.999:
                return "BEARISH"
        return "NEUTRAL"

    def _volatility(self, candles: List[Dict]) -> Dict:
        """Calculate volatility metrics."""
        if not candles:
            return {"atr": None, "daily_range": None, "volatility_pct": None}
        atr = self._atr(candles, 14)
        recent = candles[-20:]
        ranges = [c["high"] - c["low"] for c in recent if c.get("high") and c.get("low")]
        avg_range = sum(ranges) / len(ranges) if ranges else 0
        current_price = candles[-1]["close"] if candles else 0
        vol_pct = (avg_range / current_price * 100) if current_price > 0 else 0
        return {
            "atr": round(atr, 5) if atr else None,
            "daily_range": round(avg_range, 5),
            "volatility_pct": round(vol_pct, 3),
        }

    def analyze_instrument(self, symbol: str) -> Dict:
        """Full technical analysis for an instrument."""
        symbol = symbol.upper()
        config = get_instrument(symbol)
        live = market_service.get_price(symbol)
        candles = market_service.get_history(symbol, "1h", 100)

        if not candles or not config:
            return {
                "symbol": symbol,
                "error": "No data - analysis runs exclusively on the MT5 broker feed; connect the MT5 bridge.",
                "current_price": live.get("price"),
            }

        # Data-quality provenance: never present levels derived from random
        # fallback candles (or a stale/synthetic quote) as if they were real.
        from app.services.market_data import history_is_synthetic
        synthetic = history_is_synthetic(candles) or (str(live.get("source", "")).lower() == "synthetic")
        stale = bool(live.get("stale"))
        data_source = live.get("source", "unknown")
        data_quality = "synthetic" if synthetic else ("stale" if stale else "live")

        closes = [c["close"] for c in candles if c.get("close")]
        trend = self._trend(candles)
        vol = self._volatility(candles)
        sr = self._support_resistance(candles)

        sma20 = self._sma(closes, 20)
        sma50 = self._sma(closes, 50)
        sma200 = self._sma(closes, 200)  # None unless ≥200 candles — not faked from 50

        # Sentiment based on trend and recent price action
        sentiment = "NEUTRAL"
        if trend == "BULLISH" and live.get("change_pct", 0) > 0.5:
            sentiment = "BULLISH"
        elif trend == "BEARISH" and live.get("change_pct", 0) < -0.5:
            sentiment = "BEARISH"
        elif vol.get("volatility_pct", 0) > 2.0:
            sentiment = "VOLATILE"

        # Key levels
        key_levels = []
        if sr["support"]:
            key_levels.append({"level": round(sr["support"], config.get("digits", 5)), "type": "support"})
        if sr["resistance"]:
            key_levels.append({"level": round(sr["resistance"], config.get("digits", 5)), "type": "resistance"})
        for lvl in sr.get("levels", [])[:3]:
            key_levels.append({"level": round(lvl, config.get("digits", 5)), "type": "swing"})

        # Distance to SR
        price = live.get("price", 0)
        dist_to_support = round((price - sr["support"]) / price * 100, 2) if price and sr["support"] else None
        dist_to_resistance = round((sr["resistance"] - price) / price * 100, 2) if price and sr["resistance"] else None

        digits = config.get("digits", 5)
        support = round(sr["support"], digits) if sr["support"] else None
        resistance = round(sr["resistance"], digits) if sr["resistance"] else None
        sma20r = round(sma20, digits) if sma20 else None
        sma50r = round(sma50, digits) if sma50 else None

        news = self._relevant_news(symbol)
        reasoning = self._build_reasoning(
            symbol, price, live.get("change_pct", 0), trend, sentiment, sma20r, sma50r,
            support, resistance, dist_to_support, dist_to_resistance, vol, news, digits,
            data_quality,
        )

        return {
            "symbol": symbol,
            "label": config.get("label", symbol),
            "kind": config.get("kind", "unknown"),
            "current_price": price,
            "change": live.get("change"),
            "change_pct": live.get("change_pct"),
            "trend": trend,
            "sentiment": sentiment,
            "reasoning": reasoning,
            "volatility": vol,
            "support": support,
            "resistance": resistance,
            "dist_to_support": dist_to_support,
            "dist_to_resistance": dist_to_resistance,
            "key_levels": key_levels,
            "sma20": sma20r,
            "sma50": sma50r,
            "news": news,
            # Provenance so the UI never shows fabricated/stale levels as live.
            "data_source": data_source,
            "stale": stale,
            "synthetic": synthetic,
            "data_quality": data_quality,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _relevant_news(self, symbol: str, limit: int = 3) -> List[Dict]:
        """Recent headlines that can move this instrument (title/impact/source)."""
        try:
            from app.services.news_service import news_service
            items = news_service.get_news(limit=limit, symbol=symbol)
            return [{"title": n["title"], "impact": n["impact"], "source": n["source"],
                     "link": n.get("link", "")} for n in items]
        except Exception:
            return []

    def _build_reasoning(self, symbol, price, change_pct, trend, sentiment, sma20, sma50,
                         support, resistance, dist_sup, dist_res, vol, news, digits,
                         data_quality="live") -> str:
        """A precise, evidence-grounded explanation of the current read — every
        clause cites the actual number behind it (no vague 'looks bullish').

        When the underlying data isn't live (random fallback candles or a stale
        quote), the analysis leads with an explicit warning instead of presenting
        the levels as tradeable — the numbers below are not real market data."""
        parts = []
        if data_quality == "synthetic":
            return ("⚠️ DATA UNAVAILABLE — the market feed could not be reached, so the levels "
                    "below would be simulated, not real. Do not trade on this. Retry when the "
                    "price source is live.")
        if data_quality == "stale":
            parts.append("⚠️ Quote is stale (feed not updating) — treat levels as indicative only.")
        # Structure vs moving averages.
        if sma20 and sma50 and price:
            rel = []
            rel.append(f"above its 20-SMA ({sma20})" if price > sma20 else f"below its 20-SMA ({sma20})")
            rel.append(f"above the 50-SMA ({sma50})" if price > sma50 else f"below the 50-SMA ({sma50})")
            parts.append(f"Price {price} is {rel[0]} and {rel[1]} → {trend.lower()} structure.")
        else:
            parts.append(f"{trend.title()} structure.")
        # Momentum.
        if change_pct is not None:
            arrow = "up" if change_pct >= 0 else "down"
            parts.append(f"24h momentum is {arrow} {abs(change_pct):.2f}%.")
        # Levels with distances.
        if support is not None and dist_sup is not None:
            parts.append(f"Nearest support {support} ({dist_sup:.2f}% below).")
        if resistance is not None and dist_res is not None:
            parts.append(f"Resistance {resistance} ({dist_res:.2f}% above).")
        # Volatility context.
        vpct = (vol or {}).get("volatility_pct")
        if vpct is not None:
            note = "elevated — wider stops warranted" if vpct > 2.0 else "normal"
            parts.append(f"Volatility {vpct:.2f}% ({note}).")
        # Bias conclusion.
        bias = {
            "BULLISH": "Net bias bullish while price holds above the 20-SMA and support.",
            "BEARISH": "Net bias bearish while price stays below the 20-SMA and resistance.",
            "VOLATILE": "No clean bias — volatility is high; wait for a level to break and hold.",
            "NEUTRAL": "No clean bias — price is between levels; wait for a break of support/resistance.",
        }.get(sentiment, "")
        if bias:
            parts.append(bias)
        # News overlay.
        if news:
            top = news[0]
            parts.append(f"News to watch: \"{top['title']}\" ({top['impact']} impact, {top['source']}).")
        return " ".join(parts)

    def analyze_all(self) -> List[Dict]:
        """Analyze all instruments."""
        results = []
        for symbol in get_all_instruments():
            result = self.analyze_instrument(symbol)
            if "error" not in result:
                results.append(result)
        return results

    def get_correlation_matrix(self) -> Dict:
        """Calculate correlation between instrument pairs."""
        symbols = list(get_all_instruments().keys())
        returns = {}
        for sym in symbols:
            candles = market_service.get_history(sym, "1h", 50)
            if candles and len(candles) > 10:
                closes = [c["close"] for c in candles]
                # Calculate returns
                rets = []
                for i in range(1, len(closes)):
                    if closes[i - 1] > 0:
                        rets.append((closes[i] - closes[i - 1]) / closes[i - 1])
                if rets:
                    returns[sym] = rets

        # Correlation matrix
        matrix = {}
        for sym1 in returns:
            matrix[sym1] = {}
            for sym2 in returns:
                if sym1 == sym2:
                    matrix[sym1][sym2] = 1.0
                elif sym2 in returns:
                    # Pearson correlation
                    r1 = returns[sym1]
                    r2 = returns[sym2]
                    min_len = min(len(r1), len(r2))
                    if min_len > 5:
                        x = r1[-min_len:]
                        y = r2[-min_len:]
                        mean_x = sum(x) / len(x)
                        mean_y = sum(y) / len(y)
                        num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
                        den_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
                        den_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5
                        corr = num / (den_x * den_y) if den_x > 0 and den_y > 0 else 0
                        matrix[sym1][sym2] = round(corr, 3)
                    else:
                        matrix[sym1][sym2] = 0.0

        return {"matrix": matrix, "symbols": list(returns.keys())}

    def get_market_summary(self) -> Dict:
        """Get a market-wide summary."""
        all_analysis = self.analyze_all()
        bullish = sum(1 for a in all_analysis if a.get("trend") == "BULLISH")
        bearish = sum(1 for a in all_analysis if a.get("trend") == "BEARISH")
        neutral = sum(1 for a in all_analysis if a.get("trend") == "NEUTRAL")

        # Find biggest movers
        movers = sorted(all_analysis, key=lambda x: abs(x.get("change_pct", 0)), reverse=True)

        return {
            "total_instruments": len(all_analysis),
            "bullish": bullish,
            "bearish": bearish,
            "neutral": neutral,
            "biggest_movers": [
                {
                    "symbol": m["symbol"],
                    "change_pct": m["change_pct"],
                    "trend": m["trend"],
                    "sentiment": m["sentiment"],
                }
                for m in movers[:3]
            ],
            "instruments": all_analysis,
            "timestamp": datetime.utcnow().isoformat(),
        }


research_service = ResearchService()
