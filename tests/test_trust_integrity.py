"""Trust-integrity guarantees: the app must never present fabricated data as
real, never auto-trade on a guessed stop, and label heuristics honestly."""
from app.core.database import db


def _synth_candles(n=100, base=1.10):
    return [{"time": i, "open": base, "high": base * 1.001, "low": base * 0.999,
             "close": base, "volume": 0, "synthetic": True} for i in range(n)]


# ── synthetic market data must be flagged, never shown as real ────────

def test_history_is_synthetic_detects_fallback():
    from app.services.market_data import history_is_synthetic
    assert history_is_synthetic(_synth_candles()) is True
    real = [{"time": 1, "open": 1.1, "high": 1.1, "low": 1.1, "close": 1.1}]
    assert history_is_synthetic(real) is False
    assert history_is_synthetic([]) is False


def test_research_flags_synthetic_and_refuses(monkeypatch):
    from app.services import research_service as rs
    monkeypatch.setattr(rs.market_service, "get_price",
                        lambda s: {"price": 1.10, "source": "synthetic", "stale": False, "change_pct": 0.0})
    monkeypatch.setattr(rs.market_service, "get_history",
                        lambda s, tf="1h", limit=100: _synth_candles())
    out = rs.research_service.analyze_instrument("EURUSD")
    assert out["data_quality"] == "synthetic" and out["synthetic"] is True
    assert "DATA UNAVAILABLE" in out["reasoning"]  # not confident levels


def test_signal_refuses_on_synthetic(monkeypatch):
    from app.services.research_service import research_service
    from app.services.news_service import news_service
    from app.services.signal_intelligence import signal_intelligence
    monkeypatch.setattr(research_service, "analyze_instrument",
                        lambda s: {"data_quality": "synthetic", "data_source": "synthetic",
                                   "current_price": 1.1, "trend": "BULLISH", "sentiment": "BULLISH"})
    monkeypatch.setattr(news_service, "get_news", lambda limit=12, symbol=None: [])
    out = signal_intelligence.generate("EURUSD")
    assert out["signal"] == "NEUTRAL" and out.get("unavailable") is True
    assert out["data_quality"] == "synthetic"
    assert out["confidence_score"] == 0


def test_live_signal_carries_honest_basis(monkeypatch):
    from app.services.research_service import research_service
    from app.services.news_service import news_service
    from app.services.signal_intelligence import signal_intelligence
    monkeypatch.setattr(research_service, "analyze_instrument",
                        lambda s: {"data_quality": "live", "data_source": "yahoo", "stale": False,
                                   "trend": "BULLISH", "sentiment": "BULLISH", "change_pct": 0.3,
                                   "current_price": 1.1, "support": 1.09, "resistance": 1.11,
                                   "sma20": 1.10, "reasoning": "up."})
    monkeypatch.setattr(news_service, "get_news", lambda limit=12, symbol=None: [])
    out = signal_intelligence.generate("EURUSD")
    assert out["data_quality"] == "live"
    assert "not backtested" in out["confidence_basis"]
    assert out["news_sentiment"]["method"] == "keyword-polarity"


# ── Telegram: never auto-trade a guessed stop ─────────────────────────

def test_parser_flags_inferred_sl():
    from app.services.telegram_service import telegram_service
    p = telegram_service._parse_signal("EURUSD BUY 1.1000 1.0950 1.1100")
    assert p["stop_loss"] == 1.0950 and p.get("sl_inferred") is True


def test_inferred_sl_blocks_autotrade():
    from app.services.telegram_service import telegram_service
    db.insert("telegram_signals", {"id": "trust_t1", "parsed": True, "symbol": "EURUSD",
                                   "side": "BUY", "entry_prices": [1.10], "stop_loss": 1.09,
                                   "sl_inferred": True, "auto_traded": False})
    res = telegram_service.auto_trade("trust_t1")
    assert "inferred" in res.get("error", "").lower()
    db.delete("telegram_signals", "trust_t1")


# ── News impact is no longer inflated ─────────────────────────────────

def test_news_impact_has_real_low_tier():
    from app.services.news_service import news_service
    assert news_service._impact("Fed rate decision due Wednesday") == "high"
    assert news_service._impact("Retail sales data disappoints") == "medium"
    assert news_service._impact("Broker unveils redesigned mobile app logo") == "low"


# ── Telegram discard / keep ───────────────────────────────────────────

def test_telegram_discard_and_restore():
    from app.services.telegram_service import telegram_service
    db.insert("telegram_signals", {"id": "disc1", "symbol": "EURUSD", "side": "BUY",
                                   "created_at": "2026-07-16T00:00:00", "discarded": False})
    telegram_service.discard("disc1")
    assert all(s["id"] != "disc1" for s in telegram_service.get_signals())          # hidden
    assert any(s["id"] == "disc1" for s in telegram_service.get_signals(include_discarded=True))
    telegram_service.restore("disc1")
    assert any(s["id"] == "disc1" for s in telegram_service.get_signals())          # back
    db.delete("telegram_signals", "disc1")


# ── Yahoo candle window regression (range= not period=) ───────────────

def test_get_history_uses_range_param(monkeypatch):
    """Guards the one-word bug that starved every timeframe of candles
    (period= was ignored → ~14 candles → HTF bias/SMA/2R all broke)."""
    import app.services.market_data as md
    captured = {}

    class _Resp:
        def raise_for_status(self): pass
        def json(self):
            return {"chart": {"result": [{"timestamp": [1, 2],
                    "indicators": {"quote": [{"open": [1, 1], "high": [1, 1],
                    "low": [1, 1], "close": [1, 1], "volume": [0, 0]}]}}]}}

    class _Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url): captured["url"] = url; return _Resp()

    monkeypatch.setattr(md.oanda_service, "get_history", lambda *a, **k: None)
    monkeypatch.setattr(md.httpx, "Client", _Client)
    md.market_service.get_history("EURUSD", "1h", 100)
    assert "range=" in captured["url"] and "period=" not in captured["url"]
