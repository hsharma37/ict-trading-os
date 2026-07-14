"""Live prices from the MT5 bridge (the broker's own feed).

When MARKET_DATA_PROVIDER=mt5, the app prices instruments from the same feed
it executes on, so displayed prices match fills exactly (no Yahoo/OANDA gap).
This calls the bridge's /tick endpoint over HTTP; the bridge itself talks to
the MetaTrader5 terminal. Falls through (returns None) whenever the bridge
isn't configured/reachable or the symbol isn't available.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

import httpx

from app.core.config import settings
from app.services.instrument_config import get_instrument


class Mt5PriceService:
    def is_configured(self) -> bool:
        # Explicit opt-in: only price from MT5 when asked to, since every quote
        # then depends on the (single, Windows-hosted) bridge being reachable.
        return settings.MARKET_DATA_PROVIDER == "mt5" and bool(settings.MT5_BRIDGE_URL)

    def _headers(self) -> dict:
        if settings.MT5_BRIDGE_API_KEY:
            return {"X-Bridge-Key": settings.MT5_BRIDGE_API_KEY}
        return {}

    def _mt5_symbol(self, symbol: str) -> str:
        """Broker's symbol name (instrument_config 'mt5' field, else as-is)."""
        config = get_instrument(symbol.upper())
        if config and config.get("mt5"):
            return config["mt5"]
        return symbol.upper()

    def _tick(self, name: str) -> Optional[Dict]:
        try:
            resp = httpx.get(
                f"{settings.MT5_BRIDGE_URL}/tick/{name}",
                headers=self._headers(),
                timeout=8,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            if not data or not data.get("price"):
                return None
            return data
        except Exception:
            return None

    def _daily(self, name: str) -> Optional[Dict]:
        """Today's + yesterday's daily candle, for change% and OHLC context."""
        try:
            resp = httpx.get(
                f"{settings.MT5_BRIDGE_URL}/candles/{name}",
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
            "source": "mt5",
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
            "source": "mt5",
        }


mt5_price_service = Mt5PriceService()
