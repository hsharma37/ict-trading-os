"""Tests for real-time news tagging precision."""
from datetime import datetime, timedelta, timezone

import httpx

from app.services.news_service import news_service


def _recent(hours_ago: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


SAMPLE_RSS = f"""<?xml version="1.0"?><rss><channel>
<item><title>EUR/USD Price Forecast: bulls cautious below 1.1470</title>
<description>The pair holds gains.</description><link>http://x/1</link>
<pubDate>{_recent(1)}</pubDate></item>
<item><title>Gold climbs as safe-haven demand rises</title>
<description>XAU/USD advances.</description><link>http://x/2</link>
<pubDate>{_recent(2)}</pubDate></item>
<item><title>US CPI inflation data comes in hot, Fed hike bets rise</title>
<description>Dollar broadly bid.</description><link>http://x/3</link>
<pubDate>{_recent(3)}</pubDate></item>
<item><title>Indonesian Rupiah firms on trade balance</title>
<description>Local markets steady.</description><link>http://x/4</link>
<pubDate>{_recent(4)}</pubDate></item>
</channel></rss>"""


class _Resp:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status


def _wire(monkeypatch):
    from app.core.config import settings
    from app.services import bridge_config
    # Force the direct-fetch path (no residential bridge) for deterministic tests.
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "")
    bridge_config.clear_cache()
    news_service.clear_cache()
    calls = {"n": 0}

    def fake_get(url, **kwargs):
        calls["n"] += 1
        # First feed returns the sample; others empty so dedup/merge is exercised.
        return _Resp(SAMPLE_RSS if calls["n"] == 1 else "<rss></rss>")

    monkeypatch.setattr(httpx, "get", fake_get)


def test_explicit_pair_tags_single_symbol(monkeypatch):
    _wire(monkeypatch)
    news = news_service.get_news(limit=20)
    by_title = {n["title"][:10]: n for n in news}
    eur = next(n for n in news if n["title"].startswith("EUR/USD"))
    assert eur["symbols"] == ["EURUSD"]  # precise: not all pairs


def test_gold_tags_xauusd(monkeypatch):
    _wire(monkeypatch)
    gold = next(n for n in news_service.get_news(limit=20) if n["title"].startswith("Gold"))
    assert gold["symbols"] == ["XAUUSD"]
    assert "gold" in gold["reason"].lower()


def test_usd_macro_fans_out_to_all(monkeypatch):
    _wire(monkeypatch)
    cpi = next(n for n in news_service.get_news(limit=20) if "CPI" in n["title"])
    assert set(cpi["symbols"]) == {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "XAUUSD"}
    assert cpi["impact"] == "high"


def test_irrelevant_headline_untagged(monkeypatch):
    _wire(monkeypatch)
    rupiah = next(n for n in news_service.get_news(limit=20) if "Rupiah" in n["title"])
    assert rupiah["symbols"] == []  # a passing mention shouldn't tag everything


def test_stale_items_dropped(monkeypatch):
    from app.core.config import settings
    from app.services import bridge_config
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "")
    bridge_config.clear_cache()
    news_service.clear_cache()
    stale = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%a, %d %b %Y %H:%M:%S %z")
    rss = f"""<rss><channel>
    <item><title>Gold rallies today</title><description>x</description><link>l</link><pubDate>{_recent(2)}</pubDate></item>
    <item><title>Old gold story from a month ago</title><description>x</description><link>l</link><pubDate>{stale}</pubDate></item>
    </channel></rss>"""
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(rss))
    titles = [n["title"] for n in news_service.get_news(limit=20)]
    assert "Gold rallies today" in titles
    assert "Old gold story from a month ago" not in titles  # >72h -> dropped


def test_all_items_have_timestamps(monkeypatch):
    _wire(monkeypatch)
    assert all(n.get("timestamp") for n in news_service.get_news(limit=20))


def test_symbol_filter(monkeypatch):
    _wire(monkeypatch)
    xau = news_service.get_news(limit=20, symbol="XAUUSD")
    assert all("XAUUSD" in n["symbols"] for n in xau)
    assert any(n["title"].startswith("Gold") for n in xau)
