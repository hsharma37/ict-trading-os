"""
Tests for the MT5 bridge: auth decorator and graceful degradation when the
MetaTrader5 package/terminal isn't available (true on any non-Windows
machine, including CI and this dev environment).

Run from this directory: `pytest test_bridge.py` (needs flask/requests/
python-dotenv — see requirements.txt; MetaTrader5 itself is Windows-only and
not required for these tests).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest

from mt5_client import Mt5Client, Mt5ConnectionError


# ── Mt5Client: graceful degradation without the MetaTrader5 package ──


def test_client_reports_unavailable_without_package():
    client = Mt5Client(login=123, password="x", server="Demo")
    # On this dev machine the MetaTrader5 package isn't installed (Windows-only).
    assert client.available() is False


def test_connect_returns_false_without_package():
    client = Mt5Client(login=123, password="x", server="Demo")
    assert client.connect() is False
    assert client.is_connected() is False


def test_account_info_raises_clear_error_without_connection():
    client = Mt5Client(login=123, password="x", server="Demo")
    with pytest.raises(Mt5ConnectionError):
        client.account_info()


def test_send_order_raises_clear_error_without_connection():
    client = Mt5Client(login=123, password="x", server="Demo")
    with pytest.raises(Mt5ConnectionError):
        client.send_order("EURUSD", "long", 0.1)


def test_connect_false_when_credentials_missing():
    # Even hypothetically with the package present, missing credentials must
    # not attempt a connection.
    client = Mt5Client(login=0, password="", server="")
    assert client.connect() is False


# ── Flask app: shared-secret auth gate ──


@pytest.fixture
def app_client(monkeypatch):
    monkeypatch.setenv("MT5_BRIDGE_API_KEY", "test-bridge-key")
    # config is a frozen dataclass read at import time; reload so the env
    # var above takes effect for this test's import of mt5_bridge.
    import importlib
    import config as bridge_config_module
    importlib.reload(bridge_config_module)
    import mt5_bridge
    importlib.reload(mt5_bridge)
    mt5_bridge.app.config["TESTING"] = True
    return mt5_bridge.app.test_client()


def test_root_and_health_need_no_key(app_client):
    assert app_client.get("/").status_code == 200
    assert app_client.get("/health").status_code == 200


def test_protected_endpoint_rejects_missing_key(app_client):
    resp = app_client.get("/account")
    assert resp.status_code == 401


def test_protected_endpoint_rejects_wrong_key(app_client):
    resp = app_client.get("/account", headers={"X-Bridge-Key": "wrong"})
    assert resp.status_code == 401


def test_protected_endpoint_accepts_correct_key_but_mt5_not_connected(app_client):
    # Correct key passes the auth gate; then it fails honestly (503) because
    # no real terminal is connected on this machine, never a fake success.
    resp = app_client.get("/account", headers={"X-Bridge-Key": "test-bridge-key"})
    assert resp.status_code == 503
    assert "error" in resp.get_json()
