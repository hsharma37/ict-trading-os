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


def test_sentiment_handles_negation_and_intensity():
    from app.services.signal_intelligence import signal_intelligence as si
    # Plain: "dollar rises" → USD positive.
    assert si._currency_polarities("dollar rises")["USD"] > 0
    # Negated: "dollar fails to rise" → USD flips negative.
    assert si._currency_polarities("dollar fails to rise")["USD"] < 0
    # "gold not higher" → XAU negative.
    assert si._currency_polarities("gold not higher")["XAU"] < 0
    # Intensity: a surge weighs more than a mild gain.
    strong = si._currency_polarities("euro surges")["EUR"]
    mild = si._currency_polarities("euro gains")["EUR"]
    assert strong > mild > 0
