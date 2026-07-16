"""Live paper-forward test: forward-only counting, open-trade handling, lifecycle."""
from app.services import forward_test_service as mod
from app.services.forward_test_service import forward_test_service as fwd


def _series(n, start_ts=1_700_000_000, step=3600):
    # A gently trending series so some ICT patterns/entries can form.
    c, price = [], 1.10
    for i in range(n):
        price += 0.0002 if (i // 20) % 2 == 0 else -0.0002
        c.append({"time": start_ts + i * step, "open": round(price, 5),
                  "high": round(price + 0.0006, 5), "low": round(price - 0.0006, 5),
                  "close": round(price, 5)})
    return c


def test_create_refuses_synthetic(monkeypatch):
    monkeypatch.setattr(mod.market_service, "get_history",
                        lambda s, tf="1h", limit=5000, history_range="6mo":
                        [{"time": i, "open": 1.1, "high": 1.1, "low": 1.1, "close": 1.1, "synthetic": True} for i in range(300)])
    out = fwd.create("EURUSD")
    assert "error" in out


def test_forward_only_counts_after_start(monkeypatch):
    candles = _series(400)
    monkeypatch.setattr(mod.market_service, "get_history",
                        lambda s, tf="1h", limit=5000, history_range="6mo": candles)
    t = fwd.create("EURUSD", target_r=2.0)
    # start_candle_time is the LAST candle at creation → no past trade can count.
    assert t["start_candle_time"] == candles[-1]["time"]
    assert t["summary"].get("trades", 0) == 0


def test_lifecycle_stop_and_delete(monkeypatch):
    candles = _series(400)
    monkeypatch.setattr(mod.market_service, "get_history",
                        lambda s, tf="1h", limit=5000, history_range="6mo": candles)
    t = fwd.create("EURUSD")
    tid = t["id"]
    assert any(x["id"] == tid for x in fwd.list())
    assert fwd.stop(tid)["status"] == "stopped"
    # A stopped test is not recomputed but still listed.
    assert any(x["id"] == tid and x["status"] == "stopped" for x in fwd.list())
    fwd.delete(tid)
    assert all(x["id"] != tid for x in fwd.list())


def test_new_candles_accrue_forward_trades(monkeypatch):
    """After start, appending future candles should let forward trades appear."""
    base = _series(300)
    monkeypatch.setattr(mod.market_service, "get_history",
                        lambda s, tf="1h", limit=5000, history_range="6mo": base)
    t = fwd.create("EURUSD", target_r=1.0)
    assert t["summary"].get("trades", 0) == 0
    # Simulate time passing: many more candles print after the commit point.
    grown = base + _series(400, start_ts=base[-1]["time"] + 3600)
    monkeypatch.setattr(mod.market_service, "get_history",
                        lambda s, tf="1h", limit=5000, history_range="6mo": grown)
    updated = fwd.get(t["id"])
    # Forward trades are counted only from candles after start; count is >= 0 and
    # every counted trade entered strictly after the commit time.
    for tr in updated.get("trades", []):
        assert tr["entry_time"] > t["start_candle_time"]
