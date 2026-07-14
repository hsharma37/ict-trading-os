"""Runtime-resolvable MT5 bridge URL.

The free Cloudflare *quick* tunnel URL changes on every restart, which used to
mean editing the ``MT5_BRIDGE_URL`` env var on Vercel and redeploying each time.
This resolver lets the URL be overridden at runtime from the app-settings row
(editable in the UI), falling back to the ``MT5_BRIDGE_URL`` env var. The API
key stays env-only (it's a secret and rarely changes).

A tiny in-process TTL cache keeps the hot price path from hitting the DB on
every quote poll.
"""
from __future__ import annotations

import time
from typing import Optional

from app.core.config import settings

_CACHE_TTL = 5.0  # seconds
_cached_url: Optional[str] = None
_cached_at: float = 0.0


def _normalize(url: str) -> str:
    """Trim whitespace and any trailing slash; leave scheme untouched."""
    url = (url or "").strip()
    while url.endswith("/"):
        url = url[:-1]
    return url


def _read_override() -> str:
    """Return the DB-stored bridge URL override, or '' if unset/unavailable."""
    try:
        from app.core.database import db
        row = db.find_one("settings", "global") or {}
        return _normalize(row.get("mt5_bridge_url") or "")
    except Exception:
        return ""


def get_bridge_url(force_refresh: bool = False) -> str:
    """Effective bridge base URL: DB override if set, else the env value."""
    global _cached_url, _cached_at
    now = _monotonic()
    if not force_refresh and _cached_url is not None and (now - _cached_at) < _CACHE_TTL:
        return _cached_url
    resolved = _read_override() or _normalize(settings.MT5_BRIDGE_URL)
    _cached_url = resolved
    _cached_at = now
    return resolved


def get_bridge_api_key() -> str:
    """Shared secret for the bridge (env-only)."""
    return settings.MT5_BRIDGE_API_KEY


def set_bridge_url(url: str) -> str:
    """Persist a bridge URL override to the settings row and refresh the cache.

    Passing an empty string clears the override (falls back to the env value).
    Returns the effective URL after applying.
    """
    normalized = _normalize(url)
    from app.core.database import db
    if not db.find_one("settings", "global"):
        db.insert("settings", {"id": "global"})
    db.update("settings", "global", {"mt5_bridge_url": normalized})
    clear_cache()
    return get_bridge_url(force_refresh=True)


def clear_cache() -> None:
    global _cached_url, _cached_at
    _cached_url = None
    _cached_at = 0.0


def _monotonic() -> float:
    return time.monotonic()
