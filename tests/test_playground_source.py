"""Tests for price source/staleness classification (single price API: /market)."""
from datetime import datetime, timedelta, timezone

from app.services.quote_service import derive_source, is_stale


def test_derive_source_synthetic():
    assert derive_source("EUR/USD (synthetic)") == "synthetic"
    assert derive_source("XAU/USD (SYNTHETIC)") == "synthetic"


def test_derive_source_scraped():
    assert derive_source("XAU/USD (kitco)") == "scraped"
    assert derive_source("Gold (gold.org)") == "scraped"
    assert derive_source("EUR/USD (investing.com)") == "scraped"


def test_derive_source_yahoo_default():
    assert derive_source("EUR/USD") == "yahoo"
    assert derive_source("") == "yahoo"
    assert derive_source(None) == "yahoo"  # type: ignore[arg-type]


def test_is_stale_fresh():
    now = datetime.utcnow().isoformat()
    assert is_stale(now) is False


def test_is_stale_old():
    old = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
    assert is_stale(old) is True


def test_is_stale_handles_z_suffix_and_garbage():
    fresh_z = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    assert is_stale(fresh_z) is False
    assert is_stale("not-a-date") is False


def test_price_endpoint_includes_source(client):
    resp = client.get("/market/price/EURUSD")
    assert resp.status_code == 200
    body = resp.json()
    assert "source" in body and body["source"] in {"yahoo", "scraped", "synthetic", "mt5", "oanda"}
    assert "stale" in body and isinstance(body["stale"], bool)
