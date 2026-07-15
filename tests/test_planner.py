"""Tests for the trade planner (create → arm → execute)."""
from datetime import datetime, timedelta, timezone

from app.core.database import db
from app.services import planner_service as mod
from app.services.planner_service import planner_service as p


def _mock_bridge(monkeypatch, capture):
    monkeypatch.setattr(p, "_current_price", lambda symbol: 1.1200)

    def fake_post(path, payload):
        capture.append({"path": path, **payload})
        return {"status": "executed", "retcode": 10009, "order": 5000 + len(capture)}

    monkeypatch.setattr(p, "_post", fake_post)


def test_event_plan_halves_risk():
    plan = p.create_plan({"symbol": "EURUSD", "side": "BUY", "entry_price": 1.10,
                          "stop_loss": 1.095, "take_profits": [1.11], "risk_pct": 2.0, "is_event": True})
    assert plan["risk_pct"] == 1.0
    assert plan["status"] == "draft"


def test_price_trigger_arms_to_pending(monkeypatch):
    calls = []
    _mock_bridge(monkeypatch, calls)
    plan = p.create_plan({"symbol": "EURUSD", "side": "BUY", "entry_price": 1.1000,
                          "stop_loss": 1.0950, "take_profits": [1.1100], "risk_pct": 1.0,
                          "trigger_type": "price", "lot_size": 0.02})
    out = p.arm(plan["id"])
    assert out["status"] == "placed"
    # entry 1.10 below current 1.12 for a BUY -> buy limit.
    assert calls and calls[0]["path"] == "/pending"
    assert calls[0]["order_kind"] == "limit"
    assert out["mt5_tickets"]


def test_now_trigger_executes_market_scaled(monkeypatch):
    calls = []
    _mock_bridge(monkeypatch, calls)
    plan = p.create_plan({"symbol": "EURUSD", "side": "BUY", "entry_price": 1.12,
                          "stop_loss": 1.115, "take_profits": [1.13, 1.14], "risk_pct": 1.0,
                          "trigger_type": "now", "lot_size": 0.04})
    out = p.arm(plan["id"])
    assert out["status"] == "executed"
    # Two TPs + splittable lot -> two market legs, each with its own TP.
    trade_calls = [c for c in calls if c["path"] == "/trade"]
    assert len(trade_calls) == 2
    assert sorted(c["take_profit"] for c in trade_calls) == [1.13, 1.14]


def test_time_trigger_waits_then_run_due_fires(monkeypatch):
    calls = []
    _mock_bridge(monkeypatch, calls)
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    plan = p.create_plan({"symbol": "EURUSD", "side": "BUY", "entry_price": 1.12,
                          "stop_loss": 1.115, "take_profits": [1.13], "risk_pct": 1.0,
                          "trigger_type": "time", "trigger_time": past, "lot_size": 0.02})
    armed = p.arm(plan["id"])
    assert armed["status"] == "armed"  # not executed yet
    assert not calls
    res = p.run_due()
    assert res["fired"] == 1
    assert db.find_one("trade_plans", plan["id"])["status"] == "executed"


def test_plan_from_signal_removes_signal(client, monkeypatch):
    monkeypatch.setattr(p, "_current_price", lambda symbol: 1.12)
    db.insert("telegram_signals", {"id": "xxictxx/500", "symbol": "EURUSD", "side": "BUY",
                                   "entry_prices": [1.10], "stop_loss": 1.095, "take_profits": [1.11],
                                   "confidence": "high", "raw_text": "EURUSD BUY"})
    r = client.post("/planner/from-signal/xxictxx/500").json()
    assert r["plan"]["symbol"] == "EURUSD"
    assert r["plan"]["source"] == "telegram"
    # Signal is gone (doesn't pile up).
    assert not db.find_one("telegram_signals", "xxictxx/500")
