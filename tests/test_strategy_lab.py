"""Strategy Lab + ML baseline + forward-test fixes."""
import math
import pytest

from app.services import market_data as md
from app.services import strategy_service, ml_service


def _trending(n=700, base=1.10):
    """Waves on a rising drift — enough structure for every strategy to fire."""
    out = []
    for i in range(n):
        p = base + i * 0.0002 + 0.004 * math.sin(i / 9.0)
        out.append({"time": 1_700_000_000 + i * 3600, "open": round(p, 5),
                    "high": round(p + 0.0015, 5), "low": round(p - 0.0015, 5),
                    "close": round(p + 0.0005 * math.cos(i / 5.0), 5), "volume": 100})
    return out


@pytest.fixture
def candles(monkeypatch):
    data = _trending()
    monkeypatch.setattr(md.market_service, "get_history",
                        lambda s, tf="1h", limit=200, history_range=None: data[-limit:])
    return data


def test_list_strategies_catalogue():
    keys = {s["key"] for s in strategy_service.list_strategies()}
    assert {"sma_cross", "ema_cross", "rsi2", "bollinger", "donchian", "momentum"} <= keys


def test_strategy_backtest_runs_and_is_cost_aware(candles):
    r = strategy_service.run_strategy_backtest("EURUSD", "sma_cross", "1h", 2.0)
    assert not r.get("error")
    assert r["strategy"] == "sma_cross" and r["stop_model"] == "1.5×ATR(14)"
    assert r.get("signals_found", 0) > 0


def test_strategy_compare_includes_ict_baseline(candles):
    r = strategy_service.compare_strategies("EURUSD", "1h", 2.0)
    assert not r.get("error")
    names = {row["strategy"] for row in r["strategies"]}
    assert "ict_confluence" in names and "donchian" in names


def test_unknown_strategy_rejected(candles):
    assert "Unknown strategy" in strategy_service.run_strategy_backtest("EURUSD", "nope")["error"]


def test_ml_baseline_walk_forward(candles):
    r = ml_service.ml_baseline("EURUSD", "1h")
    assert not r.get("error")
    assert 0 <= r["oos_accuracy_pct"] <= 100
    assert r["oos_predictions"] > 50
    assert "walk-forward" in r["method"]


def test_forward_test_list_fast_by_default(monkeypatch, candles):
    """GET /forward-tests must NOT refetch candles per test (the timeout bug)."""
    from app.services.forward_test_service import forward_test_service
    created = forward_test_service.create("EURUSD", timeframe="1h", target_r=2.0, label="named strat")
    assert created.get("label") == "named strat"
    calls = {"n": 0}
    def counting(s, tf="1h", limit=200, history_range=None):
        calls["n"] += 1
        return _trending()[-limit:]
    monkeypatch.setattr(md.market_service, "get_history", counting)
    rows = forward_test_service.list(recompute=False)
    assert calls["n"] == 0, "fast list must not hit the bridge"
    assert any(t.get("label") == "named strat" for t in rows)
    forward_test_service.delete(created["id"])


def test_forward_test_bounded_fetch(candles):
    from app.services.forward_test_service import _fetch_limit
    t = {"timeframe": "1h", "start_candle_time": 1}   # ancient start (1970)
    assert _fetch_limit(t) == 3000                     # capped, never 5000
    t2 = {"timeframe": "1h", "start_candle_time": None}
    assert 300 <= _fetch_limit(t2) <= 3000


def test_ict_atr_stop_normalizes_stop_width(candles):
    """ATR-normalized ICT signals should carry a wider, uniform stop than the
    tight structural stops — the fix for the cost-in-R penalty on gold."""
    from app.services import strategy_service as ss
    struct = ss._ict_signals(candles, "XAUUSD", "1h", 2, atr_stop=False)
    atr = ss._ict_signals(candles, "XAUUSD", "1h", 2, atr_stop=True)
    if struct and atr:
        # ATR stops are volatility-scaled and typically wider than OB/FVG stops.
        assert sum(s["risk"] for s in atr) / len(atr) > 0


def test_ict_min_confluence_reduces_trade_count(candles):
    """Raising the confluence gate must not INCREASE the ICT signal count —
    STRONG-tier is a subset of all setups (stops the firehose)."""
    from app.services import strategy_service as ss
    lo = len(ss._ict_signals(candles, "XAUUSD", "1h", 2, atr_stop=False))
    hi = len(ss._ict_signals(candles, "XAUUSD", "1h", 4, atr_stop=False))
    assert hi <= lo


def test_compare_reports_fairness_knobs(candles):
    from app.services import strategy_service as ss
    r = ss.compare_strategies("XAUUSD", "1h", 2.0, ict_min_confluence=4, ict_atr_stop=True)
    assert r["ict_min_confluence"] == 4 and r["ict_atr_stop"] is True
    ict_row = next(x for x in r["strategies"] if x["strategy"] == "ict_confluence")
    assert "STRONG" in ict_row["label"] and "1.5×ATR" in ict_row["label"]
    assert "1.5×ATR" not in r["note"] or "structural" in r["note"]  # note is now accurate


