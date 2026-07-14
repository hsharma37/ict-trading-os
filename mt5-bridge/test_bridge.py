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

from mt5_client import Mt5Client, Mt5ConnectionError, normalize_position, pair_deals_into_trades, normalize_tick


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
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TYPE_BUY_STOP = 4
    ORDER_TYPE_SELL_STOP = 5
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    TRADE_ACTION_SLTP = 2
    TRADE_ACTION_REMOVE = 4
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_M30 = 30
    TIMEFRAME_H1 = 16385
    TIMEFRAME_H4 = 16388
    TIMEFRAME_D1 = 16408
    TIMEFRAME_W1 = 32769

    def __init__(self):
        self.initialize_result = True
        self.positions_result = ()  # empty tuple = legitimately zero positions
        self.account_info_result = _FakeResult(balance=10000.0, equity=10000.0)
        self.initialize_calls = 0
        self.last_order_request = None
        # Market-data fixtures
        self.tick_result = _FakeResult(bid=1.1000, ask=1.1002, last=1.1001, volume=5, time=1784047133)
        self.symbol_info_result = _FakeResult(visible=True, digits=5, point=0.00001, spread=2,
                                              trade_contract_size=100000, volume_min=0.01,
                                              volume_max=100.0, volume_step=0.01,
                                              currency_base="EUR", currency_profit="USD", trade_mode=4)
        self.rates_result = [
            {"time": 1784047000, "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105, "tick_volume": 100},
            {"time": 1784047600, "open": 1.105, "high": 1.12, "low": 1.10, "close": 1.115, "tick_volume": 120},
        ]
        self.symbols_result = (_FakeResult(name="EURUSD"), _FakeResult(name="XAUUSD"))
        self.orders_result = ()

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

    def symbol_info(self, symbol):
        return self.symbol_info_result

    def symbol_select(self, symbol, enable):
        return True

    def symbol_info_tick(self, symbol):
        return self.tick_result

    def copy_rates_from_pos(self, symbol, tf, start, count):
        return self.rates_result

    def symbols_get(self):
        return self.symbols_result

    def orders_get(self):
        return self.orders_result

    def order_send(self, request):
        self.last_order_request = request
        return _FakeResult(retcode=10009, order=12345, comment="Done")

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


def test_close_without_matching_open_still_appears():
    """A close (OUT) deal whose opening deal isn't in the window must still show
    as a closed trade — the old pair-both-legs approach dropped these."""
    deals = [{"position_id": 42, "entry": 1, "type": 0, "symbol": "XAUUSD",
              "volume": 0.2, "price": 4065.0, "profit": 300.0, "time": 5}]
    trades = pair_deals_into_trades(deals)
    assert len(trades) == 1
    assert trades[0]["profit"] == 300.0
    assert trades[0]["direction"] == "short"   # closed a short with a buy
    assert trades[0]["open_price"] is None


def test_multiple_closes_all_appear_newest_first():
    deals = [
        {"position_id": 1, "entry": 1, "type": 0, "symbol": "XAUUSD", "volume": 0.1, "price": 100, "profit": 10, "time": 100},
        {"position_id": 2, "entry": 1, "type": 1, "symbol": "EURUSD", "volume": 0.2, "price": 1.1, "profit": -5, "time": 300},
        {"position_id": 3, "entry": 1, "type": 0, "symbol": "XAUUSD", "volume": 0.3, "price": 200, "profit": 50, "time": 200},
    ]
    trades = pair_deals_into_trades(deals)
    assert len(trades) == 3
    assert [t["ticket"] for t in trades] == ["2", "3", "1"]  # newest close first


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


# ── Market data ──────────────────────────────────────────────


def test_normalize_tick_computes_mid_and_spread():
    out = normalize_tick("eurusd", {"bid": 1.1000, "ask": 1.1002, "last": 1.1001, "volume": 5, "time": 1784047133})
    assert out["symbol"] == "EURUSD"
    assert out["bid"] == 1.1000 and out["ask"] == 1.1002
    assert out["price"] == round((1.1000 + 1.1002) / 2, 8)
    assert out["spread"] == round(1.1002 - 1.1000, 8)
    assert out["source"] == "mt5"


def test_get_tick_returns_normalized_price(connected_client):
    client, fake = connected_client
    out = client.get_tick("EURUSD")
    assert out["source"] == "mt5"
    assert out["price"] == round((1.1000 + 1.1002) / 2, 8)


def test_get_candles_maps_ohlc(connected_client):
    client, fake = connected_client
    candles = client.get_candles("EURUSD", "1h", 200)
    assert len(candles) == 2
    assert candles[0] == {"time": 1784047000, "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105, "volume": 100}


def test_get_candles_maps_timeframe_to_mt5_constant(connected_client):
    client, fake = connected_client
    captured = {}
    fake.copy_rates_from_pos = lambda symbol, tf, start, count: captured.update(tf=tf) or fake.rates_result
    client.get_candles("EURUSD", "4h", 10)
    assert captured["tf"] == fake.TIMEFRAME_H4


def test_symbol_spec_returns_contract_details(connected_client):
    client, fake = connected_client
    spec = client.symbol_spec("EURUSD")
    assert spec["digits"] == 5
    assert spec["contract_size"] == 100000
    assert spec["volume_min"] == 0.01


def test_list_symbols(connected_client):
    client, fake = connected_client
    assert client.list_symbols() == ["EURUSD", "XAUUSD"]


# ── Order & position management ──────────────────────────────


def test_modify_sltp_sends_sltp_action(connected_client):
    client, fake = connected_client
    fake.positions_result = (_FakeResult(**{**_RAW_POSITION, "sl": 4096.0, "tp": 4065.0}),)
    client.modify_sltp(9557569537, stop_loss=4090.0, take_profit=4060.0)
    req = fake.last_order_request
    assert req["action"] == fake.TRADE_ACTION_SLTP
    assert req["sl"] == 4090.0 and req["tp"] == 4060.0
    assert req["position"] == 9557569537


def test_partial_close_rejects_volume_over_position(connected_client):
    client, fake = connected_client
    fake.positions_result = (_FakeResult(**_RAW_POSITION),)  # volume 0.1
    with pytest.raises(Mt5ConnectionError, match="must be > 0"):
        client.partial_close(9557569537, 0.5)


def test_partial_close_sends_deal_with_partial_volume(connected_client):
    client, fake = connected_client
    fake.positions_result = (_FakeResult(**_RAW_POSITION),)  # type 1 (sell) -> close with buy
    client.partial_close(9557569537, 0.05)
    req = fake.last_order_request
    assert req["action"] == fake.TRADE_ACTION_DEAL
    assert req["volume"] == 0.05
    assert req["type"] == fake.ORDER_TYPE_BUY  # closing a short


def test_place_pending_buy_limit(connected_client):
    client, fake = connected_client
    client.place_pending("EURUSD", "long", "limit", 0.1, 1.0900, stop_loss=1.0850, take_profit=1.1000)
    req = fake.last_order_request
    assert req["action"] == fake.TRADE_ACTION_PENDING
    assert req["type"] == fake.ORDER_TYPE_BUY_LIMIT
    assert req["price"] == 1.0900 and req["sl"] == 1.0850 and req["tp"] == 1.1000


def test_place_pending_short_stop(connected_client):
    client, fake = connected_client
    client.place_pending("EURUSD", "short", "stop", 0.2, 1.0800)
    assert fake.last_order_request["type"] == fake.ORDER_TYPE_SELL_STOP


def test_place_pending_rejects_bad_kind(connected_client):
    client, fake = connected_client
    with pytest.raises(Mt5ConnectionError):
        client.place_pending("EURUSD", "long", "banana", 0.1, 1.09)


def test_cancel_pending_sends_remove_action(connected_client):
    client, fake = connected_client
    client.cancel_pending(778899)
    req = fake.last_order_request
    assert req["action"] == fake.TRADE_ACTION_REMOVE
    assert req["order"] == 778899


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
