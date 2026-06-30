"""
Price Service — Live market data fetching using correct Yahoo Finance tickers.
Uses instrument_config for accurate futures/forex/crypto tickers and httpx for fast API calls.
Caches results for 15 seconds.
"""
import time
import threading
import httpx
from typing import Dict, Optional, Any
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
    timestamp: float
    kind: str
    digits: int


class PriceService:
    """Fetches and caches live market prices using correct Yahoo Finance tickers."""

    def __init__(self, cache_ttl: int = 15):
        self.cache: Dict[str, PriceData] = {}
        self.cache_ttl = cache_ttl
        self.last_fetch: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._headers = {'User-Agent': 'Mozilla/5.0'}

    def fetch_price(self, symbol: str) -> Optional[PriceData]:
        """Fetch price for a single symbol, using cache if available."""
        now = time.time()
        symbol = symbol.upper()

        with self._lock:
            if symbol in self.cache and symbol in self.last_fetch:
                if now - self.last_fetch[symbol] < self.cache_ttl:
                    return self.cache[symbol]

        config = get_instrument(symbol)
        if not config:
            return None

        yahoo_ticker = config.get("yahoo", config.get("ticker", symbol))

        try:
            url = f'https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_ticker}?range=1d&interval=1m'
            with httpx.Client(timeout=10.0, headers=self._headers) as client:
                resp = client.get(url)
                resp.raise_for_status()
                payload = resp.json()

            result = payload.get("chart", {}).get("result", [None])[0]
            if not result:
                return self._mock_price(symbol, config)

            meta = result.get("meta", {})
            quote = result.get("indicators", {}).get("quote", [{}])[0]
            timestamps = result.get("timestamp", [])

            close_prices = quote.get("close", [])
            high_prices = quote.get("high", [])
            low_prices = quote.get("low", [])
            open_prices = quote.get("open", [])
            volumes = quote.get("volume", [])

            current_price = meta.get("regularMarketPrice", 0)
            prev_close = meta.get("previousClose", meta.get("chartPreviousClose", 0))
            if not current_price and close_prices:
                current_price = next((c for c in reversed(close_prices) if c), 0)
            if not prev_close and close_prices and len(close_prices) > 1:
                prev_close = next((c for c in reversed(close_prices[:-1]) if c), 0)

            if not current_price:
                return self._mock_price(symbol, config)

            change = current_price - prev_close if prev_close else 0
            change_pct = (change / prev_close * 100) if prev_close else 0

            high = max([h for h in high_prices if h]) if high_prices else current_price
            low = min([l for l in low_prices if l]) if low_prices else current_price
            open_ = next((o for o in open_prices if o), current_price) if open_prices else current_price
            volume = sum([v for v in volumes if v]) if volumes else 0

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
                timestamp=now,
                kind=config.get("kind", "unknown"),
                digits=digits,
            )

            with self._lock:
                self.cache[symbol] = data
                self.last_fetch[symbol] = now

            return data

        except Exception as e:
            print(f"[PriceService] Error fetching {symbol} ({yahoo_ticker}): {e}")
            return self._mock_price(symbol, config)

    def _mock_price(self, symbol: str, config: Dict) -> PriceData:
        """Return mock price data when API fails."""
        now = time.time()
        base_prices = {
            "NQ1!": 20150.0, "ES1!": 5850.0, "EURUSD": 1.0830,
            "GBPUSD": 1.2650, "XAUUSD": 2350.0, "USDJPY": 157.50,
            "BTCUSD": 67500, "CL1!": 78.50,
        }
        base = base_prices.get(symbol, 100.0)
        import random
        move = (random.random() - 0.5) * base * 0.001
        price = round(base + move, config.get("digits", 5))
        digits = config.get("digits", 5)

        return PriceData(
            symbol=symbol,
            label=config.get("label", symbol) + " (mock)",
            price=price,
            change=round(move, digits),
            change_percent=round((move / base) * 100, 3),
            high=round(price + abs(move), digits),
            low=round(price - abs(move), digits),
            open=round(base, digits),
            volume=0,
            prev_close=round(base, digits),
            timestamp=now,
            kind=config.get("kind", "unknown"),
            digits=digits,
        )

    def fetch_all_prices(self) -> Dict[str, PriceData]:
        """Fetch prices for all configured instruments in parallel."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        all_instruments = get_all_instruments()
        result = {}
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(self.fetch_price, sym): sym for sym in all_instruments}
            for future in as_completed(futures):
                sym = futures[future]
                try:
                    data = future.result()
                    if data:
                        result[sym] = data
                except Exception as e:
                    print(f"[PriceService] Parallel fetch failed for {sym}: {e}")
        return result

    def get_price(self, symbol: str) -> Optional[PriceData]:
        """Get price from cache or fetch."""
        return self.fetch_price(symbol)

    def get_all_prices(self) -> Dict[str, PriceData]:
        """Get all prices from cache."""
        return {s: self.cache[s] for s in self.cache if s in get_all_instruments()}


# Global instance
price_service = PriceService()
