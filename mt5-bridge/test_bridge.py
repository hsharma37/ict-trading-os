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


# ── Simulated MetaTrader5 module: IPC-failure detection + self-healing ──
#
# The real MetaTrader5 package is Windows-only and can't be installed here,
# so these tests inject a fake module in its place to exercise the exact
# failure mode this fix addresses: an IPC call returning None mid-session
# (terminal closed, PC slept, network blip) must be treated as a real error
# — not silently coerced into "zero results" — and must make the *next*
# call attempt a fresh reconnect instead of trusting a stale "connected" flag.


class _FakeResult:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def _asdict(self):
        return dict(self.__dict__)


class _FakeMt5:
    """Minimal stand-in for the MetaTrader5 module's call surface."""
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1

    def __init__(self):
        self.initialize_result = True
        self.positions_result = ()  # empty tuple = legitimately zero positions
        self.account_info_result = _FakeResult(balance=10000.0, equity=10000.0)
        self.initialize_calls = 0

    def initialize(self, **kwargs):
        self.initialize_calls += 1
        return self.initialize_result

    def last_error(self):
        return (-10001, "IPC send failed")

    def account_info(self):
        return self.account_info_result

    def positions_get(self, ticket=None):
        return self.positions_result

    def history_deals_get(self, since, until):
        return ()

    def shutdown(self):
        pass


@pytest.fixture
def connected_client(monkeypatch):
    """An Mt5Client wired to a fake, already-connected MT5 module."""
    import mt5_client as mt5_client_module
    fake = _FakeMt5()
    monkeypatch.setattr(mt5_client_module, "mt5", fake)
    monkeypatch.setattr(mt5_client_module, "_MT5_AVAILABLE", True)
    client = Mt5Client(login=109634769, password="x", server="MetaQuotes-Demo")
    assert client.connect() is True
    return client, fake


def test_positions_get_none_raises_not_silently_empty(connected_client):
    """positions_get() -> None means the call failed. Before this fix, `if
    positions else []` treated None the same as a real empty tuple, so a
    dropped IPC connection silently looked like 'zero open positions'."""
    client, fake = connected_client
    fake.positions_result = None
    with pytest.raises(Mt5ConnectionError, match="IPC send failed"):
        client.positions()


def test_positions_get_empty_tuple_is_a_real_empty_list(connected_client):
    """Genuinely zero positions must still work normally (not raise)."""
    client, fake = connected_client
    fake.positions_result = ()
    assert client.positions() == []


def test_account_info_none_marks_disconnected_for_self_healing(connected_client):
    """account_info() -> None (IPC failure) mid-session must flip is_connected()
    back to False, so the bridge doesn't keep reporting a stale 'connected'
    status while every real call keeps failing until a manual restart."""
    client, fake = connected_client
    fake.account_info_result = None

    assert client.is_connected() is True
    with pytest.raises(Mt5ConnectionError):
        client.account_info()
    assert client.is_connected() is False


def test_reconnect_attempted_automatically_after_ipc_failure(connected_client):
    """After a mid-session failure, the *next* call must attempt a fresh
    mt5.initialize() instead of trusting the stale connected flag forever."""
    client, fake = connected_client
    calls_before = fake.initialize_calls

    fake.account_info_result = None
    with pytest.raises(Mt5ConnectionError):
        client.account_info()

    # Connection recovers (e.g. terminal reachable again); next call succeeds.
    fake.account_info_result = _FakeResult(balance=10000.0, equity=10000.0)
    info = client.account_info()
    assert info["balance"] == 10000.0
    assert fake.initialize_calls == calls_before + 1  # one fresh reconnect attempt


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
