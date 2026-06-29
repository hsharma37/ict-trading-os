"""
Price Service — Live market data fetching for instruments.

Uses yfinance to fetch real-time prices for stocks, forex, crypto, and commodities.
Caches results for 30 seconds to avoid rate limiting.
"""
import time
import threading
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    yf = None
    YFINANCE_AVAILABLE = False


@dataclass
class PriceData:
    symbol: str
    label: str
    price: float
    change: float
    change_percent: float
    high: float
    low: float
    open: float
    volume: int
    prev_close: float
    timestamp: float
    kind: str
    digits: int


# ── Instrument configuration ───────────────────
INSTRUMENTS = {
    "NQ1!": {
        "ticker": "^IXIC",
        "label": "NQ1! (Nasdaq)",
        "kind": "index",
        "digits": 2,
        "pip_digits": 1,
        "pip_val": 1,
        "mult": 20,
    },
    "ES1!": {
        "ticker": "^GSPC",
        "label": "ES1! (S&P 500)",
        "kind": "index",
        "digits": 2,
        "pip_digits": 1,
        "pip_val": 1,
        "mult": 50,
    },
    "EURUSD": {
        "ticker": "EURUSD=X",
        "label": "EUR/USD",
        "kind": "fx",
        "digits": 5,
        "pip_digits": 4,
        "pip_val": 10,
        "mult": 100000,
    },
    "GBPUSD": {
        "ticker": "GBPUSD=X",
        "label": "GBP/USD",
        "kind": "fx",
        "digits": 5,
        "pip_digits": 4,
        "pip_val": 10,
        "mult": 100000,
    },
    "XAUUSD": {
        "ticker": "XAUUSD=X",
        "label": "XAU/USD (Gold)",
        "kind": "metal",
        "digits": 2,
        "pip_digits": 2,
        "pip_val": 10,
        "mult": 100,
    },
    "USDJPY": {
        "ticker": "USDJPY=X",
        "label": "USD/JPY",
        "kind": "fx",
        "digits": 3,
        "pip_digits": 2,
        "pip_val": 9.1,
        "mult": 100000,
    },
    "BTCUSD": {
        "ticker": "BTC-USD",
        "label": "BTC/USD",
        "kind": "crypto",
        "digits": 0,
        "pip_digits": 0,
        "pip_val": 1,
        "mult": 1,
    },
    "CL1!": {
        "ticker": "CL=F",
        "label": "CL1! (Crude Oil)",
        "kind": "commodity",
        "digits": 2,
        "pip_digits": 2,
        "pip_val": 10,
        "mult": 1000,
    },
}


class PriceService:
    """Fetches and caches live market prices."""

    def __init__(self, cache_ttl: int = 30):
        self.cache: Dict[str, PriceData] = {}
        self.cache_ttl = cache_ttl
        self.last_fetch: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        return INSTRUMENTS.get(symbol)

    def fetch_price(self, symbol: str) -> Optional[PriceData]:
        """Fetch price for a single symbol, using cache if available."""
        now = time.time()

        with self._lock:
            if symbol in self.cache and symbol in self.last_fetch:
                if now - self.last_fetch[symbol] < self.cache_ttl:
                    return self.cache[symbol]

        if not YFINANCE_AVAILABLE or yf is None:
            return self._mock_price(symbol)

        config = self._get_ticker(symbol)
        if not config:
            return None

        try:
            ticker = yf.Ticker(config["ticker"])
            hist = ticker.history(period="1d", interval="1m")
            if hist.empty:
                info = ticker.info
                price = info.get("regularMarketPrice", info.get("previousClose", 0))
                prev = info.get("previousClose", price)
                high = info.get("regularMarketDayHigh", price)
                low = info.get("regularMarketDayLow", price)
                open_ = info.get("regularMarketOpen", price)
                volume = info.get("regularMarketVolume", 0)
            else:
                latest = hist.iloc[-1]
                price = latest["Close"]
                high = latest["High"] if "High" in hist.columns else price
                low = latest["Low"] if "Low" in hist.columns else price
                open_ = hist["Open"].iloc[0] if "Open" in hist.columns else price
                volume = int(latest["Volume"]) if "Volume" in hist.columns else 0
                prev = hist["Close"].iloc[-2] if len(hist) > 1 else price

            change = price - prev if prev else 0
            change_pct = (change / prev * 100) if prev else 0

            data = PriceData(
                symbol=symbol,
                label=config["label"],
                price=round(price, config["digits"]),
                change=round(change, config["digits"]),
                change_percent=round(change_pct, 3),
                high=round(high, config["digits"]),
                low=round(low, config["digits"]),
                open=round(open_, config["digits"]),
                volume=int(volume) if volume else 0,
                prev_close=round(prev, config["digits"]),
                timestamp=now,
                kind=config["kind"],
                digits=config["digits"],
            )

            with self._lock:
                self.cache[symbol] = data
                self.last_fetch[symbol] = now

            return data

        except Exception as e:
            print(f"[PriceService] Error fetching {symbol}: {e}")
            return self._mock_price(symbol)

    def _mock_price(self, symbol: str) -> Optional[PriceData]:
        """Return mock price data when yfinance is unavailable."""
        config = self._get_ticker(symbol)
        if not config:
            return None

        now = time.time()
        # Check if we have a cached mock price
        with self._lock:
            if symbol in self.cache and now - self.last_fetch.get(symbol, 0) < self.cache_ttl:
                return self.cache[symbol]

        # Base mock prices
        base_prices = {
            "NQ1!": 18445.25,
            "ES1!": 5523.75,
            "EURUSD": 1.08342,
            "GBPUSD": 1.26581,
            "XAUUSD": 2382.40,
            "USDJPY": 157.423,
            "BTCUSD": 64820,
            "CL1!": 82.34,
        }
        base = base_prices.get(symbol, 100.0)
        # Add small random movement
        import random
        move = (random.random() - 0.5) * base * 0.002
        price = round(base + move, config["digits"])
        change = round(move, config["digits"])
        change_pct = round((change / base) * 100, 3) if base else 0

        data = PriceData(
            symbol=symbol,
            label=config["label"],
            price=price,
            change=change,
            change_percent=change_pct,
            high=round(price + abs(move), config["digits"]),
            low=round(price - abs(move), config["digits"]),
            open=round(base, config["digits"]),
            volume=int(random.random() * 1000000),
            prev_close=round(base, config["digits"]),
            timestamp=now,
            kind=config["kind"],
            digits=config["digits"],
        )

        with self._lock:
            self.cache[symbol] = data
            self.last_fetch[symbol] = now

        return data

    def fetch_all_prices(self) -> Dict[str, PriceData]:
        """Fetch prices for all configured instruments."""
        result = {}
        for symbol in INSTRUMENTS:
            data = self.fetch_price(symbol)
            if data:
                result[symbol] = data
        return result

    def get_price(self, symbol: str) -> Optional[PriceData]:
        """Get price from cache or fetch."""
        return self.fetch_price(symbol)

    def get_all_prices(self) -> Dict[str, PriceData]:
        """Get all prices from cache."""
        return {s: self.cache[s] for s in self.cache if s in INSTRUMENTS}


# Global instance
price_service = PriceService()
