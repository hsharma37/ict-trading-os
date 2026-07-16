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
