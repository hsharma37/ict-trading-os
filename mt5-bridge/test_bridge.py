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

from mt5_client import Mt5Client, Mt5ConnectionError, normalize_position, pair_deals_into_trades


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


# ── Field-name translation: MT5's raw shape -> the frontend's contract ──
#
# MetaTrader5's positions_get()/history_deals_get() return their own field
# names (volume, price_open, price_current, type as 0/1 ...), not what the
# frontend expects (lot_size, open_price, current_price, direction as a
# string). Confirmed live: a real open position made the MT5 Terminal page
# crash on every 5s poll with "Cannot read properties of undefined (reading
# 'toUpperCase')" -- pos.direction was always undefined -- which looked like
# the page repeatedly reloading.

# A real open position's raw shape, captured live from the deployed bridge.
_RAW_POSITION = {
    "ticket": 9557569537, "symbol": "XAUUSD", "type": 1, "volume": 0.1,
    "price_open": 4085.44, "price_current": 4078.58, "sl": 4096.0, "tp": 4065.0,
    "profit": 68.6, "swap": 0.0, "time": 1784047133,
}


def test_normalize_position_maps_mt5_fields_to_frontend_contract():
    out = normalize_position(_RAW_POSITION)
    assert out == {
        "ticket": "9557569537",
        "symbol": "XAUUSD",
        "direction": "short",  # type=1 (SELL) -> "short", not the raw int
        "lot_size": 0.1,
        "open_price": 4085.44,
        "current_price": 4078.58,
        "sl": 4096.0,
        "tp": 4065.0,
        "profit": 68.6,
        "swap": 0.0,
    }


def test_normalize_position_buy_type_maps_to_long():
    out = normalize_position({**_RAW_POSITION, "type": 0})
    assert out["direction"] == "long"


def test_positions_returns_frontend_shaped_dicts_not_raw_mt5_fields(connected_client):
    """End-to-end: Mt5Client.positions() must never leak raw MT5 field names
    (volume, price_open, type as int) -- exactly what crashed the live page."""
    client, fake = connected_client
    fake.positions_result = (_FakeResult(**_RAW_POSITION),)
    positions = client.positions()
    assert len(positions) == 1
    assert positions[0]["direction"] == "short"
    assert positions[0]["lot_size"] == 0.1
    assert "volume" not in positions[0]
    assert "price_open" not in positions[0]


def test_pair_deals_into_trades_reconstructs_open_close_pair():
    """MT5's history is a deal ledger (separate open + close deals sharing a
    position_id), not a trade ledger -- these must be paired into the single
    open/close record the frontend's MT5HistoryTrade expects."""
    deals = [
        {  # opening deal
            "position_id": 555, "entry": 0, "type": 1, "symbol": "XAUUSD",
            "volume": 0.1, "price": 4085.44, "profit": 0.0, "time": 1784047133,
        },
        {  # closing deal
            "position_id": 555, "entry": 1, "type": 0, "symbol": "XAUUSD",
            "volume": 0.1, "price": 4070.0, "profit": 154.4, "time": 1784050000,
        },
    ]
    trades = pair_deals_into_trades(deals)
    assert len(trades) == 1
    t = trades[0]
    assert t["ticket"] == "555"
    assert t["symbol"] == "XAUUSD"
    assert t["direction"] == "short"  # from the opening deal's type
    assert t["open_price"] == 4085.44
    assert t["close_price"] == 4070.0
    assert t["profit"] == 154.4
    assert t["closed_at"]


def test_pair_deals_into_trades_omits_still_open_positions():
    """A position with only an entry deal (no exit yet) must not appear as a
    'closed trade' -- it's still open."""
    deals = [{
        "position_id": 999, "entry": 0, "type": 0, "symbol": "EURUSD",
        "volume": 0.5, "price": 1.09, "profit": 0.0, "time": 1784047133,
    }]
    assert pair_deals_into_trades(deals) == []


def test_pair_deals_into_trades_ignores_non_trade_deal_types():
    """Balance/credit ledger entries (deal type >= 2) must not be mistaken
    for a buy/sell leg."""
    deals = [{
        "position_id": 1, "entry": 0, "type": 2, "symbol": "", "volume": 0,
        "price": 0, "profit": 1000.0, "time": 1784047133,
    }]
    assert pair_deals_into_trades(deals) == []


def test_history_deals_returns_paired_trades_not_raw_deal_records(connected_client):
    client, fake = connected_client
    fake.history_deals_get = lambda since, until: (
        _FakeResult(position_id=1, entry=0, type=1, symbol="XAUUSD", volume=0.1, price=100.0, profit=0.0, time=1),
        _FakeResult(position_id=1, entry=1, type=0, symbol="XAUUSD", volume=0.1, price=110.0, profit=1000.0, time=2),
    )
    trades = client.history_deals()
    assert len(trades) == 1
    assert trades[0]["direction"] == "short"
    assert trades[0]["close_price"] == 110.0


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
