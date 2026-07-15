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
