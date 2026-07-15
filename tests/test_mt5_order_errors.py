"""The MT5 proxy must surface bridge/broker errors, not fake a success."""
import httpx
import pytest
from fastapi import HTTPException

from app.routers.mt5 import _result_or_raise


class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_ok_retcode_passes_through():
    body = {"status": "executed", "retcode": 10009, "order": 123, "price": 1.10}
    assert _result_or_raise(_Resp(200, body)) == body


def test_bridge_503_raises():
    with pytest.raises(HTTPException) as ei:
        _result_or_raise(_Resp(503, {"status": "error", "error": "Symbol NQ1! is not available."}))
    assert ei.value.status_code == 502
    assert "NQ1!" in ei.value.detail


def test_status_error_body_raises_even_on_200():
    # The bug: bridge returned 200 with an error body -> used to look like success.
    with pytest.raises(HTTPException) as ei:
        _result_or_raise(_Resp(200, {"status": "error", "error": "No tick data available"}))
    assert ei.value.status_code == 400
    assert "No tick data" in ei.value.detail


def test_bad_broker_retcode_raises_generic():
    # A retcode with no friendly mapping falls back to showing the number+comment.
    with pytest.raises(HTTPException) as ei:
        _result_or_raise(_Resp(200, {"status": "executed", "retcode": 10099, "comment": "Weird"}))
    assert ei.value.status_code == 400
    assert "10099" in ei.value.detail


def test_autotrading_disabled_gives_actionable_message():
    with pytest.raises(HTTPException) as ei:
        _result_or_raise(_Resp(200, {"status": "executed", "retcode": 10027, "comment": "AutoTrading disabled by client"}))
    assert ei.value.status_code == 400
    assert "Algo Trading" in ei.value.detail  # tells the user how to fix it


def test_non_json_raises():
    class _Bad:
        status_code = 200

        def json(self):
            raise ValueError("not json")

    with pytest.raises(HTTPException) as ei:
        _result_or_raise(_Bad())
    assert ei.value.status_code == 502


# ── Post-trade read-back confirmation ────────────────────────────

def test_confirm_position_reads_back(monkeypatch):
    import asyncio, app.routers.mt5 as mt5mod

    async def fake_get(path, **kw):
        return {"positions": [{"ticket": 777, "open_price": 1.23, "sl": 1.20,
                               "tp": 1.30, "lot_size": 0.1, "symbol": "EURUSD"}]}

    monkeypatch.setattr(mt5mod, "_bridge_get", fake_get)
    out = asyncio.run(mt5mod._confirm_position(777))
    assert out["confirmed"] is True
    assert out["ticket"] == 777 and out["open_price"] == 1.23 and out["sl"] == 1.20


def test_confirm_position_not_visible(monkeypatch):
    import asyncio, app.routers.mt5 as mt5mod

    async def fake_get(path, **kw):
        return {"positions": []}

    monkeypatch.setattr(mt5mod, "_bridge_get", fake_get)
    out = asyncio.run(mt5mod._confirm_position(999))
    assert out["confirmed"] is False and "not yet visible" in out["reason"]


def test_confirm_position_no_ticket():
    import asyncio, app.routers.mt5 as mt5mod
    out = asyncio.run(mt5mod._confirm_position(None))
    assert out["confirmed"] is False


def test_confirm_position_swallows_bridge_error(monkeypatch):
    import asyncio, app.routers.mt5 as mt5mod

    async def boom(path, **kw):
        raise RuntimeError("tunnel down")

    monkeypatch.setattr(mt5mod, "_bridge_get", boom)
    out = asyncio.run(mt5mod._confirm_position(555))
    assert out["confirmed"] is False  # never raises — order already placed


# ── Scaled (staged) profit-booking ───────────────────────────────

def test_scaled_trade_splits_lot_across_targets(client, monkeypatch):
    import app.routers.mt5 as mt5mod
    calls = []

    async def fake_exec(symbol, direction, lot, sl, tp, ref):
        calls.append({"lot": lot, "sl": sl, "tp": tp})
        return {"order": 1000 + len(calls), "price": 1.20}

    monkeypatch.setattr(mt5mod, "_execute_market", fake_exec)
    monkeypatch.setattr(mt5mod, "_reference_price", lambda s: 1.20)

    r = client.post("/mt5/scaled-trade?symbol=EURUSD&direction=long&lot_size=0.09"
                    "&take_profits=1.2100,1.2200,1.2300&stop_loss=1.1900")
    assert r.status_code == 200
    body = r.json()
    assert body["legs"] == 3 and body["executed"] == 3
    assert len(calls) == 3
    # Equal thirds of 0.09.
    assert [round(c["lot"], 2) for c in calls] == [0.03, 0.03, 0.03]
    # Each leg carries its own TP and the shared SL.
    assert sorted(c["tp"] for c in calls) == [1.21, 1.22, 1.23]
    assert all(c["sl"] == 1.1900 for c in calls)


def test_scaled_trade_rejects_lot_too_small(client, monkeypatch):
    import app.routers.mt5 as mt5mod
    monkeypatch.setattr(mt5mod, "_reference_price", lambda s: 1.20)
    r = client.post("/mt5/scaled-trade?symbol=EURUSD&direction=long&lot_size=0.02"
                    "&take_profits=1.21,1.22,1.23")
    assert r.status_code == 400
    assert "too small to split" in r.json()["detail"]


def test_scaled_trade_reports_partial_failure(client, monkeypatch):
    import app.routers.mt5 as mt5mod
    from fastapi import HTTPException
    n = {"i": 0}

    async def flaky_exec(symbol, direction, lot, sl, tp, ref):
        n["i"] += 1
        if n["i"] == 2:
            raise HTTPException(status_code=400, detail="Broker rejected leg 2")
        return {"order": 500 + n["i"], "price": 1.2}

    monkeypatch.setattr(mt5mod, "_execute_market", flaky_exec)
    monkeypatch.setattr(mt5mod, "_reference_price", lambda s: 1.2)
    r = client.post("/mt5/scaled-trade?symbol=EURUSD&direction=long&lot_size=0.06"
                    "&take_profits=1.21,1.22").json()  # only 2 legs
    assert r["executed"] == 1
    statuses = [p["status"] for p in r["positions"]]
    assert "failed" in statuses and "executed" in statuses
