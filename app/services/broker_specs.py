"""Broker contract specs (tick value/size) straight from MT5, for exact sizing.

Static per-symbol pip values are only correct for USD-quoted pairs; CAD/JPY-quoted
pairs (USDCAD, USDJPY) differ and drift with the rate. When the bridge is
connected we use the broker's own `trade_tick_value` (in the account currency),
so risk→lot sizing is exact for every symbol. Cached ~1h (specs rarely change).
"""
from __future__ import annotations

import time
from typing import Dict, Optional

import httpx

from app.services.bridge_config import get_bridge_url, get_bridge_api_key

_TTL = 3600.0
_cache: Dict[str, dict] = {}
_cache_at: Dict[str, float] = {}


def _headers() -> dict:
    h = {"ngrok-skip-browser-warning": "true"}
    key = get_bridge_api_key()
    if key:
        h["X-Bridge-Key"] = key
    return h


def get_specs(symbol: str) -> Optional[dict]:
    """Broker spec for a symbol (tick_value/tick_size/contract_size) or None."""
    symbol = symbol.upper()
    base = get_bridge_url()
    low = (base or "").lower()
    if not base or "localhost" in low or "127.0.0.1" in low:
        return None
    now = time.monotonic()
    if symbol in _cache and (now - _cache_at.get(symbol, 0)) < _TTL:
        return _cache[symbol]
    try:
        r = httpx.get(f"{base}/symbol/{symbol}", headers=_headers(), timeout=8)
        if r.status_code != 200:
            return None
        spec = r.json()
    except Exception:
        return None
    if not isinstance(spec, dict) or not spec.get("tick_value") or not spec.get("tick_size"):
        return None
    _cache[symbol] = spec
    _cache_at[symbol] = now
    return spec


def money_per_lot(symbol: str, price_distance: float) -> Optional[float]:
    """Loss/gain in the account currency for a 1.0-lot move of `price_distance`,
    using the broker's real tick value. None if specs unavailable."""
    spec = get_specs(symbol)
    if not spec:
        return None
    try:
        tick_value = float(spec["tick_value"])
        tick_size = float(spec["tick_size"])
        if tick_size <= 0:
            return None
        return (price_distance / tick_size) * tick_value
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def clear_cache() -> None:
    _cache.clear()
    _cache_at.clear()
