"""Tests for the OANDA v20 market-data provider and its fallback behaviour."""
import httpx
import pytest

from app.core.config import settings
from app.services.oanda_service import oanda_service
from app.services import market_data


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    """Minimal httpx.Client stand-in routing by URL path."""
    def __init__(self, pricing=None, candles=None):
        self._pricing = pricing
        self._candles = candles

    def get(self, url, params=None):
        if "/pricing" in url:
            return _FakeResponse(self._pricing or {"prices": []})
        if "/candles" in url:
            return _FakeResponse(self._candles or {"candles": []})
        return _FakeResponse({})


@pytest.fixture
def oanda_configured(monkeypatch):
    monkeypatch.setattr(settings, "MARKET_DATA_PROVIDER", "auto")
    monkeypatch.setattr(settings, "OANDA_API_TOKEN", "test-token")
    monkeypatch.setattr(settings, "OANDA_ACCOUNT_ID", "101-001-0000000-001")
    monkeypatch.setattr(settings, "OANDA_ENV", "practice")
    oanda_service._daily_open.clear()
    yield
    oanda_service._daily_open.clear()


def test_unconfigured_returns_none(monkeypatch):
    """With no credentials the provider is inert and callers fall back."""
    monkeypatch.setattr(settings, "OANDA_API_TOKEN", "")
    monkeypatch.setattr(settings, "OANDA_ACCOUNT_ID", "")
    assert oanda_service.is_configured() is False
    assert oanda_service.get_price("EURUSD") is None
    assert oanda_service.get_history("EURUSD") is None


def test_yahoo_forced_disables_oanda(monkeypatch):
    monkeypatch.setattr(settings, "MARKET_DATA_PROVIDER", "yahoo")
    monkeypatch.setattr(settings, "OANDA_API_TOKEN", "test-token")
    monkeypatch.setattr(settings, "OANDA_ACCOUNT_ID", "101-001-0000000-001")
    assert oanda_service.is_configured() is False


def test_symbol_mapping():
    assert oanda_service.oanda_name("EURUSD") == "EUR_USD"
    assert oanda_service.oanda_name("XAUUSD") == "XAU_USD"
    assert oanda_service.oanda_name("NQ1!") == "NAS100_USD"
    # Unmapped symbol (e.g. BTCUSD) -> None so it falls back to Yahoo.
    assert oanda_service.oanda_name("BTCUSD") is None


def test_get_price_parses_pricing(monkeypatch, oanda_configured):
    pricing = {"prices": [{
        "instrument": "EUR_USD",
        "time": "2026-07-14T10:00:00.000000000Z",
        "status": "tradeable",
        "bids": [{"price": "1.08340"}],
        "asks": [{"price": "1.08360"}],
        "closeoutBid": "1.08339",
        "closeoutAsk": "1.08361",
    }]}
    candles = {"candles": [{"complete": True, "mid": {"o": "1.08000"}, "time": "2026-07-14T00:00:00Z"}]}
    monkeypatch.setattr(oanda_service, "_http", lambda: _FakeClient(pricing=pricing, candles=candles))

    price = oanda_service.get_price("EURUSD")
    assert price is not None
    assert price["source"] == "oanda"
    assert price["bid"] == 1.08340
    assert price["ask"] == 1.08360
    assert price["price"] == round((1.08340 + 1.08360) / 2, 5)
    # change vs today's open (1.08000)
    assert price["change"] == round(1.08350 - 1.08000, 5)
    assert price["change_pct"] > 0


def test_get_history_parses_candles(monkeypatch, oanda_configured):
    candles = {"candles": [
        {"complete": True, "time": "2026-07-14T09:00:00Z",
         "mid": {"o": "1.0800", "h": "1.0820", "l": "1.0795", "c": "1.0810"}, "volume": 42},
        {"complete": False, "time": "2026-07-14T10:00:00Z",
         "mid": {"o": "1.0810", "h": "1.0830", "l": "1.0805", "c": "1.0825"}, "volume": 10},
    ]}
    monkeypatch.setattr(oanda_service, "_http", lambda: _FakeClient(candles=candles))

    hist = oanda_service.get_history("EURUSD", "1h", 200)
    assert hist is not None
    # incomplete candle is dropped
    assert len(hist) == 1
    assert hist[0]["open"] == 1.08
    assert hist[0]["close"] == 1.081
    assert hist[0]["volume"] == 42


def test_market_data_falls_back_when_oanda_off(monkeypatch):
    """market_service.get_price still returns a dict with OANDA disabled."""
    monkeypatch.setattr(settings, "OANDA_API_TOKEN", "")
    monkeypatch.setattr(settings, "OANDA_ACCOUNT_ID", "")
    result = market_data.market_service.get_price("EURUSD")
    assert isinstance(result, dict)
    assert result.get("source") != "oanda"


def test_market_data_prefers_oanda_when_configured(monkeypatch, oanda_configured):
    pricing = {"prices": [{
        "instrument": "EUR_USD", "time": "2026-07-14T10:00:00Z", "status": "tradeable",
        "bids": [{"price": "1.1000"}], "asks": [{"price": "1.1002"}],
    }]}
    monkeypatch.setattr(oanda_service, "_http", lambda: _FakeClient(pricing=pricing, candles={"candles": []}))
    result = market_data.market_service.get_price("EURUSD")
    assert result["source"] == "oanda"
    assert result["price"] == round((1.1000 + 1.1002) / 2, 5)
