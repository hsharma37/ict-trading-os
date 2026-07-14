"""Tests for the single source-of-truth price resolver."""
import httpx
import pytest

from app.core.config import settings
from app.services import quote_service
from app.services.quote_service import get_quote, clear_cache


class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _mt5_mock(tick_price):
    def fake_get(url, **kwargs):
        if "/tick/" in url:
            return _Resp(200, {"price": tick_price, "bid": tick_price - 0.01, "ask": tick_price + 0.01,
                               "volume": 1, "time": None})
        if "/candles/" in url:
            return _Resp(200, {"candles": [
                {"open": tick_price - 1, "high": tick_price + 1, "low": tick_price - 2, "close": tick_price - 0.5},
                {"open": tick_price - 0.5, "high": tick_price + 1, "low": tick_price - 1, "close": tick_price},
            ]})
        return _Resp(404, {})
    return fake_get


@pytest.fixture(autouse=True)
def _clear():
    clear_cache()
    yield
    clear_cache()


def test_canonical_shape_has_both_change_keys():
    settings_provider = settings.MARKET_DATA_PROVIDER
    try:
        q = get_quote("EURUSD")
        for key in ("symbol", "price", "bid", "ask", "change", "change_pct",
                    "change_percent", "high", "low", "open", "prev_close",
                    "volume", "timestamp", "source", "label", "kind", "digits", "stale"):
            assert key in q, f"missing {key}"
    finally:
        settings.MARKET_DATA_PROVIDER = settings_provider


def test_provider_switch_mt5(monkeypatch):
    monkeypatch.setattr(settings, "MARKET_DATA_PROVIDER", "mt5")
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "http://bridge")
    monkeypatch.setattr(httpx, "get", _mt5_mock(4096.7))
    q = get_quote("XAUUSD")
    assert q["source"] == "mt5"
    assert q["price"] == 4096.7


def test_provider_switch_yahoo(monkeypatch):
    monkeypatch.setattr(settings, "MARKET_DATA_PROVIDER", "yahoo")
    q = get_quote("EURUSD")
    assert q["source"] in {"yahoo", "scraped", "synthetic"}


def test_cache_makes_concurrent_reads_consistent(monkeypatch):
    """Two reads of the same symbol within the TTL return the identical quote,
    even if the underlying feed would have moved -- this is what keeps prices
    consistent across pages."""
    monkeypatch.setattr(settings, "MARKET_DATA_PROVIDER", "mt5")
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "http://bridge")

    prices = iter([100.0, 999.0])
    def moving_get(url, **kwargs):
        if "/tick/" in url:
            return _Resp(200, {"price": next(prices), "bid": 1, "ask": 2, "volume": 1, "time": None})
        return _Resp(200, {"candles": []})
    monkeypatch.setattr(httpx, "get", moving_get)

    first = get_quote("XAUUSD")
    second = get_quote("XAUUSD")   # cache hit -> same value, feed's 999.0 not fetched
    assert first["price"] == second["price"] == 100.0


def test_single_and_bulk_price_endpoints_agree(client, monkeypatch):
    """/market/price/{symbol} and /market/prices must return the same price
    for a symbol, because both go through the one resolver (get_quote)."""
    monkeypatch.setattr(settings, "MARKET_DATA_PROVIDER", "mt5")
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "http://bridge")
    monkeypatch.setattr(httpx, "get", _mt5_mock(4096.7))

    single = client.get("/market/price/XAUUSD").json()
    bulk = client.get("/market/prices?symbols=XAUUSD").json()
    bulk_xau = bulk["prices"][0]
    assert single["source"] == bulk_xau["source"] == "mt5"
    assert single["price"] == bulk_xau["price"] == 4096.7


def test_price_feed_restricted_to_configured_symbols(client):
    """The feed must ignore symbols outside the app's instrument list."""
    body = client.get("/market/prices?symbols=XAUUSD,NQ1!,BTCUSD,FOOBAR").json()
    returned = {p["symbol"] for p in body["prices"]}
    assert "XAUUSD" in returned
    assert returned.isdisjoint({"NQ1!", "BTCUSD", "FOOBAR"})


def test_price_feed_default_is_the_six_supported(client):
    body = client.get("/market/prices").json()
    returned = {p["symbol"] for p in body["prices"]}
    assert returned == {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "XAUUSD"}
