"""Lot sizing uses the broker's real tick value when available."""
from app.services.lot_calculator import lot_calculator


def test_lot_uses_broker_tick_value(monkeypatch):
    # USDCAD: SL distance 0.0050 (50 pips). Broker says $7.10 loss per lot.
    monkeypatch.setattr("app.services.broker_specs.money_per_lot",
                        lambda symbol, dist: 71.0 if symbol == "USDCAD" else None)
    out = lot_calculator.calculate("USDCAD", entry_price=1.4000, stop_loss=1.3950,
                                   account_balance=10000, risk_pct=1.0)
    assert out["rate_source"] == "mt5"
    # risk_per_lot came from the broker (≈71 for this distance), not static config.
    assert out["risk_per_lot"] == 71.0
    # lot ≈ risk_amount(100) / 71 ≈ 1.41
    assert 1.3 <= out["lot_size"] <= 1.5


def test_lot_falls_back_to_static(monkeypatch):
    monkeypatch.setattr("app.services.broker_specs.money_per_lot", lambda symbol, dist: None)
    out = lot_calculator.calculate("EURUSD", entry_price=1.1000, stop_loss=1.0950,
                                   account_balance=10000, risk_pct=1.0)
    assert out["rate_source"] == "static"
    assert out["lot_size"] > 0


def test_gold_rejects_implausible_broker_value(monkeypatch):
    # XAUUSD, SL $5 away, $100 risk. Correct static risk/lot = 5*100 = $500 → 0.2 lots.
    # A broker that reports a 10×-understated tick value (→ $50/lot) would size
    # 2.0 lots (10× too large). The USD-quoted sanity band must reject it.
    monkeypatch.setattr("app.services.broker_specs.money_per_lot",
                        lambda symbol, dist: 50.0 if symbol == "XAUUSD" else None)
    out = lot_calculator.calculate("XAUUSD", entry_price=4000.0, stop_loss=3995.0,
                                   account_balance=10000, risk_pct=1.0)
    assert out["rate_source"] == "static (broker spec rejected)"
    assert out["risk_per_lot"] == 500.0          # static, not the bad 50
    assert abs(out["lot_size"] - 0.2) < 1e-6     # sane 0.2 lots, not 2.0


def test_gold_accepts_plausible_broker_value(monkeypatch):
    # A broker value close to static (within band) is trusted.
    monkeypatch.setattr("app.services.broker_specs.money_per_lot",
                        lambda symbol, dist: 505.0 if symbol == "XAUUSD" else None)
    out = lot_calculator.calculate("XAUUSD", entry_price=4000.0, stop_loss=3995.0,
                                   account_balance=10000, risk_pct=1.0)
    assert out["rate_source"] == "mt5"
    assert out["risk_per_lot"] == 505.0