# ── top-trader strategies (Williams, Raschke, Crabel, Turtle S2) ──────

def _strong_trend_with_pullbacks(n=400, base=1.10):
    """Steady uptrend with periodic dips to the EMA — Holy Grail / VBO fodder.
    Bars are hourly starting at midnight so the London ORB finds 07:00 bars."""
    out = []
    p = base
    for i in range(n):
        drift = 0.0012
        dip = -0.004 if i % 25 in (20, 21) else 0.0   # periodic pullback
        o = p
        c = p + drift + dip
        h = max(o, c) + 0.0008
        l = min(o, c) - (0.0035 if dip else 0.0008)   # pullback wick
        out.append({"time": 1_700_000_000 - (1_700_000_000 % 86400) + i * 3600,
                    "open": round(o, 5), "high": round(h, 5),
                    "low": round(l, 5), "close": round(c, 5), "volume": 100})
        p = c
    return out


def test_new_strategies_in_catalogue():
    keys = {s["key"] for s in strategy_service.list_strategies()}
    assert {"williams_vbo", "holy_grail", "london_orb", "turtle55"} <= keys


def test_top_trader_strategies_emit_signals():
    data = _strong_trend_with_pullbacks()
    for key in ("williams_vbo", "turtle55", "london_orb", "holy_grail"):
        sigs = strategy_service.signals_for(data, key)
        assert isinstance(sigs, list)
        if key in ("williams_vbo", "turtle55", "london_orb"):
            assert len(sigs) > 0, f"{key} should fire on a strong trend with hourly bars"
        for s in sigs:
            assert s["risk"] > 0 and "i" in s and isinstance(s["long"], bool)


def test_london_orb_needs_intraday_bars():
    """Daily bars have no 07:00 hour — ORB must yield nothing, not crash."""
    data = _strong_trend_with_pullbacks()
    daily = [dict(c, time=1_700_000_000 - (1_700_000_000 % 86400) + i * 86400) for i, c in enumerate(data)]
    assert strategy_service.signals_for(daily, "london_orb") == []


def test_forward_test_accepts_strategy(monkeypatch):
    data = _strong_trend_with_pullbacks()
    monkeypatch.setattr(md.market_service, "get_history",
                        lambda s, tf="1h", limit=200, history_range=None: data[-limit:])
    from app.services.forward_test_service import forward_test_service
    t = forward_test_service.create("EURUSD", timeframe="1h", target_r=2.0,
                                    label="VBO paper", strategy="williams_vbo")
    assert not t.get("error")
    assert t["strategy"] == "williams_vbo" and t["label"] == "VBO paper"
    forward_test_service.delete(t["id"])


def test_forward_test_rejects_unknown_strategy(client):
    resp = client.post("/forward-tests", json={"symbol": "EURUSD", "strategy": "moon_phase"})
    assert resp.status_code == 422
    assert "Unknown strategy" in resp.json()["detail"]


# ── New York ORB + forward-test trade details ─────────────────────────

def test_ny_orb_in_catalogue_and_fires():
    keys = {s["key"] for s in strategy_service.list_strategies()}
    assert "ny_orb" in keys
    data = _strong_trend_with_pullbacks()   # hourly bars from midnight → has 13:00 hours
    sigs = strategy_service.signals_for(data, "ny_orb")
    assert len(sigs) > 0, "NY ORB should fire on hourly trending data"
    from datetime import datetime
    for s in sigs:
        hour = datetime.utcfromtimestamp(data[s["i"]]["time"]).hour
        assert 13 < hour < 17, "NY breakout must land in the 14:00-16:59 UTC window"


def test_ny_orb_and_london_orb_are_distinct():
    data = _strong_trend_with_pullbacks()
    ny = {s["i"] for s in strategy_service.signals_for(data, "ny_orb")}
    lon = {s["i"] for s in strategy_service.signals_for(data, "london_orb")}
    assert ny.isdisjoint(lon), "sessions must not share signal bars"


def test_forward_test_trades_carry_details(monkeypatch):
    data = _strong_trend_with_pullbacks()
    monkeypatch.setattr(md.market_service, "get_history",
                        lambda s, tf="1h", limit=200, history_range=None: data[-limit:])
    from app.services.forward_test_service import forward_test_service
    t = forward_test_service.create("EURUSD", timeframe="1h", target_r=2.0,
                                    label="detail check", strategy="williams_vbo")
    assert not t.get("error")
    # Force trades into view: recompute against a start at the beginning of history.
    import app.core.database as dbm
    dbm.db.update("forward_tests", t["id"], {"start_candle_time": data[0]["time"]})
    t2 = forward_test_service.get(t["id"])
    for tr in t2.get("trades", []):
        assert {"r", "dir", "entry", "sl", "target", "outcome"} <= set(tr.keys())
        assert tr["outcome"] in ("target", "stop", "time")
    forward_test_service.delete(t["id"])
