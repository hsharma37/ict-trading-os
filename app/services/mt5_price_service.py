"""Live prices AND historical candles from the MT5 bridge (the broker's feed).

The bridge is the app's single market-data source: every price and every
candle the analysis runs on comes from the same feed trades execute on, so
levels/signals/research always line up with the user's MT5 chart. There is
no Yahoo/OANDA fallback — when the bridge isn't configured or reachable the
app reports that instead of analysing a different broker's prices.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

import httpx

from app.services.bridge_config import get_bridge_url, get_bridge_api_key, get_bridge_provider
from app.services.instrument_config import get_instrument


# Timeframes the bridge's /candles endpoint understands (mt5_client._TIMEFRAME_NAMES).
_HISTORY_TIMEFRAMES = {"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"}


class Mt5PriceService:
    def _source(self) -> str:
        """Provider label for price provenance badges ('ctrader' | 'mt5')."""
        return get_bridge_provider()
    def is_configured(self) -> bool:
        # MT5 is THE market-data source: a configured bridge URL is all it takes.
        return bool(get_bridge_url())

    def _headers(self) -> dict:
        h = {"ngrok-skip-browser-warning": "true"}
        key = get_bridge_api_key()
        if key:
            h["X-Bridge-Key"] = key
        return h

    def _mt5_symbol(self, symbol: str) -> str:
        """Broker's symbol name (instrument_config 'mt5' field, else as-is)."""
        config = get_instrument(symbol.upper())
        if config and config.get("mt5"):
            return config["mt5"]
        return symbol.upper()

    def _tick(self, name: str) -> Optional[Dict]:
        # One retry — free tunnels drop the occasional connection.
        for _ in range(2):
            try:
                resp = httpx.get(
                    f"{get_bridge_url()}/tick/{name}",
                    headers=self._headers(),
                    timeout=10,
                )
                if resp.status_code != 200:
                    return None
                data = resp.json()
                if not data or not data.get("price"):
                    return None
                return data
            except Exception:
                continue
        return None

    def _daily(self, name: str) -> Optional[Dict]:
        """Today's + yesterday's daily candle, for change% and OHLC context."""
        try:
            resp = httpx.get(
                f"{get_bridge_url()}/candles/{name}",
                params={"timeframe": "1d", "count": 2},
                headers=self._headers(),
                timeout=8,
            )
            if resp.status_code != 200:
                return None
            candles = (resp.json() or {}).get("candles") or []
            return {"today": candles[-1], "prev": candles[-2] if len(candles) > 1 else candles[-1]} if candles else None
        except Exception:
            return None

    def get_history(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> list:
        """Historical OHLC candles from the broker's own feed (bridge /candles).
        Returns [] when the bridge is unconfigured/unreachable — callers treat
        that as 'no data', never as a cue to fall back to another provider."""
        if not self.is_configured() or timeframe not in _HISTORY_TIMEFRAMES:
            return []
        name = self._mt5_symbol(symbol)
        # One retry — free tunnels drop the occasional connection.
        for _ in range(2):
            try:
                resp = httpx.get(
                    f"{get_bridge_url()}/candles/{name}",
                    params={"timeframe": timeframe, "count": min(int(limit), 5000)},
                    headers=self._headers(),
                    timeout=20,
                )
                if resp.status_code != 200:
                    return []
                # Bridge candles already use the app's shape: time/open/high/low/close/volume.
                return (resp.json() or {}).get("candles") or []
            except Exception:
                continue
        return []

    def get_price(self, symbol: str) -> Optional[Dict]:
        """Compact price dict for MarketDataService.get_price (/market/price)."""
        if not self.is_configured():
            return None
        data = self._tick(self._mt5_symbol(symbol))
        if not data:
            return None
        config = get_instrument(symbol.upper())
        digits = config.get("digits", 5) if config else 5
        return {
            "symbol": symbol.upper(),
            "price": round(data["price"], digits),
            "bid": round(data.get("bid", data["price"]), digits),
            "ask": round(data.get("ask", data["price"]), digits),
            "change": 0.0,       # MT5 tick has no daily change; kept 0 here by design
            "change_pct": 0.0,
            "volume": int(data.get("volume", 0) or 0),
            "timestamp": data.get("time") or datetime.now(timezone.utc).isoformat(),
            "source": self._source(),
        }

    def get_price_detailed(self, symbol: str) -> Optional[Dict]:
        """Richer price for the playground/topbar feed: adds day change% and OHLC
        by combining the live tick with the daily candle. Returns None to fall
        back to the Yahoo/synthetic price_service."""
        if not self.is_configured():
            return None
        name = self._mt5_symbol(symbol)
        data = self._tick(name)
        if not data:
            return None
        price = data["price"]
        daily = self._daily(name)
        today = (daily or {}).get("today") or {}
        prev = (daily or {}).get("prev") or {}
        prev_close = prev.get("close", price) or price
        change = price - prev_close
        change_pct = (change / prev_close * 100.0) if prev_close else 0.0
        config = get_instrument(symbol.upper())
        digits = config.get("digits", 5) if config else 5
        return {
            "symbol": symbol.upper(),
            "price": round(price, digits),
            "bid": round(data.get("bid", price), digits),
            "ask": round(data.get("ask", price), digits),
            "change": round(change, digits),
            "change_percent": round(change_pct, 3),
            "high": round(today.get("high", price), digits),
            "low": round(today.get("low", price), digits),
            "open": round(today.get("open", price), digits),
            "prev_close": round(prev_close, digits),
            "volume": int(data.get("volume", 0) or 0),
            "timestamp": data.get("time") or datetime.now(timezone.utc).isoformat(),
            "source": self._source(),
        }


mt5_price_service = Mt5PriceService()
