"""Trading Strategist — regime detection + evidence-gated planning."""
import math
import pytest

from app.services import market_data as md
from app.services import strategist_service as st


def _trending(n=700, base=1.10, drift=0.0008):
    out, p = [], base
    for i in range(n):
        o = p
        c = p + drift + 0.001 * math.sin(i / 7.0)
        h = max(o, c) + 0.0006
        l = min(o, c) - 0.0006
        out.append({"time": 1_700_000_000 + i * 3600, "open": round(o, 5), "high": round(h, 5),
                    "low": round(l, 5), "close": round(c, 5), "volume": 100})
        p = c
    return out


def _choppy(n=700, base=1.10):
    out = []
    for i in range(n):
        p = base + 0.003 * math.sin(i / 3.0) + 0.002 * math.sin(i / 11.0)
        out.append({"time": 1_700_000_000 + i * 3600, "open": round(p, 5),
                    "high": round(p + 0.0025, 5), "low": round(p - 0.0025, 5),
                    "close": round(p + 0.0008 * math.cos(i / 2.0), 5), "volume": 100})
    return out


def test_regime_trending_up_detected():
    r = st.detect_regime(_trending())
    assert r["regime"] == "trending_up"
    assert r["direction"] == "bullish"
    assert r["adx"] > 25 and r["efficiency_ratio"] >= 0.25
    assert "rules" in r  # thresholds are stated, not hidden


def test_regime_chop_not_trending():
    r = st.detect_regime(_choppy())
    assert r["regime"] in ("ranging", "unclear")


def test_plan_structure_and_evidence_gate(monkeypatch):
    data = _trending()
    monkeypatch.setattr(md.market_service, "get_history",
                        lambda s, tf="1h", limit=200, history_range=None: data[-limit:])
    plan = st.build_plan("EURUSD", "1h", 2.0)
    assert not plan.get("error")
    assert plan["action"] in ("TRADE_CANDIDATE", "STAND_ASIDE")
    assert plan["regime"]["regime"] == "trending_up"
    assert isinstance(plan["evidence"], list) and plan["caveats"]
    if plan["action"] == "TRADE_CANDIDATE":
        rec = plan["recommendation"]
        # The gate: recommended strategy must fit the regime AND be measured
        # positive with a real sample — never a style-mismatched pick.
        assert rec["style"] in ("trend", "breakout", "trend-pullback")
        assert rec["expectancy_r"] > 0 and rec["trades"] >= st._MIN_TRADES
        assert plan["setup"]["status"] in ("actionable", "wait")
    else:
        assert "reason" in plan


def test_plan_stand_aside_in_unclear_regime(monkeypatch):
    data = _choppy()
    monkeypatch.setattr(md.market_service, "get_history",
                        lambda s, tf="1h", limit=200, history_range=None: data[-limit:])
    plan = st.build_plan("EURUSD", "1h", 2.0)
    assert not plan.get("error")
    if plan["regime"]["regime"] == "unclear":
        assert plan["action"] == "STAND_ASIDE"


def test_plan_refuses_without_data(monkeypatch):
    monkeypatch.setattr(md.market_service, "get_history",
                        lambda s, tf="1h", limit=200, history_range=None: [])
    assert st.build_plan("EURUSD", "1h", 2.0).get("error")
