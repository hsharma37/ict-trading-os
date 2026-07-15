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


def test_auto_note_generated():
    j.record_closed([_closed("1", "XAUUSD", 71.8, r=2.0)])
    t = j.list_trades()[0]
    assert t.get("note")
    assert "XAUUSD" in t["note"]
    assert "win" in t["note"].lower()
    assert "2.0R" in t["note"] or "+2.00R" in t["note"]


def test_manual_set_risk_by_sl(monkeypatch):
    # No broker specs in tests -> uses the rough fallback; R sign/magnitude sane.
    j.record_closed([{"ticket": "50", "symbol": "EURUSD", "side": "BUY", "direction": "long",
                      "lot_size": 0.1, "open_price": 1.1000, "close_price": 1.1050,
                      "realized_pnl": 50.0, "r": None, "closed_at": "2026-07-15T05:00:00"}])
    out = j.set_risk("50", sl=1.0950)  # 50-pip stop
    assert out.get("r") is not None
    assert out["r"] > 0  # winning trade -> positive R
    assert out["sl"] == 1.0950


def test_sync_mirrors_mt5_and_prunes_stale(monkeypatch):
    # Journal starts with a broker row MT5 no longer reports, plus a manual one.
    j.record_closed([_closed("OLD", "XAUUSD", 40.0)])
    j.record_closed([{"ticket": "MANUAL", "symbol": "EURUSD", "side": "BUY", "direction": "long",
                      "lot_size": 0.1, "open_price": 1.1, "close_price": 1.11,
                      "realized_pnl": 10.0, "closed_at": "2026-07-15T02:00:00", "source": "manual"}])

    from app.services import mt5_trades_service as mod
    fresh = [_closed("A", "XAUUSD", 50.0), _closed("B", "EURUSD", -20.0)]
    monkeypatch.setattr(mod.mt5_trades_service, "is_active", lambda: True)
    monkeypatch.setattr(mod.mt5_trades_service, "fetch_history", lambda: fresh)
    monkeypatch.setattr(mod.mt5_trades_service, "_normalize_closed", lambda t: t)

    res = j.sync_from_mt5()
    assert res["ok"] and res["added"] == 2 and res["removed"] == 1  # OLD pruned, MANUAL kept
    tickets = {t["ticket"] for t in j.list_trades()}
    assert tickets == {"A", "B", "MANUAL"}  # exact mirror of MT5 + manual entry


def test_sync_never_prunes_on_empty_fetch(monkeypatch):
    j.record_closed([_closed("A", "XAUUSD", 50.0)])
    from app.services import mt5_trades_service as mod
    monkeypatch.setattr(mod.mt5_trades_service, "is_active", lambda: True)
    monkeypatch.setattr(mod.mt5_trades_service, "fetch_history", lambda: [])  # bridge blip
    monkeypatch.setattr(mod.mt5_trades_service, "_normalize_closed", lambda t: t)
    res = j.sync_from_mt5()
    assert res["removed"] == 0 and len(j.list_trades()) == 1  # durable record survives


def test_manual_set_risk_direct():
    j.record_closed([{"ticket": "51", "symbol": "XAUUSD", "side": "SELL", "direction": "short",
                      "lot_size": 0.1, "open_price": 4000, "close_price": 3990,
                      "realized_pnl": 100.0, "r": None, "closed_at": "2026-07-15T05:00:00"}])
    out = j.set_risk("51", r=2.5)
    assert out["r"] == 2.5
    assert "2.5" in out["note"] or "2.50" in out["note"]
