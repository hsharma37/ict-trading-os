"""Tests for the runtime-resolvable MT5 bridge URL (DB override -> env)."""
from app.core.config import settings
from app.core.database import db
from app.services import bridge_config


def test_env_used_when_no_override(monkeypatch):
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "http://env-bridge")
    bridge_config.clear_cache()
    assert bridge_config.get_bridge_url() == "http://env-bridge"


def test_trailing_slash_stripped(monkeypatch):
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "http://env-bridge/")
    bridge_config.clear_cache()
    assert bridge_config.get_bridge_url() == "http://env-bridge"


def test_db_override_wins_over_env(monkeypatch):
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "http://env-bridge")
    effective = bridge_config.set_bridge_url("https://tunnel.example.com/")
    assert effective == "https://tunnel.example.com"
    assert bridge_config.get_bridge_url() == "https://tunnel.example.com"


def test_clearing_override_falls_back_to_env(monkeypatch):
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "http://env-bridge")
    bridge_config.set_bridge_url("https://tunnel.example.com")
    assert bridge_config.get_bridge_url() == "https://tunnel.example.com"
    bridge_config.set_bridge_url("")  # clear
    assert bridge_config.get_bridge_url() == "http://env-bridge"


def test_settings_endpoint_reports_source(client, monkeypatch):
    monkeypatch.setattr(settings, "MT5_BRIDGE_URL", "http://env-bridge")
    bridge_config.clear_cache()
    # start on env
    body = client.get("/settings").json()
    assert body["mt5_bridge_url"] == "http://env-bridge"
    assert body["mt5_bridge_url_source"] == "env"
    # persist an override directly, then it should report override
    bridge_config.set_bridge_url("https://my-tunnel.trycloudflare.com")
    body = client.get("/settings").json()
    assert body["mt5_bridge_url"] == "https://my-tunnel.trycloudflare.com"
    assert body["mt5_bridge_url_source"] == "override"
