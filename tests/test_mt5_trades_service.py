"""Tests for MT5 as the trades-data base (Dashboard/Analytics/chatbot)."""
import httpx

from app.core.config import settings
from app.services import mt5_trades_service as mod
from app.services.mt5_trades_service import mt5_trades_service


class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


ACCOUNT = {"balance": 10391.74, "equity": 10538.25, "free_margin": 1208.85,
           "margin": 9329.4, "margin_level": 112.9, "currency": "USD", "status": "connected"}
POSITIONS = {"positions": [
    {"ticket": "1", "symbol": "XAUUSD", "direction": "short", "lot_size": 0.23,
     "open_price": 4056.26, "current_price": 4049.85, "sl": 4056.0, "tp": 4044.0,
     "profit": 147.43, "swap": 0.0},
], "count": 1, "status": "connected"}
HISTORY = {"history": [
    {"ticket": "9", "symbol": "XAUUSD", "direction": "short", "lot_size": 0.2,
     "open_price": 4063.3, "close_price": 4059.71, "profit": 71.8, "closed_at": "2026-07-15T01:00:01"},
    {"ticket": "8", "symbol": "EURUSD", "direction": "long", "lot_size": 0.5,
     "open_price": 1.10, "close_price": 1.09, "profit": -50.0, "closed_at": "2026-07-14T13:00:00"},
], "count": 2, "status": "connected"}


def _wire(monkeypatch, connected=True):
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "https://bridge.example.com")

    def fake_get(url, **kwargs):
        if url.endswith("/account"):
            return _Resp(200, ACCOUNT if connected else {"status": "disconnected"})
        if url.endswith("/positions"):
            return _Resp(200, POSITIONS)
        if url.endswith("/history"):
            return _Resp(200, HISTORY)
        return _Resp(404, {})

    monkeypatch.setattr(httpx, "get", fake_get)
    mt5_trades_service.clear_cache()


def test_not_active_on_localhost(monkeypatch):
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "http://localhost:5001")
    mt5_trades_service.clear_cache()
    # Must be offline without any network call.
    monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no net")))
    assert mt5_trades_service.is_active() is False


def test_active_when_connected(monkeypatch):
    _wire(monkeypatch, connected=True)
    assert mt5_trades_service.is_active() is True


def test_not_active_when_disconnected(monkeypatch):
    _wire(monkeypatch, connected=False)
    assert mt5_trades_service.is_active() is False


def test_stats_from_broker(monkeypatch):
    _wire(monkeypatch)
    s = mt5_trades_service.get_stats()
    assert s["source"] == "mt5"
    assert s["closed_trades"] == 2
    assert s["open_trades"] == 1
    assert s["winning_trades"] == 1 and s["losing_trades"] == 1
    assert s["win_rate"] == 50.0
    # realized 71.8 + (-50.0) = 21.8 ; unrealized 147.43
    assert s["realized_pnl"] == 21.8
    assert s["unrealized_pnl"] == 147.43
    assert s["total_pnl"] == round(21.8 + 147.43, 2)
    assert s["by_symbol"]["XAUUSD"]["trades"] == 1
    assert s["account"]["balance"] == 10391.74


def test_recent_trades_normalized(monkeypatch):
    _wire(monkeypatch)
    recent = mt5_trades_service.get_recent_trades(5)
    assert len(recent) == 2
    # newest first
    assert recent[0]["symbol"] == "XAUUSD"
    t = recent[0]
    assert t["status"] == "CLOSED"
    assert t["side"] == "SELL"  # short -> SELL
    assert t["realized_pnl"] == t["profit"] == 71.8
    assert t["entry_price"] == t["open_price"] == 4063.3


def test_open_trades_normalized(monkeypatch):
    _wire(monkeypatch)
    opens = mt5_trades_service.get_open_trades()
    assert len(opens) == 1
    p = opens[0]
    assert p["status"] == "OPEN" and p["side"] == "SELL"
    assert p["unrealized_pnl"] == 147.43
    assert p["stop_loss"] == 4056.0


def test_context_block_mentions_account_and_positions(monkeypatch):
    _wire(monkeypatch)
    block = mt5_trades_service.get_context_block()
    assert block is not None
    assert "LIVE MT5 ACCOUNT SNAPSHOT" in block
    assert "XAUUSD" in block
    assert "10391.74" in block


def test_trade_lifecycle_delegates_to_mt5(monkeypatch):
    _wire(monkeypatch)
    from app.services.trade_lifecycle_service import trade_lifecycle_service
    stats = trade_lifecycle_service.get_trade_stats()
    assert stats.get("source") == "mt5"
    assert stats["closed_trades"] == 2
