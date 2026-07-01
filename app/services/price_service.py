"""
Price Service — Robust live market data with multi-source fallback.

Fallback chain:
1. Yahoo Finance (with 60s cache to avoid rate limits)
2. Persistent file cache (last known good price)
3. Simple web scraper for gold/forex
4. Synthetic base prices (only as absolute last resort)

Key changes from v1:
- 60s cache TTL instead of 15s
- Persistent JSON cache file across restarts
- Returns last known price on API failure instead of random synthetic
- Updated synthetic base prices to current market levels
- Added web scraper fallback for gold/forex
"""
import time
import threading
import httpx
import json
import os
from typing import Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from app.services.instrument_config import get_instrument, get_all_instruments


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
    timestamp: str
    kind: str
    digits: int


CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "price_cache.json")


def _load_persistent_cache() -> Dict[str, dict]:
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_persistent_cache(data: Dict[str, dict]) -> None:
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


class PriceService:
    """Fetches and caches live market prices with robust fallback chain."""

    # Current market-level base prices (July 2026) — update when user reports drift
    SYNTHETIC_BASE = {
        "NQ1!": 30000.0,    # E-mini Nasdaq-100 futures (user confirmed ~30k)
        "ES1!": 7800.0,     # E-mini S&P 500 futures (proportionally ~7.8k)
        "EURUSD": 1.1250,   # EUR/USD spot
        "GBPUSD": 1.3050,   # GBP/USD spot
        "XAUUSD": 4050.0,   # Gold spot (user confirmed ~4030)
        "USDJPY": 162.50,   # USD/JPY spot
        "BTCUSD": 135000.0, # Bitcoin (~135k in 2026)
        "CL1!": 72.50,      # Crude Oil futures
    }

    def __init__(self, cache_ttl: int = 60):
        self.cache: Dict[str, PriceData] = {}
        self.cache_ttl = cache_ttl
        self.last_fetch: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'application/json',
        }
        # Load persistent cache into memory
        persistent = _load_persistent_cache()
        for sym, data in persistent.items():
            try:
                self.cache[sym.upper()] = PriceData(**data)
            except Exception:
                pass

    def _save_to_persistent(self, symbol: str, data: PriceData) -> None:
        """Save price to persistent file cache."""
        persistent = _load_persistent_cache()
        persistent[symbol.upper()] = asdict(data)
        _save_persistent_cache(persistent)

    def _get_from_persistent(self, symbol: str) -> Optional[PriceData]:
        """Get price from persistent cache."""
        persistent = _load_persistent_cache()
        data = persistent.get(symbol.upper())
        if data:
            try:
                # Check if data is not too old (6 hours)
                ts = datetime.fromisoformat(data.get('timestamp', datetime.utcnow().isoformat()))
                age = (datetime.utcnow() - ts).total_seconds()
                if age < 21600:  # 6 hours
                    return PriceData(**data)
            except Exception:
                pass
        return None

    def fetch_price(self, symbol: str) -> Optional[PriceData]:
        """Fetch price with robust fallback chain."""
        now = time.time()
        symbol = symbol.upper()

        # 1. Check in-memory cache
        with self._lock:
            if symbol in self.cache and symbol in self.last_fetch:
                if now - self.last_fetch[symbol] < self.cache_ttl:
                    return self.cache[symbol]

        config = get_instrument(symbol)
        if not config:
            return None

        yahoo_ticker = config.get("yahoo", config.get("ticker", symbol))

        # 2. Try Yahoo Finance
        try:
            url = f'https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_ticker}?range=1d&interval=1m'
            with httpx.Client(timeout=10.0, headers=self._headers) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    payload = resp.json()
                    result = payload.get("chart", {}).get("result", [None])[0]
                    if result:
                        meta = result.get("meta", {})
                        quote = result.get("indicators", {}).get("quote", [{}])[0]

                        close_prices = quote.get("close", [])
                        high_prices = quote.get("high", [])
                        low_prices = quote.get("low", [])
                        open_prices = quote.get("open", [])
                        volumes = quote.get("volume", [])

                        current_price = meta.get("regularMarketPrice", 0)
                        prev_close = meta.get("previousClose", meta.get("chartPreviousClose", 0))
                        if not current_price and close_prices:
                            current_price = next((c for c in reversed(close_prices) if c is not None), 0)
                        if not prev_close and close_prices and len(close_prices) > 1:
                            prev_close = next((c for c in reversed(close_prices[:-1]) if c is not None), 0)

                        if current_price and current_price > 0:
                            change = current_price - prev_close if prev_close else 0
                            change_pct = (change / prev_close * 100) if prev_close else 0
                            high = max([h for h in high_prices if h is not None]) if high_prices else current_price
                            low = min([l for l in low_prices if l is not None]) if low_prices else current_price
                            open_ = next((o for o in open_prices if o is not None), current_price) if open_prices else current_price
                            volume = sum([v for v in volumes if v is not None]) if volumes else 0

                            digits = config.get("digits", 5)
                            data = PriceData(
                                symbol=symbol,
                                label=config.get("label", symbol),
                                price=round(current_price, digits),
                                change=round(change, digits),
                                change_percent=round(change_pct, 3),
                                high=round(high, digits),
                                low=round(low, digits),
                                open=round(open_, digits),
                                volume=int(volume) if volume else 0,
                                prev_close=round(prev_close, digits) if prev_close else round(current_price, digits),
                                timestamp=datetime.utcnow().isoformat(),
                                kind=config.get("kind", "unknown"),
                                digits=digits,
                            )
                            with self._lock:
                                self.cache[symbol] = data
                                self.last_fetch[symbol] = now
                            self._save_to_persistent(symbol, data)
                            return data
        except Exception as e:
            print(f"[PriceService] Yahoo fetch failed for {symbol}: {e}")

        # 3. Try web scraper fallback for specific symbols
        scraped = self._scrape_price(symbol, config)
        if scraped:
            with self._lock:
                self.cache[symbol] = scraped
                self.last_fetch[symbol] = now
            self._save_to_persistent(symbol, scraped)
            return scraped

        # 4. Try persistent cache (last known good price)
        persistent = self._get_from_persistent(symbol)
        if persistent:
            print(f"[PriceService] Using persistent cache for {symbol}: {persistent.price}")
            with self._lock:
                self.cache[symbol] = persistent
                self.last_fetch[symbol] = now
            return persistent

        # 5. Absolute last resort: synthetic base price
        print(f"[PriceService] Using synthetic price for {symbol}")
        return self._synthetic_price(symbol, config)

    def _scrape_price(self, symbol: str, config: Dict) -> Optional[PriceData]:
        """Try to scrape price from alternative sources."""
        now = time.time()
        digits = config.get("digits", 5)

        # Try Kitco gold scraper for XAUUSD
        if symbol == "XAUUSD":
            try:
                url = "https://www.kitco.com/charts/gold.html"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                with httpx.Client(timeout=10.0, headers=headers) as client:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        html = resp.text
                        # Look for price in the page
                        import re
                        # Try to find the current price in various formats
                        patterns = [
                            r'"price":\s*([\d,]+\.?\d*)',
                            r'Gold[^\d]*(\d{3,4}\.\d{2})',
                            r'>(\d{3,4}\.\d{2})\s*<',
                        ]
                        for pattern in patterns:
                            match = re.search(pattern, html)
                            if match:
                                price_str = match.group(1).replace(',', '')
                                price = float(price_str)
                                if 2000 < price < 10000:  # Sanity check for gold
                                    return PriceData(
                                        symbol=symbol,
                                        label=config.get("label", symbol) + " (scraped)",
                                        price=round(price, digits),
                                        change=0.0,
                                        change_percent=0.0,
                                        high=round(price, digits),
                                        low=round(price, digits),
                                        open=round(price, digits),
                                        volume=0,
                                        prev_close=round(price, digits),
                                        timestamp=datetime.utcnow().isoformat(),
                                        kind=config.get("kind", "unknown"),
                                        digits=digits,
                                    )
            except Exception as e:
                print(f"[PriceService] Scrape failed for {symbol}: {e}")

        return None

    def _synthetic_price(self, symbol: str, config: Dict) -> PriceData:
        """Return a realistic base price when all other sources fail."""
        now = time.time()
        digits = config.get("digits", 5)
        base = self.SYNTHETIC_BASE.get(symbol, 100.0)

        # Very small drift (0.01%) to show it's synthetic
        import random
        drift = (random.random() - 0.5) * base * 0.0001
        price = round(base + drift, digits)

        return PriceData(
            symbol=symbol,
            label=config.get("label", symbol) + " (synthetic)",
            price=price,
            change=round(drift, digits),
            change_percent=round((drift / base) * 100, 3),
            high=round(price + abs(drift), digits),
            low=round(price - abs(drift), digits),
            open=round(base, digits),
            volume=0,
            prev_close=round(base, digits),
            timestamp=datetime.utcnow().isoformat(),
            kind=config.get("kind", "unknown"),
            digits=digits,
        )

    def fetch_all_prices(self) -> Dict[str, PriceData]:
        """Fetch prices for all configured instruments with rate limiting."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        all_instruments = get_all_instruments()
        result = {}

        # Stagger requests to avoid rate limits
        for sym in all_instruments:
            try:
                data = self.fetch_price(sym)
                if data:
                    result[sym] = data
                time.sleep(0.5)  # 500ms delay between requests
            except Exception as e:
                print(f"[PriceService] Fetch failed for {sym}: {e}")

        return result

    def get_price(self, symbol: str) -> Optional[PriceData]:
        """Get price from cache or fetch."""
        return self.fetch_price(symbol)

    def get_all_prices(self) -> Dict[str, PriceData]:
        """Get all prices from cache."""
        return {s: self.cache[s] for s in self.cache if s in get_all_instruments()}


# Global instance
price_service = PriceService()
