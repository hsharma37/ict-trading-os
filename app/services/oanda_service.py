"""OANDA v20 REST market-data provider.

Real-time FX / metals / index-CFD prices from an OANDA fxTrade account
(practice or live). This is a *data* provider only — it never places orders.

Configuration (env):
    OANDA_API_TOKEN   personal access token from the OANDA account
    OANDA_ACCOUNT_ID  v20 account id, e.g. 101-001-1234567-001
    OANDA_ENV         "practice" (default) or "live"

When the token/account are absent the service reports itself unconfigured and
callers fall back to the existing Yahoo chain, so default behaviour is unchanged.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx

from app.core.config import settings
from app.services.instrument_config import get_instrument

# Fallback symbol -> OANDA instrument map (instrument_config's "oanda" field
# takes precedence). BTCUSD is intentionally omitted; OANDA coverage is
# region-dependent, so it falls back to Yahoo.
_OANDA_NAMES = {
    "EURUSD": "EUR_USD",
    "GBPUSD": "GBP_USD",
    "USDJPY": "USD_JPY",
    "XAUUSD": "XAU_USD",
    "NQ1!": "NAS100_USD",
    "ES1!": "SPX500_USD",
    "CL1!": "WTICO_USD",
}

# app timeframe -> OANDA candle granularity
_GRANULARITY = {
    "1m": "M1", "5m": "M5", "15m": "M15", "30m": "M30",
    "1h": "H1", "4h": "H4", "1d": "D",
}

_HOSTS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}


class OandaService:
    def __init__(self) -> None:
        self._client: Optional[httpx.Client] = None
        # Cache of today's opening mid per instrument, keyed by (name, utc-date),
        # so daily change% costs one extra call per symbol per day.
        self._daily_open: Dict[str, tuple] = {}

    # -- configuration -------------------------------------------------

    def is_configured(self) -> bool:
        if settings.MARKET_DATA_PROVIDER == "yahoo":
            return False
        return bool(settings.OANDA_API_TOKEN and settings.OANDA_ACCOUNT_ID)

    @property
    def _base(self) -> str:
        return _HOSTS.get(settings.OANDA_ENV, _HOSTS["practice"])

    def _http(self) -> httpx.Client:
        # Lazily build a pooled client with the auth header set once.
        if self._client is None:
            self._client = httpx.Client(
                timeout=10.0,
                headers={
                    "Authorization": f"Bearer {settings.OANDA_API_TOKEN}",
                    "Accept-Datetime-Format": "RFC3339",
                },
            )
        return self._client

    def oanda_name(self, symbol: str) -> Optional[str]:
        symbol = symbol.upper()
        config = get_instrument(symbol)
        if config and config.get("oanda"):
            return config["oanda"]
        return _OANDA_NAMES.get(symbol)

    # -- pricing -------------------------------------------------------

    def get_price(self, symbol: str) -> Optional[Dict]:
        """Return a normalized price dict, or None to fall back to Yahoo."""
        if not self.is_configured():
            return None
        name = self.oanda_name(symbol)
        if not name:
            return None
        try:
            resp = self._http().get(
                f"{self._base}/v3/accounts/{settings.OANDA_ACCOUNT_ID}/pricing",
                params={"instruments": name},
            )
            resp.raise_for_status()
            prices = resp.json().get("prices") or []
            if not prices:
                return None
            p = prices[0]
            bid = _first_price(p.get("bids")) or _to_float(p.get("closeoutBid"))
            ask = _first_price(p.get("asks")) or _to_float(p.get("closeoutAsk"))
            if bid is None or ask is None:
                return None
            mid = (bid + ask) / 2.0

            config = get_instrument(symbol.upper())
            digits = config.get("digits", 5) if config else 5

            change = change_pct = 0.0
            open_mid = self._today_open(name)
            if open_mid:
                change = mid - open_mid
                change_pct = (change / open_mid * 100.0) if open_mid else 0.0

            return {
                "symbol": symbol.upper(),
                "price": round(mid, digits),
                "bid": round(bid, digits),
                "ask": round(ask, digits),
                "change": round(change, digits),
                "change_pct": round(change_pct, 3),
                "volume": 0,  # OANDA pricing stream carries no volume
                "timestamp": _iso(p.get("time")),
                "source": "oanda",
                "tradeable": p.get("status", "tradeable") == "tradeable",
            }
        except Exception:
            return None

    def _today_open(self, name: str) -> Optional[float]:
        """Opening mid of the current UTC day, cached once per day per symbol."""
        today = datetime.now(timezone.utc).date().isoformat()
        cached = self._daily_open.get(name)
        if cached and cached[0] == today:
            return cached[1]
        try:
            resp = self._http().get(
                f"{self._base}/v3/instruments/{name}/candles",
                params={"granularity": "D", "count": 1, "price": "M"},
            )
            resp.raise_for_status()
            candles = resp.json().get("candles") or []
            if not candles:
                return None
            open_mid = _to_float(candles[0].get("mid", {}).get("o"))
            if open_mid is not None:
                self._daily_open[name] = (today, open_mid)
            return open_mid
        except Exception:
            return None

    # -- history -------------------------------------------------------

    def get_history(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> Optional[List[Dict]]:
        """Return OHLC candles, or None to fall back to Yahoo."""
        if not self.is_configured():
            return None
        name = self.oanda_name(symbol)
        if not name:
            return None
        granularity = _GRANULARITY.get(timeframe, "H1")
        config = get_instrument(symbol.upper())
        digits = config.get("digits", 5) if config else 5
        try:
            resp = self._http().get(
                f"{self._base}/v3/instruments/{name}/candles",
                params={"granularity": granularity, "count": min(limit, 500), "price": "M"},
            )
            resp.raise_for_status()
            candles = resp.json().get("candles") or []
            out: List[Dict] = []
            for c in candles:
                if not c.get("complete", True):
                    continue
                mid = c.get("mid", {})
                o, h, l, cl = (_to_float(mid.get(k)) for k in ("o", "h", "l", "c"))
                if None in (o, h, l, cl):
                    continue
                out.append({
                    "time": _epoch(c.get("time")),
                    "open": round(o, digits),
                    "high": round(h, digits),
                    "low": round(l, digits),
                    "close": round(cl, digits),
                    "volume": int(c.get("volume", 0) or 0),
                })
            return out or None
        except Exception:
            return None

    def status(self) -> Dict:
        return {
            "provider": "oanda",
            "configured": self.is_configured(),
            "env": settings.OANDA_ENV,
            "account_set": bool(settings.OANDA_ACCOUNT_ID),
            "token_set": bool(settings.OANDA_API_TOKEN),
        }


def _to_float(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _first_price(book) -> Optional[float]:
    if isinstance(book, list) and book:
        return _to_float(book[0].get("price"))
    return None


def _iso(oanda_time: Optional[str]) -> str:
    """Normalize OANDA RFC3339 time to a UTC ISO string; fall back to now."""
    if oanda_time:
        try:
            return datetime.fromisoformat(oanda_time.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError):
            pass
    return datetime.now(timezone.utc).isoformat()


def _epoch(oanda_time: Optional[str]) -> int:
    if oanda_time:
        try:
            return int(datetime.fromisoformat(oanda_time.replace("Z", "+00:00")).timestamp())
        except (ValueError, TypeError):
            pass
    return int(datetime.now(timezone.utc).timestamp())


oanda_service = OandaService()
