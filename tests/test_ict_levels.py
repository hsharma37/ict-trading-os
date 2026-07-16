"""Live ICT levels: zones carry real price ranges + position vs current price."""
from app.services import market_data as md
from app.services.ict_engine import ict_engine


def _trend(n, base=100.0, up=True):
    c, p = [], base
    for i in range(n):
        p += (0.5 if up else -0.5) * (1 if (i // 15) % 2 == 0 else -0.6)
        c.append({"time": 1_700_000_000 + i * 900, "open": round(p, 3),
                  "high": round(p + 0.4, 3), "low": round(p - 0.4, 3), "close": round(p, 3)})
    return c


def test_range_levels_has_equilibrium():
    r = ict_engine.range_levels(_trend(120))
    assert r and r["low"] < r["equilibrium"] < r["high"]


def test_levels_endpoint_annotates_position(monkeypatch):
    from app.routers import ict as ict_router
    monkeypatch.setattr(ict_router.market_service, "get_history",
                        lambda s, tf, limit: _trend(150))
    out = ict_router.levels("EURUSD", timeframes="15m")
    assert out["symbol"] == "EURUSD" and out["current_price"] is not None
    assert "dealing_range" in out
    for z in out["zones"]:
        assert z["position"] in ("above", "below", "inside")
        assert z["high"] >= z["low"]
        # zone is on the correct side of price
        if z["position"] == "above":
            assert z["low"] > out["current_price"] - 1e-6


def test_levels_refuses_nothing_but_flags_synthetic(monkeypatch):
    from app.routers import ict as ict_router
    synth = [{**c, "synthetic": True} for c in _trend(150)]
    monkeypatch.setattr(ict_router.market_service, "get_history", lambda s, tf, limit: synth)
    out = ict_router.levels("EURUSD", timeframes="15m")
    assert out["synthetic"] is True
