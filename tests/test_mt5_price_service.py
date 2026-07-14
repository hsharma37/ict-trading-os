"""Tests for MT5 as a market-data provider."""
import httpx
import pytest

from app.core.config import settings
from app.services.mt5_price_service import mt5_price_service
from app.services import market_data


class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_unconfigured_when_provider_not_mt5(monkeypatch):
    monkeypatch.setattr(settings, "MARKET_DATA_PROVIDER", "auto")
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "http://bridge")
    assert mt5_price_service.is_configured() is False
    assert mt5_price_service.get_price("EURUSD") is None


def test_configured_when_provider_mt5_and_url_set(monkeypatch):
    monkeypatch.setattr(settings, "MARKET_DATA_PROVIDER", "mt5")
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "http://bridge")
    assert mt5_price_service.is_configured() is True


def test_get_price_parses_tick(monkeypatch):
    monkeypatch.setattr(settings, "MARKET_DATA_PROVIDER", "mt5")
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "http://bridge")
    monkeypatch.setattr(settings, "MT5_BRIDGE_API_KEY", "k")
    tick = {"symbol": "EURUSD", "price": 1.1001, "bid": 1.1000, "ask": 1.1002,
            "volume": 5, "time": "2026-07-14T10:00:00+00:00", "source": "mt5"}
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(200, tick))
    out = mt5_price_service.get_price("EURUSD")
    assert out["source"] == "mt5"
    assert out["price"] == 1.1001
    assert out["bid"] == 1.1000 and out["ask"] == 1.1002


def test_get_price_none_on_bridge_error(monkeypatch):
    monkeypatch.setattr(settings, "MARKET_DATA_PROVIDER", "mt5")
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "http://bridge")
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(503, {"error": "x"}))
    assert mt5_price_service.get_price("EURUSD") is None


def test_market_data_prefers_mt5_when_selected(monkeypatch):
    monkeypatch.setattr(settings, "MARKET_DATA_PROVIDER", "mt5")
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "http://bridge")
    tick = {"symbol": "EURUSD", "price": 1.2345, "bid": 1.2344, "ask": 1.2346, "volume": 1, "time": None}
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(200, tick))
    result = market_data.market_service.get_price("EURUSD")
    assert result["source"] == "mt5"
    assert result["price"] == 1.2345


def test_market_data_falls_through_when_mt5_off(monkeypatch):
    monkeypatch.setattr(settings, "MARKET_DATA_PROVIDER", "yahoo")
    result = market_data.market_service.get_price("EURUSD")
    assert isinstance(result, dict)
    assert result.get("source") != "mt5"
