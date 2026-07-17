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


# ── structure + liquidity marking (BOS, BSL/SSL, per-TF fib ranges) ────

def _wave(n=120, base=100.0, amp=1.0, period=20):
    """Sine-ish wave: EQUAL highs every crest and EQUAL lows every trough —
    textbook resting liquidity on both sides."""
    import math
    out = []
    for i in range(n):
        p = base + amp * math.sin(2 * math.pi * i / period)
        out.append({"time": 1_700_000_000 + i * 900, "open": round(p, 4),
                    "high": round(p + 0.05, 4), "low": round(p - 0.05, 4),
                    "close": round(p, 4)})
    return out


def _staircase():
    """Higher highs + higher lows with closes breaking each prior swing high —
    textbook bullish Break of Structure."""
    pts = [(0, 99.0), (10, 101.0), (20, 100.0), (30, 102.0), (40, 101.0),
           (50, 103.0), (60, 102.5)]
    out = []
    for (i0, p0), (i1, p1) in zip(pts, pts[1:]):
        for i in range(i0, i1):
            p = p0 + (p1 - p0) * (i - i0) / (i1 - i0)
            out.append({"time": 1_700_000_000 + i * 900, "open": round(p, 4),
                        "high": round(p + 0.05, 4), "low": round(p - 0.05, 4),
                        "close": round(p, 4)})
    return out


def test_liquidity_detects_both_sides_with_side_metadata():
    a = ict_engine.analyze(_wave(), "EURUSD", "15m")
    liq = [p for p in a["patterns"] if p["type"] == "LIQUIDITY"]
    sides = {p["metadata"]["side"] for p in liq}
    assert "BSL" in sides, "equal highs must be marked as buy-side liquidity"
    assert "SSL" in sides, "equal lows must be marked as sell-side liquidity"
    # Resting (unswept) pools must NOT count as the 'Liquidity_Swept' confluence.
    if all(not p["metadata"]["swept"] for p in liq):
        assert "Liquidity_Swept" not in a["active_confluences"]


def test_bos_detected_on_trending_structure():
    a = ict_engine.analyze(_staircase(), "EURUSD", "15m")
    bos = [p for p in a["patterns"] if p["type"] == "BOS"]
    assert bos, "staircase higher-highs must produce a Break of Structure"
    assert all(p["direction"] == "bullish" for p in bos)


def test_levels_endpoint_exposes_per_tf_ranges_and_liquidity_sides(monkeypatch):
    from app.routers import ict as ict_router
    monkeypatch.setattr(ict_router.market_service, "get_history",
                        lambda s, tf, limit: _wave())
    out = ict_router.levels("EURUSD", timeframes="1h,15m")
    # one dealing range per timeframe -> each chart draws its own fibonacci
    assert set(out["ranges"].keys()) == {"1h", "15m"}
    for r in out["ranges"].values():
        assert r["low"] < r["equilibrium"] < r["high"]
    assert "htf_bias" in out
    types = {z["type"] for z in out["zones"]}
    assert ("BSL" in types) or ("SSL" in types), "liquidity zones must be side-tagged"
