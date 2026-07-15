"""Real-time market news relevant to the instruments the app trades.

Pulls headlines from public forex/markets RSS feeds (FXStreet primary), tags each
item with the **supported symbols it can move** and a short, factual reason, rates
impact, caches briefly, and falls back to the residential MT5 bridge if a feed is
blocked from the cloud IP. No API key required.
"""
from __future__ import annotations

import html as html_lib
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional

import httpx

from app.services.instrument_config import get_all_instruments

# Fresh, forex-focused feeds only. (Dropped feeds.a.dj.com/RSSMarketsMain — it
# serves stale cached items to datacenter IPs.) FXStreet is cloud-blocked, so it
# loads via the residential bridge; Investing.com loads directly.
_FEEDS = [
    "https://www.fxstreet.com/rss/news",
    "https://www.investing.com/rss/news_1.rss",
    "https://www.fxstreet.com/rss/majors",
]

# Only show news from the last few days — never stale items.
_MAX_AGE_HOURS = 72

# Per-currency focus keywords (currency name + its central bank). A passing "USD"
# mention is deliberately NOT here — only genuine USD-macro events (below) fan out
# to every dollar pair, so tagging stays precise instead of tagging all 6 on every
# headline.
_CCY_KEYWORDS = {
    "EUR": ["euro", "ecb", "eurozone", "euro-zone", "lagarde", "sintra", "bundesbank"],
    "GBP": ["pound", "sterling", "cable", " boe", "bank of england", "bailey", "gilt"],
    "JPY": ["yen", " boj", "bank of japan", "ueda"],
    "AUD": ["aussie", " rba", "reserve bank of australia", "australian dollar"],
    "NZD": ["kiwi", "rbnz", "reserve bank of new zealand", "new zealand dollar"],
    "CAD": ["loonie", " boc", "bank of canada", "canadian dollar"],
    "XAU": ["xau", "gold", "bullion", "precious metal", "safe haven", "safe-haven"],
}

# USD-macro events that genuinely move ALL dollar pairs (and gold).
_USD_MACRO = [
    "fed ", "fomc", "powell", "nonfarm", "non-farm", "nfp", "cpi", "pce",
    "jobless", "payroll", "u.s. inflation", "us inflation", "inflation data",
    "dollar index", "dxy", "treasury yields", "rate decision", "jackson hole",
]

_ALL_CCYS = ["EUR", "USD", "GBP", "JPY", "AUD", "NZD", "CAD"]

# High-impact scheduled/econ events.
_HIGH_IMPACT = [
    "rate decision", "rate hike", "rate cut", "interest rate", "fomc", "nonfarm",
    "non-farm", "nfp", "cpi", "inflation", "gdp", "pce", "jobs report", "payroll",
    "central bank", "emergency", "breaking", "intervention",
]

_CACHE_TTL = 300.0  # 5 min


def _monotonic() -> float:
    return time.monotonic()


