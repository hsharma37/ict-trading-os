"""Durable trade journal: record, filter by symbol, summarize, dedup."""
from app.services.trade_journal_service import trade_journal_service as j


def _closed(ticket, symbol, profit, r=None, side="SELL"):
    return {"ticket": ticket, "symbol": symbol, "side": side, "direction": "short" if side == "SELL" else "long",
            "lot_size": 0.1, "open_price": 1.1, "close_price": 1.09, "realized_pnl": profit,
            "r": r, "risk_money": 20, "closed_at": f"2026-07-15T0{ticket}:00:00", "source": "mt5"}


def test_record_and_dedup():
    trades = [_closed("1", "XAUUSD", 50.0, r=2.0), _closed("2", "EURUSD", -20.0, r=-1.0)]
    assert j.record_closed(trades) == 2
    assert j.record_closed(trades) == 0  # dedup by ticket
    assert len(j.list_trades()) == 2


def test_filter_by_symbol():
    j.record_closed([_closed("1", "XAUUSD", 50.0), _closed("2", "EURUSD", -20.0), _closed("3", "XAUUSD", 30.0)])
    xau = j.list_trades(symbol="XAUUSD")
    assert len(xau) == 2
    assert all(t["symbol"] == "XAUUSD" for t in xau)


def test_per_instrument_summary():
    j.record_closed([_closed("1", "XAUUSD", 50.0, r=2.0), _closed("2", "XAUUSD", -25.0, r=-1.0), _closed("3", "EURUSD", 10.0)])
    s = j.summary("XAUUSD")
    assert s["symbol"] == "XAUUSD"
    assert s["closed_trades"] == 2
    assert s["win_rate"] == 50.0
    assert s["total_pnl"] == 25.0
    assert s["total_r"] == 1.0  # 2.0 + (-1.0)


def test_symbols_index():
    j.record_closed([_closed("1", "XAUUSD", 50.0), _closed("2", "EURUSD", -20.0), _closed("3", "XAUUSD", 30.0)])
    syms = {s["symbol"]: s for s in j.symbols()}
    assert syms["XAUUSD"]["trades"] == 2
    assert syms["XAUUSD"]["total_pnl"] == 80.0


def test_stats_fallback_shape():
    j.record_closed([_closed("1", "XAUUSD", 50.0, r=2.0), _closed("2", "EURUSD", -20.0)])
    st = j.stats()
    assert st["source"] == "journal"
    assert st["closed_trades"] == 2
    assert st["total_pnl"] == 30.0
    assert st["r_tracked_trades"] == 1


def test_backfills_r_on_later_sighting():
    j.record_closed([_closed("9", "XAUUSD", 70.0, r=None)])
    assert j.list_trades()[0]["r"] is None
    j.record_closed([_closed("9", "XAUUSD", 70.0, r=2.0)])  # risk captured later
    assert j.list_trades()[0]["r"] == 2.0
