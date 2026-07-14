"""Tests for public-channel (web-preview) Telegram polling."""
import httpx

from app.core.config import settings
from app.core.database import db
from app.services.telegram_service import telegram_service


# Minimal t.me/s/<channel> preview markup: two messages, one a clean signal.
SAMPLE_HTML = """
<html><body>
<div class="tgme_widget_message js-widget_message" data-post="xxictxx/100" data-view="1">
  <div class="tgme_widget_message_text js-message_text" dir="auto">
    XAUUSD SELL @ 4060.5 SL 4065.0 TP1 4055.0 TP2 4050.0 — ICT FVG setup
  </div>
  <div class="tgme_widget_message_footer compact js-message_footer">
    <time datetime="2026-07-14T12:00:00+00:00" class="time">12:00</time>
  </div>
</div>
<div class="tgme_widget_message js-widget_message" data-post="xxictxx/101" data-view="1">
  <div class="tgme_widget_message_text js-message_text" dir="auto">
    Good morning traders &amp; welcome<br>US CPI in 30 minutes
  </div>
  <div class="tgme_widget_message_footer compact js-message_footer">
    <time datetime="2026-07-14T12:30:00+00:00" class="time">12:30</time>
  </div>
</div>
</body></html>
"""


class _Resp:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


def test_parse_channel_html_extracts_messages():
    msgs = telegram_service._parse_channel_html(SAMPLE_HTML)
    assert len(msgs) == 2
    assert msgs[0]["post"] == "xxictxx/100"
    assert "XAUUSD SELL" in msgs[0]["text"]
    assert msgs[0]["datetime"].startswith("2026-07-14T12:00")
    # HTML entities decoded, <br> -> newline
    assert "&" in msgs[1]["text"]
    assert "\n" in msgs[1]["text"]


def test_poll_source_stores_and_dedupes(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_SOURCE_CHANNEL", "xxictxx")
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(SAMPLE_HTML))

    r1 = telegram_service.poll_source_channel()
    assert r1["ok"] is True
    assert r1["channel"] == "xxictxx"
    assert r1["new_signals"] == 2

    # The clean signal parsed symbol+side+SL.
    sig = db.find_one("telegram_signals", "xxictxx/100")
    assert sig is not None
    assert sig["symbol"] == "XAUUSD"
    assert sig["side"] == "SELL"
    assert sig["stop_loss"] == 4065.0
    assert sig["source"] == "web_preview"
    assert sig["source_channel"] == "xxictxx"

    # Second poll: same posts -> nothing new (dedup by channel/msgid).
    r2 = telegram_service.poll_source_channel()
    assert r2["new_signals"] == 0


def test_poll_source_fetch_error(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_SOURCE_CHANNEL", "xxictxx")

    def boom(*a, **k):
        raise httpx.ConnectError("no net")

    monkeypatch.setattr(httpx, "get", boom)
    r = telegram_service.poll_source_channel()
    assert r["ok"] is False
    assert r["new_signals"] == 0


def test_poll_source_endpoint(client, monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_SOURCE_CHANNEL", "xxictxx")
    monkeypatch.setattr(settings, "CRON_SECRET", "")
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(SAMPLE_HTML))
    resp = client.get("/telegram/poll-source")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_poll_source_is_public_even_when_auth_enabled(monkeypatch):
    """The cron/bridge scheduler can't carry X-Api-Key, so this path must be
    exempt from the key gate even with AUTH_ENABLED (it's guarded by CRON_SECRET)."""
    from app.core import auth
    from app.core.config import settings
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "API_KEY", "secret")
    # Exempt regardless of the /api prefix normalization.
    assert auth.should_require_api_key("GET", "/telegram/poll-source") is False
    assert auth.should_require_api_key("GET", "/api/telegram/poll-source") is False
    # A sibling telegram GET is still gated.
    assert auth.should_require_api_key("GET", "/telegram/signals") is True


def test_poll_source_endpoint_requires_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "CRON_SECRET", "s3cret")
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(SAMPLE_HTML))
    # No auth header -> 401
    assert client.get("/telegram/poll-source").status_code == 401
    # Correct bearer -> 200
    ok = client.get("/telegram/poll-source", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200
