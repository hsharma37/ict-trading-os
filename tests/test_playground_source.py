"""Tests for price source/staleness classification (single price API: /market)."""
from datetime import datetime, timedelta, timezone

from app.services.quote_service import is_stale

# derive_source (Yahoo-era label classifier) was removed with the OANDA/Yahoo
# purge — quotes are mt5/manual/unavailable only, asserted by the endpoint test.


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
    assert "source" in body and body["source"] in {"mt5", "manual", "unavailable"}
    assert "stale" in body and isinstance(body["stale"], bool)
