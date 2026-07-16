"""Backtest + Monte Carlo: honest degradation and deterministic math."""
from app.services import backtest_service as bt


def _flat(n, base=1.10, synthetic=False):
    c = []
    for i in range(n):
        row = {"time": i, "open": base, "high": base * 1.0005, "low": base * 0.9995, "close": base}
        if synthetic:
            row["synthetic"] = True
        c.append(row)
    return c


def test_backtest_refuses_synthetic(monkeypatch):
    monkeypatch.setattr(bt.market_service, "get_history",
                        lambda s, tf="1h", limit=5000, history_range="1y": _flat(300, synthetic=True))
    out = bt.run_backtest("EURUSD")
    assert out.get("data_quality") == "synthetic" and "error" in out


def test_backtest_needs_enough_data(monkeypatch):
    monkeypatch.setattr(bt.market_service, "get_history",
                        lambda s, tf="1h", limit=5000, history_range="1y": _flat(30))
    out = bt.run_backtest("EURUSD")
    assert "error" in out


def test_backtest_summary_shape(monkeypatch):
    # A flat series won't fire signals, but the summary must still be well-formed.
    monkeypatch.setattr(bt.market_service, "get_history",
                        lambda s, tf="1h", limit=5000, history_range="1y": _flat(300))
    out = bt.run_backtest("EURUSD")
    assert out["symbol"] == "EURUSD" and "trades" in out and out["candles"] == 300


def test_monte_carlo_needs_min_sample():
    assert "error" in bt.monte_carlo([0.5, -1.0])


def test_monte_carlo_deterministic_and_bounded():
    rs = [2.0, -1.0, -1.0, 2.0, -1.0, -1.0, 2.0, -1.0]  # 3/8 win at 2R ≈ break-even
    a = bt.monte_carlo(rs, n_sims=500, seed=7)
    b = bt.monte_carlo(rs, n_sims=500, seed=7)
    assert a["final_return_pct"] == b["final_return_pct"]        # seeded → reproducible
    assert 0 <= a["risk_of_ruin_pct"] <= 100
    assert 0 <= a["prob_loss_pct"] <= 100
    # Percentiles are ordered.
    fr = a["final_return_pct"]
    assert fr["p5"] <= fr["median"] <= fr["p95"]


def test_monte_carlo_losing_edge_shows_high_ruin():
    # A clearly negative edge should surface a high probability of loss.
    rs = [-1.0, -1.0, -1.0, 2.0, -1.0, -1.0, -1.0, -1.0]  # 1/8 win at 2R → strongly negative
    out = bt.monte_carlo(rs, n_sims=1000, risk_per_trade_pct=2.0, horizon=100, seed=1)
    assert out["prob_loss_pct"] > 80


# ── Parameter sweep + out-of-sample verdict ───────────────────────────

def test_sweep_refuses_synthetic(monkeypatch):
    monkeypatch.setattr(bt.market_service, "get_history",
                        lambda s, tf="1h", limit=5000, history_range="1y": _flat(300, synthetic=True))
    out = bt.run_sweep("EURUSD")
    assert out.get("data_quality") == "synthetic" and "error" in out


def test_sweep_flat_data_has_no_edge(monkeypatch):
    monkeypatch.setattr(bt.market_service, "get_history",
                        lambda s, tf="1h", limit=5000, history_range="1y": _flat(400))
    out = bt.run_sweep("EURUSD")
    assert out["best"] is None and out["verdict"]["tone"] == "bad"


def test_sweep_verdict_flags_curve_fit():
    # Positive in-sample but negative out-of-sample → curve-fit warning.
    fit = {"target_r": 3.0, "session_filter": True, "trend_filter": False,
           "expectancy_r": 0.2, "oos_expectancy_r": -0.1}
    assert bt._sweep_verdict(fit)["tone"] == "warn"
    # Positive and holds OOS → good.
    real = {"target_r": 3.0, "session_filter": True, "trend_filter": True,
            "expectancy_r": 0.25, "oos_expectancy_r": 0.18}
    assert bt._sweep_verdict(real)["tone"] == "good"
    # Break-even → bad.
    flat = {"target_r": 2.0, "session_filter": False, "trend_filter": False,
            "expectancy_r": 0.0, "oos_expectancy_r": 0.0}
    assert bt._sweep_verdict(flat)["tone"] == "bad"


# ── Honest walk-forward test (train → lock → unseen test) ─────────────

def test_honest_test_refuses_synthetic(monkeypatch):
    monkeypatch.setattr(bt.market_service, "get_history",
                        lambda s, tf="1h", limit=5000, history_range="1y": _flat(400, synthetic=True))
    out = bt.run_honest_test("EURUSD")
    assert out.get("data_quality") == "synthetic" and "error" in out


def test_honest_test_flat_no_config(monkeypatch):
    monkeypatch.setattr(bt.market_service, "get_history",
                        lambda s, tf="1h", limit=5000, history_range="1y": _flat(400))
    out = bt.run_honest_test("EURUSD")
    assert out.get("note")  # not enough training trades


def test_honest_verdict_distinguishes_real_from_curvefit():
    best = {"target_r": 3.0, "session_filter": False, "trend_filter": True, "train_expectancy_r": 0.2}
    # Holds out-of-sample → good.
    assert bt._honest_verdict(best, {"trades": 200, "expectancy_r": 0.12})["tone"] == "good"
    # Collapses out-of-sample → bad (curve-fit).
    assert bt._honest_verdict(best, {"trades": 200, "expectancy_r": -0.1})["tone"] == "bad"
    # Break-even → warn.
    assert bt._honest_verdict(best, {"trades": 200, "expectancy_r": 0.01})["tone"] == "warn"
    # Too few test trades → warn (inconclusive).
    assert bt._honest_verdict(best, {"trades": 5, "expectancy_r": 0.3})["tone"] == "warn"


# ── Trading costs (spread + commission) ───────────────────────────────

def test_round_trip_cost_is_positive():
    assert bt._round_trip_cost_price("EURUSD") > 0
    assert bt._round_trip_cost_price("XAUUSD") > bt._round_trip_cost_price("EURUSD")


def test_costs_reduce_expectancy(monkeypatch):
    # A trending series that produces some trades; net must be <= gross.
    from tests.test_forward_test import _series  # reuse the trending generator
    candles = _series(500)
    monkeypatch.setattr(bt.market_service, "get_history",
                        lambda s, tf="1h", limit=5000, history_range="1y": candles)
    gross = bt.run_backtest("EURUSD", target_r=2.0, include_costs=False)
    net = bt.run_backtest("EURUSD", target_r=2.0, include_costs=True)
    if gross.get("trades", 0) >= 5 and net.get("trades", 0) >= 5:
        assert net["expectancy_r"] <= gross["expectancy_r"]
        assert net["costs_included"] is True and gross["costs_included"] is False


def test_min_stop_filter_reduces_trades(monkeypatch):
    from tests.test_forward_test import _series
    candles = _series(500)
    monkeypatch.setattr(bt.market_service, "get_history",
                        lambda s, tf="1h", limit=5000, history_range="1y": candles)
    wide = bt.run_backtest("EURUSD", target_r=2.0, min_stop_pips=30)
    allt = bt.run_backtest("EURUSD", target_r=2.0, min_stop_pips=0)
    assert wide.get("trades", 0) <= allt.get("trades", 0)