class NewsService:
    def __init__(self) -> None:
        self._cache: Optional[List[Dict]] = None
        self._cache_at: float = 0.0

    # ── currency / symbol mapping ────────────────────────────────────

    def _supported_currencies(self) -> Dict[str, List[str]]:
        """currency code -> supported symbols containing it (e.g. USD -> all pairs)."""
        out: Dict[str, List[str]] = {}
        for sym in get_all_instruments():
            s = sym.upper()
            if s == "XAUUSD":
                out.setdefault("XAU", []).append(sym)
                out.setdefault("USD", []).append(sym)
                continue
            for ccy in (s[:3], s[3:6]):
                if ccy:
                    out.setdefault(ccy, []).append(sym)
        return out

    def _tag_symbols(self, title: str, blob: str, ccy_map: Dict[str, List[str]], supported: set) -> List[str]:
        low = blob.lower()
        title_low = title.lower()
        symbols: set = set()

        # 1) Explicit pair mentions (EUR/USD, XAU/USD, GBPUSD) -> that exact pair.
        for m in re.finditer(r"\b([a-z]{3})[\/\-]?([a-z]{3})\b", low):
            pair = (m.group(1) + m.group(2)).upper().replace("XAG", "XAU")
            if pair in supported:
                symbols.add(pair)

        # 2) Per-currency focus (a currency + its central bank) -> its supported pairs.
        hit_ccys = set()
        for ccy, words in _CCY_KEYWORDS.items():
            if any(w in low for w in words):
                hit_ccys.add(ccy)

        # 3) USD-macro events move every dollar pair (and gold) — judged from the
        # TITLE only, so a passing mention in a long summary doesn't tag all 6.
        if any(w in title_low for w in _USD_MACRO):
            hit_ccys.update(_ALL_CCYS)
            hit_ccys.add("XAU")

        for ccy in hit_ccys:
            symbols.update(ccy_map.get(ccy, []))
        return sorted(symbols)

    def _impact(self, text: str) -> str:
        low = text.lower()
        return "high" if any(k in low for k in _HIGH_IMPACT) else "medium"

    def _reason(self, symbols: List[str], text: str) -> str:
        if not symbols:
            return ""
        low = text.lower()
        drivers = []
        if any(w in low for w in _USD_MACRO):
            drivers.append("a US-macro event (moves all USD pairs & gold)")
        for ccy, words in _CCY_KEYWORDS.items():
            if any(w in low for w in words):
                drivers.append("gold" if ccy == "XAU" else ccy)
        driver = "; ".join(dict.fromkeys(drivers)) if drivers else "the pair named in the headline"
        return f"Driver: {driver}. Affects {', '.join(symbols)}."

    # ── fetch + parse ────────────────────────────────────────────────

    @staticmethod
    def _clean(fragment: str) -> str:
        fragment = re.sub(r"<[^>]+>", "", fragment or "")
        return html_lib.unescape(fragment).strip()

    @staticmethod
    def _parse_date(pub: str):
        """Parse the several pubDate formats feeds use -> tz-aware UTC datetime."""
        pub = (pub or "").strip()
        if not pub:
            return None
        # RFC-822 (FXStreet: "Wed, 15 Jul 2026 05:26:01 Z" / WSJ with offset).
        try:
            dt = parsedate_to_datetime(pub)
            if dt:
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
        # Plain "YYYY-MM-DD HH:MM:SS" (Investing.com) and ISO variants.
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(pub, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    def _parse_feed(self, xml_text: str, source_hint: str) -> List[Dict]:
        try:
            root = ET.fromstring(xml_text)
        except Exception:
            return []
        items = []
        for it in root.findall(".//item"):
            title = self._clean(it.findtext("title") or "")
            if not title:
                continue
            desc = self._clean(it.findtext("description") or "")
            link = (it.findtext("link") or "").strip()
            dt = self._parse_date(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date") or "")
            items.append({"title": title, "summary": desc[:400], "link": link,
                          "_dt": dt, "timestamp": dt.astimezone(timezone.utc).isoformat() if dt else None,
                          "source": source_hint})
        return items

    def _fetch_direct(self, url: str) -> Optional[str]:
        try:
            r = httpx.get(url, timeout=8, follow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0 (compatible; ICTradingOS/1.0)"})
            if r.status_code == 200 and r.text:
                return r.text
        except Exception:
            return None
        return None

    def _fetch_via_bridge(self, url: str) -> Optional[str]:
        """Residential-IP fallback if a feed blocks the cloud IP."""
        from app.services.bridge_config import get_bridge_url, get_bridge_api_key
        base = get_bridge_url()
        if not base:
            return None
        headers = {"ngrok-skip-browser-warning": "true"}
        key = get_bridge_api_key()
        if key:
            headers["X-Bridge-Key"] = key
        try:
            r = httpx.get(f"{base}/fetch", params={"url": url}, headers=headers, timeout=12)
            if r.status_code == 200:
                data = r.json()
                return data.get("body")
        except Exception:
            return None
        return None

    def get_news(self, limit: int = 25, symbol: Optional[str] = None) -> List[Dict]:
        now = _monotonic()
        if self._cache is None or (now - self._cache_at) >= _CACHE_TTL:
            self._cache = self._build()
            self._cache_at = now
        news = self._cache
        if symbol:
            s = symbol.upper()
            news = [n for n in news if s in n.get("symbols", [])]
        return news[:limit]

    def _build(self) -> List[Dict]:
        ccy_map = self._supported_currencies()
        supported = {s.upper() for s in get_all_instruments()}
        raw: List[Dict] = []
        seen_titles = set()
        # Forex-specific feeds (FXStreet/Investing) block datacenter IPs, so when
        # the residential bridge is available fetch through it first; else direct.
        from app.services.bridge_config import get_bridge_url
        bridge_ready = bool(get_bridge_url())
        for url in _FEEDS:
            src = "FXStreet" if "fxstreet" in url else ("Investing.com" if "investing" in url else "WSJ Markets")
            if bridge_ready:
                xml_text = self._fetch_via_bridge(url) or self._fetch_direct(url)
            else:
                xml_text = self._fetch_direct(url)
            if not xml_text:
                continue
            for item in self._parse_feed(xml_text, src):
                key = item["title"].lower()[:80]
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                blob = f"{item['title']} {item['summary']}"
                symbols = self._tag_symbols(item["title"], blob, ccy_map, supported)
                item["symbols"] = symbols
                item["impact"] = self._impact(blob)
                item["reason"] = self._reason(symbols, blob)
                item["relevant"] = bool(symbols)
                raw.append(item)

        # Keep only dated, recent items (never stale), newest first.
        cutoff = datetime.now(timezone.utc) - timedelta(hours=_MAX_AGE_HOURS)
        fresh = [n for n in raw if n.get("_dt") and n["_dt"] >= cutoff]
        fresh.sort(key=lambda n: n["_dt"], reverse=True)
        for n in fresh:
            n.pop("_dt", None)  # internal only; don't serialize
        return fresh or self._static_fallback()

    def _static_fallback(self) -> List[Dict]:
        """Last resort if every feed is unreachable — keeps the panel non-empty."""
        return [{
            "title": "Live news feed temporarily unavailable",
            "summary": "Could not reach the market news providers. Prices and trading are unaffected.",
            "link": "", "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "system", "symbols": [], "impact": "low", "reason": "", "relevant": False,
        }]

    def clear_cache(self) -> None:
        self._cache = None
        self._cache_at = 0.0


news_service = NewsService()
