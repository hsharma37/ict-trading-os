"""Tests for fetching YouTube transcripts through the MT5 bridge (residential IP)."""
from app.core.config import settings
from app.services.youtube_service import youtube_service, VideoTranscript


class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_bridge_transcript_used_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "http://bridge")
    monkeypatch.setattr(settings, "MT5_BRIDGE_API_KEY", "k")
    payload = {"text": "hello world", "segments": [{"text": "hello", "start": 0}],
               "language": "en", "is_generated": True}
    monkeypatch.setattr(youtube_service._http_client, "get", lambda *a, **k: _Resp(200, payload))

    t = youtube_service.fetch_video_transcript("vid123", allow_whisper=False)
    assert isinstance(t, VideoTranscript)
    assert t.source == "bridge"
    assert t.text == "hello world"


def test_no_bridge_configured_returns_none_helper(monkeypatch):
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "")
    assert youtube_service._fetch_transcript_via_bridge("vid", ["en"]) is None


def test_bridge_error_falls_through(monkeypatch):
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "http://bridge")
    monkeypatch.setattr(youtube_service._http_client, "get", lambda *a, **k: _Resp(502, {"error": "x"}))
    assert youtube_service._fetch_transcript_via_bridge("vid", ["en"]) is None
