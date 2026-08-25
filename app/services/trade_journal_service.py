"""Durable trade journal — every closed MT5 trade, persisted per instrument.

The broker's closed-deal ledger is a rolling ~30-day window and vanishes when the
bridge is offline. This service snapshots each closed trade into a durable
Postgres collection (deduped by ticket) as it's seen, so:
  • analytics/dashboard stay correct and keep updating after every close,
  • history survives bridge blips and grows beyond the 30-day window,
  • you can pull up a particular instrument's trades with a summary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import db

_COLL = "trade_journal"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TradeJournalService:
    def record_closed(self, closed: List[Dict[str, Any]]) -> int:
        """Upsert normalized closed trades (from mt5_trades_service). Returns the
        number of newly-journaled trades."""
        added = 0
        for t in closed:
            ticket = str(t.get("ticket") or t.get("id") or "")
            if not ticket:
                continue
            existing = db.find_one(_COLL, ticket)
            profit_val = t.get("realized_pnl", t.get("profit", 0))
            from app.services.mt5_trades_service import normalized_profit
            entry = {
                "id": ticket,
                "ticket": ticket,
                "symbol": t.get("symbol"),
                "side": t.get("side"),
                "direction": t.get("direction"),
                "lot_size": t.get("lot_size"),
                "open_price": t.get("open_price"),
                "close_price": t.get("close_price"),
                "sl": t.get("sl"),
                "tp": t.get("tp"),
                "profit": profit_val,
                # P&L rescaled to the instrument's standard lot (size-normalized).
                "profit_norm": t.get("profit_norm", normalized_profit(t.get("symbol"), profit_val, t.get("lot_size"))),
                "r": t.get("r"),
                "risk_money": t.get("risk_money"),
                "closed_at": t.get("closed_at") or t.get("created_at"),
                "source": t.get("source", "mt5"),
            }
            entry["note"] = self._auto_note(entry)  # auto-journal each trade
            if existing:
                patch = {}
                # Refresh R/risk/SL from the (now correct) computation — this also
                # overwrites the old garbage values from the buggy risk method.
                for k in ("r", "risk_money", "sl", "tp", "profit_norm"):
                    if entry.get(k) is not None and existing.get(k) != entry.get(k):
                        patch[k] = entry[k]
                if patch or not existing.get("note"):
                    patch["note"] = self._auto_note({**existing, **patch})
                    db.update(_COLL, ticket, patch)
                continue
            entry["journaled_at"] = _now()
            db.insert(_COLL, entry)
            added += 1
        return added

    @staticmethod
    def _auto_note(e: Dict[str, Any]) -> str:
        """Deterministic auto-journal commentary for a closed trade."""
        sym = e.get("symbol", "?")
        side = e.get("side") or ("BUY" if e.get("direction") == "long" else "SELL")
        profit = float(e.get("profit") or 0)
        r = e.get("r")
        outcome = "win" if profit > 0 else "loss" if profit < 0 else "scratch"
        move = f"{e.get('open_price')}→{e.get('close_price')}"
        rtxt = f", {r:+.2f}R" if r is not None else ""
        head = f"{sym} {side} {e.get('lot_size')} lots {move}: {profit:+.2f}{rtxt} ({outcome})."
        if r is not None and r >= 2:
            takeaway = "Strong winner (≥2R) — the plan worked; keep letting winners run to target."
        elif r is not None and r <= -1:
            takeaway = "Full stop taken — review entry timing/confluence; risk was contained to plan."
        elif profit > 0:
            takeaway = "Profit booked before full target — fine if it was managed, but check if it ran further."
        elif profit < 0:
            takeaway = "Small loss — acceptable if it followed the plan; avoid revenge trading."
        else:
            takeaway = "Scratch — break-even exit."
        return f"{head} {takeaway}"

    def set_risk(self, ticket: str, sl: Optional[float] = None, r: Optional[float] = None) -> Dict[str, Any]:
        """Manually fill R for a journaled trade — either by giving the stop-loss
        (R is computed from it) or R directly. Regenerates the auto-note."""
        entry = db.find_one(_COLL, str(ticket))
        if not entry:
            return {"error": "Trade not found"}
        profit = float(entry.get("profit") or 0)
        risk_money = entry.get("risk_money")
        if sl:
            try:
                dist = abs(float(entry["open_price"]) - float(sl))
                lot = float(entry.get("lot_size") or 0)
                if dist > 0 and lot > 0:
                    from app.services.broker_specs import money_per_lot
                    mpl = money_per_lot(entry.get("symbol", ""), dist)
                    risk_money = round((mpl or (dist * 100000 / 1.0)) * lot, 2)  # broker rate, else rough
                    r = round(profit / risk_money, 2) if risk_money else None
                    entry["sl"] = float(sl)
            except (TypeError, ValueError, ZeroDivisionError):
                return {"error": "Could not compute R from that stop-loss"}
        if r is None:
            return {"error": "Provide a stop-loss (to compute R) or an R value."}
        patch = {"r": r, "risk_money": risk_money, "sl": entry.get("sl")}
        patch["note"] = self._auto_note({**entry, **patch})
        db.update(_COLL, str(ticket), patch)
        return db.find_one(_COLL, str(ticket))

    def sync_from_mt5(self) -> Dict[str, Any]:
        """Mirror the broker's closed-trade history into the journal: upsert every
        current MT5 close, then prune stale broker-sourced rows so the journal is
        an exact reflection of the terminal (same trade count, same totals).

        Safe to call repeatedly / on a schedule. Pruning only runs when MT5 is
        connected and returned a non-empty history, so a bridge blip never wipes
        the durable record. Manually-entered rows (source != "mt5") are never
        pruned."""
        try:
            from app.services.mt5_trades_service import mt5_trades_service
            if not mt5_trades_service.is_active():
                return {"ok": False, "reason": "MT5 not connected", "added": 0}
            closed = [mt5_trades_service._normalize_closed(t) for t in mt5_trades_service.fetch_history()]
            added = self.record_closed(closed)
            removed = self._reconcile(closed)
            return {
                "ok": True, "fetched": len(closed), "added": added,
                "removed": removed, "total": len(self.list_trades(limit=100000)),
            }
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "reason": str(e), "added": 0}

    def _reconcile(self, closed: List[Dict[str, Any]]) -> int:
        """Drop broker-sourced journal rows that MT5 no longer reports, so the
        journal stays a 1:1 mirror of the terminal's history. No-op on an empty
        fetch (treated as an unreliable snapshot, not "all trades gone")."""
        if not closed:
            return 0
        live = {str(t.get("ticket") or t.get("id") or "") for t in closed}
        removed = 0
        for r in db.get_collection(_COLL):
            if (r.get("source") or "mt5") not in ("mt5", "ctrader"):
                continue  # never prune manual entries
            tid = str(r.get("id") or r.get("ticket") or "")
            if tid and tid not in live:
                db.delete(_COLL, tid)
                removed += 1
        return removed

    def list_trades(self, symbol: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        rows = db.get_collection(_COLL)
        if symbol:
            s = symbol.upper()
            rows = [r for r in rows if (r.get("symbol") or "").upper() == s]
        rows.sort(key=lambda r: r.get("closed_at") or "", reverse=True)
        return rows[:limit]

    def symbols(self) -> List[Dict[str, Any]]:
        """Instruments present in the journal, each with a count + net P&L."""
        agg: Dict[str, Dict[str, Any]] = {}
        for r in db.get_collection(_COLL):
            sym = (r.get("symbol") or "?").upper()
            a = agg.setdefault(sym, {"symbol": sym, "trades": 0, "total_pnl": 0.0})
            a["trades"] += 1
            a["total_pnl"] += float(r.get("profit") or 0)
        out = list(agg.values())
        for a in out:
            a["total_pnl"] = round(a["total_pnl"], 2)
        return sorted(out, key=lambda a: a["trades"], reverse=True)

    def summary(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Per-instrument (or overall) closed-trade summary."""
        rows = self.list_trades(symbol, limit=100000)
        return self._summarize(rows, symbol)

    @staticmethod
    def _norm(r: Dict[str, Any]) -> float:
        """A row's size-normalized P&L (per standard lot). Uses the stored value
        when present, else computes it on the fly so rows journaled before the
        field existed still normalize correctly."""
        if r.get("profit_norm") is not None:
            return float(r["profit_norm"])
        from app.services.mt5_trades_service import normalized_profit
        return normalized_profit(r.get("symbol"), r.get("profit") or 0, r.get("lot_size"))

    def _summarize(self, rows: List[Dict[str, Any]], symbol: Optional[str]) -> Dict[str, Any]:
        n = len(rows)
        pnls = [float(r.get("profit") or 0) for r in rows]        # raw actual money
        norms = [self._norm(r) for r in rows]                     # per standard lot
        win_norms = [nm for nm, raw in zip(norms, pnls) if raw > 0]
        loss_norms = [nm for nm, raw in zip(norms, pnls) if raw <= 0]
        n_win = sum(1 for p in pnls if p > 0)
        n_loss = n - n_win
        r_vals = [float(r["r"]) for r in rows if r.get("r") is not None]
        total_pnl = round(sum(pnls), 2)
        return {
            "symbol": symbol.upper() if symbol else "ALL",
            "closed_trades": n,
            "winning_trades": n_win,
            "losing_trades": n_loss,
            "win_rate": round(n_win / n * 100, 1) if n else 0,
            "total_pnl": total_pnl,                                # raw actual money
            # Per-trade money stats below are size-normalized (per standard lot).
            "avg_pnl": round(sum(norms) / n, 2) if n else 0,
            "avg_win": round(sum(win_norms) / len(win_norms), 2) if win_norms else 0,
            "avg_loss": round(sum(loss_norms) / len(loss_norms), 2) if loss_norms else 0,
            "best_trade": round(max(norms), 2) if norms else 0,
            "worst_trade": round(min(norms), 2) if norms else 0,
            "total_r": round(sum(r_vals), 2) if r_vals else 0,
            "avg_r": round(sum(r_vals) / len(r_vals), 2) if r_vals else 0,
            "r_tracked_trades": len(r_vals),
            "stats_basis": "per_standard_lot",
        }

    def stats(self) -> Dict[str, Any]:
        """Full stats dict (same shape as get_trade_stats) from the journal — used
        as the analytics fallback when MT5 is offline, so real closed trades show
        instead of the synthetic ledger."""
        rows = self.list_trades(limit=100000)
        if not rows:
            return {}
        s = self._summarize(rows, None)
        by_symbol: Dict[str, Any] = {}
        for r in rows:
            sym = (r.get("symbol") or "?").upper()
            b = by_symbol.setdefault(sym, {"trades": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "norm_pnl": 0.0, "best": 0, "worst": 0})
            pnl = float(r.get("profit") or 0)
            pn = self._norm(r)
            b["trades"] += 1
            b["wins" if pnl > 0 else "losses"] += 1
            b["total_pnl"] += pnl        # raw actual money
            b["norm_pnl"] += pn          # normalized (per standard lot)
            b["best"] = max(b["best"], pn)
            b["worst"] = min(b["worst"], pn)
        for b in by_symbol.values():
            b["win_rate"] = round(b["wins"] / b["trades"] * 100, 1) if b["trades"] else 0
            b["avg_pnl"] = round(b["norm_pnl"] / b["trades"], 2) if b["trades"] else 0  # per standard lot
            b["total_pnl"] = round(b["total_pnl"], 2)
            b["norm_pnl"] = round(b["norm_pnl"], 2)
            b["best"] = round(b["best"], 2)
            b["worst"] = round(b["worst"], 2)
        return {
            "total_trades": s["closed_trades"], "open_trades": 0,
            "closed_trades": s["closed_trades"],
            "winning_trades": s["winning_trades"], "losing_trades": s["losing_trades"],
            "win_rate": s["win_rate"], "total_pnl": s["total_pnl"],
            "realized_pnl": s["total_pnl"], "unrealized_pnl": 0,
            "avg_pnl": s["avg_pnl"], "avg_win": s["avg_win"], "avg_loss": s["avg_loss"],
            "expectancy": round((s["win_rate"] / 100 * s["avg_win"]) + ((1 - s["win_rate"] / 100) * s["avg_loss"]), 2),
            "best_trade": s["best_trade"], "worst_trade": s["worst_trade"],
            "avg_r": s["avg_r"], "total_r": s["total_r"], "best_r": 0, "worst_r": 0,
            "r_tracked_trades": s["r_tracked_trades"],
            "max_win_streak": 0, "max_loss_streak": 0, "current_streak": 0,
            "max_drawdown": 0, "max_drawdown_duration": 0, "equity_curve": [],
            "by_symbol": by_symbol, "monthly": {}, "sessions": {},
            "stats_basis": "per_standard_lot",
            "source": "journal",
        }


trade_journal_service = TradeJournalService()
