"""Live market data via Yahoo Finance."""
import httpx
from typing import List, Dict, Optional
from datetime import datetime
import random

from app.services.instrument_config import get_instrument
from app.services.price_service import price_service
from app.services.oanda_service import oanda_service
from app.services.mt5_price_service import mt5_price_service

# Deprecated hardcoded map — now using instrument_config for all ticker lookups
# Kept for backward compatibility only
SYMBOL_MAP = {
    "NQ1!": "NQ=F", "ES1!": "ES=F", "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X", "XAUUSD": "GC=F", "USDJPY": "USDJPY=X",
    "BTCUSD": "BTC-USD", "CL1!": "CL=F",
}

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
        self.price_history = {s: [] for s in SYMBOL_MAP.keys()}
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
        """Clear manual price override and return to Yahoo Finance."""
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

    def _last_valid_value(self, values, default=None):
        if not values:
            return default
        for v in reversed(values):
            if v is not None:
                return v
        return default

    def _get_yahoo_ticker(self, symbol: str) -> str:
        """Resolve symbol to Yahoo Finance ticker using instrument_config."""
        config = get_instrument(symbol)
        if config:
            return config.get("yahoo", config.get("ticker", symbol))
        return SYMBOL_MAP.get(symbol, symbol)

    def get_price(self, symbol: str) -> Dict:
        """Single entry point for a live price. Delegates to quote_service, the
        one place that resolves the provider (manual -> MT5 -> OANDA -> Yahoo)
        and caches, so every page shows the same value from the same source."""
        from app.services.quote_service import get_quote  # late import: avoids cycle
        return get_quote(symbol)

    def get_history(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> List[Dict]:
        # Prefer OANDA candles when configured (native 4H, tighter data).
        oanda_candles = oanda_service.get_history(symbol, timeframe, limit)
        if oanda_candles:
            return oanda_candles

        yahoo_sym = self._get_yahoo_ticker(symbol)
        tf_map = {
            "1m": ("1d", "1m"), "5m": ("5d", "5m"), "15m": ("5d", "15m"),
            "1h": ("1mo", "1h"), "4h": ("3mo", "1h"),  # 4h uses 1h data (Yahoo limitation)
            "1d": ("6mo", "1d")
        }
        period, interval = tf_map.get(timeframe, ("1mo", "1h"))

        try:
            url = f'https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_sym}?period={period}&interval={interval}&events=div%2Csplit'
            headers = {'User-Agent': 'Mozilla/5.0'}
            with httpx.Client(timeout=20.0, headers=headers) as client:
                resp = client.get(url)
                resp.raise_for_status()
                payload = resp.json()
            result = payload.get('chart', {}).get('result')
            if result and len(result) > 0:
                quotes = result[0].get('indicators', {}).get('quote', [])
                if quotes and len(quotes) > 0:
                    quote = quotes[0]
                    close = quote.get('close', [])
                    open_ = quote.get('open', [])
                    high = quote.get('high', [])
                    low = quote.get('low', [])
                    volume = quote.get('volume', [])
                    candles = []
                    for idx, ts in enumerate(result[0].get('timestamp', [])):
                        if idx >= len(close):
                            break
                        c = close[idx]
                        o = open_[idx] if idx < len(open_) else None
                        h = high[idx] if idx < len(high) else None
                        l = low[idx] if idx < len(low) else None
                        v = volume[idx] if idx < len(volume) else 0
                        if c is None or o is None or h is None or l is None:
                            continue
                        candles.append({
                            'time': int(ts),
                            'open': round(o, 5),
                            'high': round(h, 5),
                            'low': round(l, 5),
                            'close': round(c, 5),
                            'volume': int(v or 0)
                        })
                    return candles[-limit:] if len(candles) > limit else candles
        except Exception:
            pass
        return self._synthetic_history(symbol, limit)

    def _synthetic_history(self, symbol: str, limit: int) -> List[Dict]:
        # Use price_service for a realistic base price
        try:
            pdata = price_service.get_price(symbol)
            base = pdata.price if pdata else 100.0
        except Exception:
            base = 100.0
        candles = []
        price = base
        for i in range(limit):
            o = price
            c = price + (random.random() - 0.48) * base * 0.002
            h = max(o, c) + random.random() * base * 0.001
            l = min(o, c) - random.random() * base * 0.001
            candles.append({"time": int(datetime.utcnow().timestamp()) - (limit-i)*3600,
                           "open": round(o, 5), "high": round(h, 5), "low": round(l, 5), "close": round(c, 5),
                           # Mark every fabricated bar so downstream analysis can refuse or
                           # clearly label it — these are RANDOM, not market data.
                           "synthetic": True})
            price = c
        return candles


def history_is_synthetic(candles: List[Dict]) -> bool:
    """True when a candle list came from _synthetic_history (random fallback data),
    so callers never present derived levels/signals from it as real."""
    return bool(candles) and any(c.get("synthetic") for c in candles)


market_service = MarketDataService()
