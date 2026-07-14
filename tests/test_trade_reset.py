"""Tests for resetting the internal trade ledger."""
from app.services.trade_lifecycle_service import trade_lifecycle_service


def _make_trade(symbol="EURUSD"):
    # BUY with SL below / TP above entry (valid per the side-aware guardrails).
    return trade_lifecycle_service.create_trade(
        symbol=symbol, side="BUY", entry_price=1.10, stop_loss=1.09,
        take_profit_1=1.12, quantity=0.1, account_balance=10000, risk_pct=1.0,
    )


def test_reset_all_clears_ledger():
    _make_trade()
    _make_trade(symbol="GBPUSD")
    assert len(trade_lifecycle_service.list_trades()) >= 2
    result = trade_lifecycle_service.reset_all()
    assert result["deleted"] >= 2
    assert result["remaining"] == 0
    assert trade_lifecycle_service.list_trades() == []


def test_reset_endpoint_requires_no_key_locally_but_clears(client):
    _make_trade()
    resp = client.delete("/trades")
    assert resp.status_code == 200
    assert client.get("/trades").json()["trades"] == []


def test_reset_by_status_only_targets_that_status():
    open_trade = _make_trade()
    # close nothing; create a second and leave both OPEN, then reset only CLOSED
    _make_trade(symbol="GBPUSD")
    before = len(trade_lifecycle_service.list_trades())
    result = trade_lifecycle_service.reset_all(status="CLOSED")
    assert result["deleted"] == 0
    assert len(trade_lifecycle_service.list_trades()) == before
    assert open_trade  # sanity
