"""Bridge provider selection: ctrader default, mt5 opt-in, runtime override."""
from fastapi.testclient import TestClient

from app.main import app
from app.services.bridge_config import get_bridge_provider, set_bridge_provider


def test_provider_defaults_to_pinned_env(monkeypatch):
    """The suite pins BRIDGE_PROVIDER=mt5 (see conftest); the setting resolves."""
    monkeypatch.setattr("app.core.config.settings.BRIDGE_PROVIDER", "mt5")
    assert get_bridge_provider(force_refresh=True) == "mt5"


def test_provider_falls_back_to_ctrader_when_env_unknown(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.BRIDGE_PROVIDER", "nonsense")
    assert get_bridge_provider(force_refresh=True) == "ctrader"


def test_provider_db_override_wins(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.BRIDGE_PROVIDER", "mt5")
    set_bridge_provider("ctrader")
    assert get_bridge_provider(force_refresh=True) == "ctrader"


def test_provider_rejects_unknown_value():
    import pytest
    with pytest.raises(ValueError):
        set_bridge_provider("oanda")


def test_settings_endpoints_expose_and_set_provider():
    client = TestClient(app)
    r = client.get("/api/settings/bridge-provider")
    assert r.status_code == 200
    assert r.json()["bridge_provider"] in ("mt5", "ctrader")

    r = client.post("/api/settings/bridge-provider", json={"provider": "ctrader"})
    assert r.status_code == 200
    assert r.json()["bridge_provider"] == "ctrader"

    r = client.post("/api/settings/bridge-provider", json={"provider": "bad"})
    assert r.status_code == 422


def test_settings_payload_includes_provider():
    client = TestClient(app)
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert "bridge_provider" in r.json()
