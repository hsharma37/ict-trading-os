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

    def get_price(self, symbol: str) -> Optional[Dict]:
        if not self.is_configured():
            return None
        name = self._mt5_symbol(symbol)
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
            config = get_instrument(symbol.upper())
            digits = config.get("digits", 5) if config else 5
            return {
                "symbol": symbol.upper(),
                "price": round(data["price"], digits),
                "bid": round(data.get("bid", data["price"]), digits),
                "ask": round(data.get("ask", data["price"]), digits),
                "change": 0.0,       # MT5 tick has no daily change; kept 0 by design
                "change_pct": 0.0,
                "volume": int(data.get("volume", 0) or 0),
                "timestamp": data.get("time") or datetime.now(timezone.utc).isoformat(),
                "source": "mt5",
            }
        except Exception:
            return None


mt5_price_service = Mt5PriceService()
