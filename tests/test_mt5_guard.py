"""Tests for MT5 execution guardrails."""
import pytest

from app.core.config import settings
from app.services.mt5_guard import validate_trade, Mt5ValidationError, allowed_symbols


def test_valid_trade_normalizes():
    out = validate_trade("eurusd", "buy", 0.5)
    assert out["symbol"] == "EURUSD"
    assert out["direction"] == "long"
    assert out["lot_size"] == 0.5


def test_rejects_unknown_symbol():
    with pytest.raises(Mt5ValidationError):
        validate_trade("DOGEUSD", "long", 0.1)


def test_rejects_bad_direction():
    with pytest.raises(Mt5ValidationError):
        validate_trade("EURUSD", "sideways", 0.1)


def test_rejects_nonpositive_and_oversized_lot():
    with pytest.raises(Mt5ValidationError):
        validate_trade("EURUSD", "long", 0)
    with pytest.raises(Mt5ValidationError):
        validate_trade("EURUSD", "long", settings.MT5_MAX_LOT + 1)


def test_rejects_below_min_qty():
    with pytest.raises(Mt5ValidationError):
        validate_trade("EURUSD", "long", 0.0001)


def test_sl_tp_side_validation_long():
    # long: SL must be below, TP above the reference price
    with pytest.raises(Mt5ValidationError):
        validate_trade("EURUSD", "long", 0.1, stop_loss=1.20, reference_price=1.10)
    with pytest.raises(Mt5ValidationError):
        validate_trade("EURUSD", "long", 0.1, take_profit=1.05, reference_price=1.10)
    ok = validate_trade("EURUSD", "long", 0.1, stop_loss=1.05, take_profit=1.15, reference_price=1.10)
    assert ok["direction"] == "long"


def test_sl_tp_side_validation_short():
    with pytest.raises(Mt5ValidationError):
        validate_trade("EURUSD", "short", 0.1, stop_loss=1.05, reference_price=1.10)
    ok = validate_trade("EURUSD", "short", 0.1, stop_loss=1.15, take_profit=1.05, reference_price=1.10)
    assert ok["direction"] == "short"


def test_require_sl_flag(monkeypatch):
    monkeypatch.setattr(settings, "MT5_REQUIRE_SL", True)
    with pytest.raises(Mt5ValidationError):
        validate_trade("EURUSD", "long", 0.1)


def test_allowlist_override(monkeypatch):
    monkeypatch.setattr(settings, "MT5_ALLOWED_SYMBOLS", "EURUSD,XAUUSD")
    assert allowed_symbols() == {"EURUSD", "XAUUSD"}
    with pytest.raises(Mt5ValidationError):
        validate_trade("GBPUSD", "long", 0.1)


def test_route_rejects_bad_symbol_without_hitting_bridge(client):
    # Bad symbol, no SL/TP -> pure validation -> 400 (never contacts the bridge).
    resp = client.post("/mt5/trade", params={"symbol": "DOGEUSD", "direction": "long", "lot_size": 0.1})
    assert resp.status_code == 400
    assert "not allowed" in resp.json()["detail"]


def test_route_rejects_oversized_lot(client):
    resp = client.post("/mt5/trade", params={
        "symbol": "EURUSD", "direction": "long", "lot_size": settings.MT5_MAX_LOT + 5,
    })
    assert resp.status_code == 400
    assert "exceeds" in resp.json()["detail"]
