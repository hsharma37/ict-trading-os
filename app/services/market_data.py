"""Live market data via Yahoo Finance."""
import httpx
from typing import List, Dict
from datetime import datetime
import random

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

BASE_PRICES = {
    "NQ1!": 18445.25, "ES1!": 5523.75, "EURUSD": 1.08342,
    "GBPUSD": 1.26581, "XAUUSD": 2382.40, "USDJPY": 157.423,
    "BTCUSD": 64820, "CL1!": 82.34
}

class MarketDataService:
    def __init__(self):
        self.price_history = {s: [] for s in SYMBOL_MAP.keys()}

    def _last_valid_value(self, values, default=None):
        if not values:
            return default
        for v in reversed(values):
            if v is not None:
                return v
        return default

    def get_price(self, symbol: str) -> Dict:
        yahoo_sym = SYMBOL_MAP.get(symbol, symbol)
        try:
            url = f'https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_sym}?range=1d&interval=1m'
            headers = {'User-Agent': 'Mozilla/5.0'}
            with httpx.Client(timeout=20.0, headers=headers) as client:
                resp = client.get(url)
                resp.raise_for_status()
                payload = resp.json()
            result = payload.get('chart', {}).get('result')
            if result and len(result) > 0:
                meta = result[0].get('meta', {})
                indicators = result[0].get('indicators', {}).get('quote', [])
                if indicators and len(indicators) > 0:
                    quote = indicators[0]
                    close = quote.get('close', [])
                    high = quote.get('high', [])
                    low = quote.get('low', [])
                    volume = quote.get('volume', [])
                    price = self._last_valid_value(close)
                    if price is None:
                        price = meta.get('regularMarketPrice') or meta.get('previousClose')
                    if price is not None:
                        bid = self._last_valid_value(low, price)
                        ask = self._last_valid_value(high, price)
                        prev = meta.get('previousClose', price)
                        change = price - prev if prev is not None else 0
                        return {
                            'symbol': symbol,
                            'price': round(price, 5),
                            'bid': round(bid, 5) if bid is not None else round(price, 5),
                            'ask': round(ask, 5) if ask is not None else round(price, 5),
                            'change': round(change, 5),
                            'change_pct': round((change / prev * 100), 3) if prev else 0,
                            'volume': int(self._last_valid_value(volume, 0) or 0),
                            'timestamp': datetime.utcnow().isoformat(),
                            'source': 'yahoo'
                        }
        except Exception:
            pass
        base = BASE_PRICES.get(symbol, 100.0)
        price = base + (random.random() - 0.5) * base * 0.001
        return {'symbol': symbol, 'price': round(price, 5), 'timestamp': datetime.utcnow().isoformat(), 'source': 'synthetic'}

    def get_history(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> List[Dict]:
        yahoo_sym = SYMBOL_MAP.get(symbol, symbol)
        tf_map = {"1m": ("1d", "1m"), "5m": ("5d", "5m"), "15m": ("5d", "15m"),
                  "1h": ("1mo", "1h"), "4h": ("3mo", "1h"), "1d": ("6mo", "1d")}
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
        base = BASE_PRICES.get(symbol, 100.0)
        candles = []
        price = base
        for i in range(limit):
            o = price
            c = price + (random.random() - 0.48) * base * 0.002
            h = max(o, c) + random.random() * base * 0.001
            l = min(o, c) - random.random() * base * 0.001
            candles.append({"time": int(datetime.utcnow().timestamp()) - (limit-i)*3600,
                           "open": round(o, 5), "high": round(h, 5), "low": round(l, 5), "close": round(c, 5)})
            price = c
        return candles

market_service = MarketDataService()
