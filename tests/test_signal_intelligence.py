"""Tests for news-sentiment signal fusion."""
from app.services.signal_intelligence import signal_intelligence as si


def _news(title, impact="medium", ts="2026-07-15T05:00:00+00:00"):
    return {"title": title, "impact": impact, "source": "Test", "timestamp": ts, "link": ""}


def test_weak_dollar_is_bullish_for_eurusd():
    news = [_news("US Dollar retreats after soft inflation data")]
    s = si.news_sentiment("EURUSD", news)
    # USD is the quote; a weak dollar => bullish EURUSD.
    assert s["label"] == "bullish"
    assert s["score"] > 0


def test_weak_dollar_is_bullish_for_gold():
    news = [_news("Gold climbs as US Dollar slips on dovish Fed")]
    s = si.news_sentiment("XAUUSD", news)
    assert s["label"] == "bullish"  # gold rises + weak USD both push XAUUSD up


def test_strong_dollar_is_bearish_for_eurusd():
    news = [_news("US Dollar surges after hot CPI, hawkish Fed bets rise")]
    s = si.news_sentiment("EURUSD", news)
    assert s["label"] == "bearish"
    assert s["score"] < 0


def test_euro_strength_is_bullish_for_eurusd():
    news = [_news("Euro rallies as ECB signals higher rates")]
    s = si.news_sentiment("EURUSD", news)
    assert s["label"] == "bullish"


def test_neutral_when_no_directional_words():
    news = [_news("EUR/USD trades sideways into the European session")]
    s = si.news_sentiment("EURUSD", news)
    assert s["label"] == "neutral"


def test_generate_shape_and_reasoning(monkeypatch):
    # Stub the heavy dependencies so the fusion is deterministic and offline.
    from app.services import signal_intelligence as mod
    monkeypatch.setattr("app.services.research_service.research_service.analyze_instrument",
                        lambda symbol: {"trend": "BULLISH", "sentiment": "BULLISH", "change_pct": 0.4,
                                        "support": 1.1380, "resistance": 1.1470, "current_price": 1.1420,
                                        "sma20": 1.1400, "reasoning": "Price above SMAs. Bullish."})
    monkeypatch.setattr("app.services.news_service.news_service.get_news",
                        lambda limit=12, symbol=None: [_news("US Dollar retreats after soft inflation data", impact="high")])
    out = si.generate("EURUSD")
    assert out["symbol"] == "EURUSD"
    assert out["signal"] in {"BUY", "SELL", "NEUTRAL"}
    assert out["signal"] == "BUY"  # bullish news (weak USD) + bullish trend
    assert out["confidence"] in {"low", "medium", "high"}
    assert len(out["factors"]) >= 3
    assert out["reasoning"]
    assert len(out["suggestions"]) >= 2
    # Factor names present.
    names = {f["name"] for f in out["factors"]}
    assert {"News sentiment", "Technical trend", "Momentum (24h)"} <= names


def test_conflict_caps_confidence(monkeypatch):
    monkeypatch.setattr("app.services.research_service.research_service.analyze_instrument",
                        lambda symbol: {"trend": "BEARISH", "sentiment": "BEARISH", "change_pct": -0.3,
                                        "support": None, "resistance": None, "current_price": 1.14,
                                        "sma20": None, "reasoning": "Bearish."})
    monkeypatch.setattr("app.services.news_service.news_service.get_news",
                        lambda limit=12, symbol=None: [_news("Euro surges, US Dollar tumbles on soft data", impact="high")])
    out = si.generate("EURUSD")
    # News bullish, technicals bearish -> conflict -> confidence capped low/medium.
    assert out["confidence"] != "high"


# ── signal_engine adopts Signal-Intelligence direction + adjustable R ──

def test_calculate_entry_target_r_scales_targets():
    from app.services.ict_engine import ict_engine
    patterns = [{"type": "OB", "direction": "bullish", "price_level": 1.10,
                 "metadata": {"ob_high": 1.10, "ob_low": 1.09}}]
    # default 3.0 -> 1R/2R/3R (unchanged behaviour)
    d3 = ict_engine.calculate_entry(patterns, "BULLISH", 1.10, target_r=3.0)
    risk = d3["risk"]
    assert round(d3["tp3"] - d3["entry"], 5) == round(risk * 3, 5)
    # 2R -> tp3 sits at exactly 2R
    d2 = ict_engine.calculate_entry(patterns, "BULLISH", 1.10, target_r=2.0)
    assert round(d2["tp3"] - d2["entry"], 5) == round(risk * 2, 5)
    assert d2["target_r"] == 2.0


def test_signal_engine_adopts_signal_intelligence_direction(monkeypatch):
    from app.services import signal_engine as se
    # Force ICT structural bias NEUTRAL but SI says BUY -> engine should go BULLISH.
    monkeypatch.setattr(se.market_service, "get_history",
                        lambda s, tf, limit: [{"time": i, "open": 1.1, "high": 1.11,
                                               "low": 1.09, "close": 1.1} for i in range(60)])
    monkeypatch.setattr(se.ict_engine, "analyze",
                        lambda c, s, tf: {"current_bias": "NEUTRAL", "patterns": [],
                                          "current_price": 1.1, "premium_discount": "discount"})
    import app.services.signal_intelligence as si_mod
    monkeypatch.setattr(si_mod.signal_intelligence, "generate",
                        lambda symbol: {"signal": "BUY"})
    out = se.signal_engine.analyze("EURUSD", target_r=2.0)
    assert out["bias_source"] == "signal_intelligence"
    assert out["htf_bias"] == "BULLISH"
    assert out["target_r"] == 2.0
