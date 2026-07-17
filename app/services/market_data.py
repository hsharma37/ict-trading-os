"""Market data from the MT5 bridge — the broker's own feed, the app's single
source for both live prices and historical candles."""
from typing import List, Dict, Optional
from datetime import datetime

from app.services.instrument_config import get_instrument
from app.services.mt5_price_service import mt5_price_service

MARKET_SPECS = {
    "NQ1!": {"point_value": 0.5, "unit": "contract", "min_qty": 0.25, "qty_step": 0.25},
    "ES1!": {"point_value": 0.25, "unit": "contract", "min_qty": 0.25, "qty_step": 0.25},
    "EURUSD": {"point_value": 10000.0, "unit": "lot", "min_qty": 0.01, "qty_step": 0.01},
    "GBPUSD": {"point_value": 10000.0, "unit": "lot", "min_qty": 0.01, "qty_step": 0.01},
    "XAUUSD": {"point_value": 100.0, "unit": "oz", "min_qty": 0.01, "qty_step": 0.01},
    "USDJPY": {"point_value": 1000.0, "unit": "lot", "min_qty": 0.01, "qty_step": 0.01},
    "BTCUSD": {"point_value": 1.0, "unit": "coin", "min_qty": 0.001, "qty_step": 0.001},
    "CL1!": {"point_value": 100.0, "unit": "contract", "min_qty": 0.01, "qty_step": 0.01},
}

class MarketDataService:
    def __init__(self):
        self.manual_prices: Dict[str, Dict] = {}  # symbol -> {price, bid, ask, timestamp}

    def set_manual_price(self, symbol: str, price: float, bid: float = None, ask: float = None) -> Dict:
        """Set a manual price override (e.g., from MT5 broker feed)."""
        from app.services.instrument_config import get_instrument
        config = get_instrument(symbol)
        digits = config.get("digits", 5) if config else 5
        now = datetime.utcnow().isoformat()
        self.manual_prices[symbol.upper()] = {
            "price": round(price, digits),
            "bid": round(bid, digits) if bid is not None else round(price, digits),
            "ask": round(ask, digits) if ask is not None else round(price, digits),
            "change": 0,
            "change_pct": 0,
            "volume": 0,
            "timestamp": now,
            "source": "manual"
        }
        return self.manual_prices[symbol.upper()]

    def clear_manual_price(self, symbol: str) -> None:
        """Clear the manual price override (quotes return to the MT5 bridge)."""
        self.manual_prices.pop(symbol.upper(), None)

    def get_manual_price(self, symbol: str) -> Optional[Dict]:
        """Get manual price if set and not expired (5 min)."""
        data = self.manual_prices.get(symbol.upper())
        if not data:
            return None
        # Check if expired (>5 minutes)
        try:
            ts = datetime.fromisoformat(data["timestamp"])
            if (datetime.utcnow() - ts).total_seconds() > 300:
                self.manual_prices.pop(symbol.upper(), None)
                return None
        except Exception:
            pass
        return data

    def get_price(self, symbol: str) -> Dict:
        """Single entry point for a live price. Delegates to quote_service, the
        one place that resolves the provider (manual -> MT5 -> OANDA -> Yahoo)
        and caches, so every page shows the same value from the same source."""
        from app.services.quote_service import get_quote  # late import: avoids cycle
        return get_quote(symbol)

    def get_history(self, symbol: str, timeframe: str = "1h", limit: int = 200,
                    history_range: Optional[str] = None) -> List[Dict]:
        """Historical candles from the MT5 bridge — the broker feed the app
        trades on, so every level/signal/backtest lines up with the user's
        MT5 chart. There is deliberately NO Yahoo/OANDA/synthetic fallback:
        without a connected bridge there is no data, and analysis surfaces
        say so rather than analysing a different broker's prices.
        (history_range is accepted for backward compat; MT5 serves by count,
        capped at 5000 bars per request.)"""
        return mt5_price_service.get_history(symbol, timeframe, limit)


def history_is_synthetic(candles: List[Dict]) -> bool:
    """True when a candle list came from _synthetic_history (random fallback data),
    so callers never present derived levels/signals from it as real."""
    return bool(candles) and any(c.get("synthetic") for c in candles)


market_service = MarketDataService()
