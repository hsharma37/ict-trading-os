"""Single source of truth for instrument prices.

Every price surface in the app (the /market/* endpoints, the topbar, signals,
quant, trade reference prices, ...) resolves through get_quote() here, so a
given symbol shows the *same* value everywhere at a given moment and the data
provider is switched in exactly one place.

Provider order (per settings.MARKET_DATA_PROVIDER):
  manual override -> MT5 (when provider=mt5) -> OANDA (when configured)
  -> Yahoo/scrape/synthetic (price_service). Each step falls through on failure.

A short in-process TTL cache makes concurrent reads across pages consistent
and shields the (single, Windows-hosted) MT5 bridge from redundant hits.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from app.core.config import settings
from app.services.instrument_config import get_instrument
from app.services.mt5_price_service import mt5_price_service
from app.services.oanda_service import oanda_service
from app.services.price_service import price_service

# symbol -> (quote, monotonic_expiry)
_CACHE: Dict[str, tuple] = {}
_TTL_SECONDS = 2.5


def clear_cache() -> None:
    _CACHE.clear()


def _stale(timestamp: str, max_age_s: int = 120) -> bool:
    from datetime import datetime
    try:
        ts = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        now = datetime.now(ts.tzinfo) if ts.tzinfo else datetime.utcnow()
        return (now - ts).total_seconds() > max_age_s
    except (ValueError, TypeError):
        return False


def derive_source(label: str) -> str:
    """Classify a price's provenance from its label suffix (yahoo/scraped/synthetic)."""
    l = (label or "").lower()
    if "(synthetic)" in l:
        return "synthetic"
    if any(s in l for s in ("(kitco)", "(gold.org)", "(investing.com)", "(scraped)")):
        return "scraped"
    return "yahoo"


# Public aliases (single home for these helpers now that playground is gone).
_derive_source_from_label = derive_source
is_stale = _stale


def _canonical(symbol: str, fields: Dict[str, Any], source: str) -> Dict[str, Any]:
    """Assemble the one canonical quote shape from a provider's partial data.

    Superset of both historical shapes (market_data's price/bid/ask/change_pct
    and playground's change_percent/OHLC/label/kind/digits) so every existing
    consumer keeps working.
    """
    symbol = symbol.upper()
    config = get_instrument(symbol) or {}
    digits = fields.get("digits", config.get("digits", 5))
    price = fields.get("price", 0) or 0
    bid = fields.get("bid", price)
    ask = fields.get("ask", price)
    change = fields.get("change", 0) or 0
    change_pct = fields.get("change_percent", fields.get("change_pct", 0) or 0)
    ts = fields.get("timestamp")
    return {
        "symbol": symbol,
        "label": fields.get("label", config.get("label", symbol)),
        "kind": fields.get("kind", config.get("kind", "")),
        "digits": digits,
        "price": round(price, digits),
        "bid": round(bid, digits),
        "ask": round(ask, digits),
        "change": round(change, digits),
        "change_pct": round(change_pct, 3),          # legacy key (market path)
        "change_percent": round(change_pct, 3),      # playground key
        "high": round(fields.get("high", price), digits),
        "low": round(fields.get("low", price), digits),
        "open": round(fields.get("open", price), digits),
        "prev_close": round(fields.get("prev_close", price), digits),
        "volume": int(fields.get("volume", 0) or 0),
        "timestamp": ts,
        "source": source,
        "stale": _stale(ts) if ts else False,
    }


def _resolve(symbol: str) -> Dict[str, Any]:
    symbol = symbol.upper()

    # 1. Manual override (e.g. an MT5/broker price pinned via the market router).
    from app.services.market_data import market_service  # late import: avoids cycle
    manual = market_service.get_manual_price(symbol)
    if manual and manual.get("price"):
        return _canonical(symbol, {**manual, "timestamp": manual.get("timestamp")}, source="manual")

    # 2. MT5 broker feed (only when explicitly selected; see mt5_price_service).
    if mt5_price_service.is_configured():
        q = mt5_price_service.get_price_detailed(symbol)
        if q and q.get("price"):
            return _canonical(symbol, q, source="mt5")

    # 3. OANDA (when configured and not forced to yahoo).
    if oanda_service.is_configured():
        oq = oanda_service.get_price(symbol)
        if oq and oq.get("price"):
            return _canonical(symbol, oq, source="oanda")

    # 4. Yahoo -> scrape -> synthetic (price_service handles that chain itself).
    pdata = price_service.fetch_price(symbol)
    if pdata and getattr(pdata, "price", 0):
        return _canonical(symbol, {
            "label": pdata.label, "kind": pdata.kind, "digits": pdata.digits,
            "price": pdata.price, "change": pdata.change, "change_percent": pdata.change_percent,
            "high": pdata.high, "low": pdata.low, "open": pdata.open,
            "prev_close": pdata.prev_close, "volume": pdata.volume, "timestamp": pdata.timestamp,
        }, source=_derive_source_from_label(pdata.label))

    return _canonical(symbol, {"price": 0, "timestamp": None}, source="unavailable")


def get_quote(symbol: str) -> Dict[str, Any]:
    """The one function every price surface calls. Cached for _TTL_SECONDS so
    all pages see the same value at a given moment."""
    symbol = symbol.upper()
    now = time.monotonic()
    cached = _CACHE.get(symbol)
    if cached and cached[1] > now:
        return cached[0]
    quote = _resolve(symbol)
    # Only cache real quotes, so a transient failure isn't pinned for the TTL.
    if quote.get("price"):
        _CACHE[symbol] = (quote, now + _TTL_SECONDS)
    return quote
