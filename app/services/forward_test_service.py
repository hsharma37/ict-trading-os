"""Live paper-forward test — the real out-of-sample proof.

A backtest (even a walk-forward one) is still measured on data that already
existed. A forward test commits to a LOCKED config now, then only counts signals
that fire on candles printed AFTER you started. Nothing about the future can be
curve-fit. This service persists each forward test and recomputes it from the
broker's candles on demand (and on the planner tick), so trades accrue as new
bars close — no execution, pure paper.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import db
from app.services.market_data import market_service, history_is_synthetic
from app.services import backtest_service as bt

_COLL = "forward_tests"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _range_for(timeframe: str) -> str:
    # Enough lookback to cover a multi-week/month forward test plus the pattern
    # window; only trades after start_candle_time are counted.
    return {"1d": "2y"}.get(timeframe, "6mo")


_TF_SECONDS = {"5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}


def _fetch_limit(test) -> int:
    """Bars needed to recompute THIS test: bars elapsed since its start plus the
    scan window — not a blanket 5000. Each 5000-bar pull through the tunnel takes
    seconds; recomputing several tests per page load timed out the serverless
    function (the 'forward test error'). Bounded fetches fix it."""
    tf_sec = _TF_SECONDS.get(test.get("timeframe", "1h"), 3600)
    start = test.get("start_candle_time") or 0
    elapsed = datetime.now(timezone.utc).timestamp() - start if start else 0
    elapsed_bars = int(max(0.0, elapsed) / tf_sec)
    return min(3000, max(300, elapsed_bars + 150))


class ForwardTestService:
    def create(self, symbol: str, timeframe: str = "1h", target_r: float = 3.0,
               session_filter: bool = False, trend_filter: bool = False,
               min_confluence: int = 2, label: str = "",
               strategy: str = "ict_confluence") -> Dict[str, Any]:
        symbol = symbol.upper()
        candles = market_service.get_history(symbol, timeframe, 200, history_range=_range_for(timeframe))
        if not candles or history_is_synthetic(candles):
            return {"error": "Market data unavailable right now — try again when the feed is live."}
        start_time = candles[-1].get("time")
        test = {
            "id": uuid.uuid4().hex[:12],
            "label": label or f"{symbol} {strategy if strategy != 'ict_confluence' else 'ICT'} {target_r}R"
                     + (" KZ" if session_filter else "") + (" trend" if trend_filter else ""),
            "strategy": strategy,
            "symbol": symbol, "timeframe": timeframe, "target_r": target_r,
            "session_filter": session_filter, "trend_filter": trend_filter, "min_confluence": min_confluence,
            "start_candle_time": start_time, "started_at": _now(), "status": "running",
            "trades": [], "open_trade": None, "summary": {}, "last_checked": _now(),
        }
        db.insert(_COLL, test)
        return self._recompute(test)

    def _recompute(self, test: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministically rebuild the forward test's trades from current candles
        (idempotent — same candles → same trades, and new bars extend the list)."""
        if test.get("status") != "running":
            return test
        symbol, tf = test["symbol"], test.get("timeframe", "1h")
        candles = market_service.get_history(symbol, tf, _fetch_limit(test), history_range=_range_for(tf))
        if not candles or history_is_synthetic(candles):
            return test  # keep last-known; don't wipe on a feed blip
        strat = test.get("strategy") or "ict_confluence"
        if strat == "ict_confluence":
            signals = bt._scan_signals(candles, symbol, tf, 100, test.get("min_confluence", 2))
        else:
            # Strategy Lab forward test — same signal generator + 1.5×ATR stop
            # as the backtest, so forward results are comparable to it.
            from app.services.strategy_service import signals_for
            signals = signals_for(candles, strat)
        cost_price = bt._round_trip_cost_price(symbol)  # net-of-cost, like the backtest
        all_trades = bt._evaluate(candles, signals, test["target_r"], 8, 48,
                                  test.get("session_filter", False), test.get("trend_filter", False), cost_price)
        start = test.get("start_candle_time") or 0
        fwd = [t for t in all_trades if (t.get("entry_time") or 0) > start]
        closed = [t for t in fwd if not t.get("open")]
        open_t = next((t for t in fwd if t.get("open")), None)
        summary = bt._summarize_backtest(symbol, tf, test["target_r"], "forward", len(candles), closed)
        patch = {
            "trades": [{"r": t["r"], "dir": t["dir"], "entry": t["entry"],
                        "entry_time": t.get("entry_time"), "exit_time": t.get("exit_time")} for t in closed],
            "open_trade": ({"dir": open_t["dir"], "entry": open_t["entry"], "sl": open_t["sl"],
                            "target": open_t["target"], "entry_time": open_t.get("entry_time"),
                            "unrealized_r": open_t["r"]} if open_t else None),
            "summary": summary, "last_checked": _now(),
            "latest_candle_time": candles[-1].get("time"),
        }
        db.update(_COLL, test["id"], patch)
        return {**test, **patch}

    def tick_all(self) -> Dict[str, Any]:
        """Advance every running forward test (called on the planner tick). Cheap:
        skips a test whose newest candle hasn't changed since last check."""
        updated = 0
        for test in db.get_collection(_COLL):
            if test.get("status") != "running":
                continue
            try:
                symbol, tf = test["symbol"], test.get("timeframe", "1h")
                probe = market_service.get_history(symbol, tf, 2, history_range=_range_for(tf))
                if not probe:
                    continue
                if probe[-1].get("time") == test.get("latest_candle_time"):
                    continue  # no new bar → nothing to do
                self._recompute(test)
                updated += 1
            except Exception:
                continue
        return {"updated": updated}

    def list(self, recompute: bool = True) -> List[Dict[str, Any]]:
        rows = db.get_collection(_COLL)
        if recompute:
            rows = [self._recompute(r) if r.get("status") == "running" else r for r in rows]
        rows.sort(key=lambda r: r.get("started_at", ""), reverse=True)
        return rows

    def get(self, test_id: str) -> Optional[Dict[str, Any]]:
        t = db.find_one(_COLL, test_id)
        return self._recompute(t) if t and t.get("status") == "running" else t

    def stop(self, test_id: str) -> Dict[str, Any]:
        t = db.find_one(_COLL, test_id)
        if not t:
            return {"error": "Not found"}
        db.update(_COLL, test_id, {"status": "stopped", "stopped_at": _now()})
        return {"ok": True, "id": test_id, "status": "stopped"}

    def delete(self, test_id: str) -> Dict[str, Any]:
        db.delete(_COLL, test_id)
        return {"ok": True, "id": test_id, "deleted": True}


forward_test_service = ForwardTestService()
