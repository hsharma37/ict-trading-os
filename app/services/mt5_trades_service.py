"""MT5 as the source of truth for trades data.

When the MT5 bridge is reachable and the terminal is connected, this service
becomes the base for everything trade-related — Dashboard KPIs, Analytics, and
the knowledge chatbot's live-account awareness — by pulling real open positions
+ closed history + account from the broker and reshaping them into the SAME
stats schema the synthetic ledger produces (``trade_lifecycle_service
.get_trade_stats``). That lets the existing consumers switch over with no schema
churn; when the bridge is down, callers fall back to the synthetic ledger.

Broker data has no per-trade risk (SL/TP) on the closed-deal ledger, so R-based
metrics are reported as 0 (not fabricated). P&L is the broker's realized/float
profit, so displayed numbers match the terminal exactly.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import httpx

from app.services.bridge_config import get_bridge_url, get_bridge_api_key

# Short caches: Dashboard/Analytics poll frequently; the bridge shouldn't be hit
# on every call. Connectivity is cached separately (and for longer) so a down
# bridge doesn't cost a network timeout on every stats request.
_DATA_TTL = 4.0
_CONN_TTL = 10.0

_STARTING_EQUITY_FALLBACK = 10000.0


def _monotonic() -> float:
    return time.monotonic()


class Mt5TradesService:
    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}
        self._cache_at: Dict[str, float] = {}
        self._active: Optional[bool] = None
        self._active_at: float = 0.0

    # ── low-level bridge access ──────────────────────────────────────

    def _headers(self) -> dict:
        h = {"ngrok-skip-browser-warning": "true"}
        key = get_bridge_api_key()
        if key:
            h["X-Bridge-Key"] = key
        return h

    def _configured(self) -> bool:
        """Is a real (remote) bridge URL set? A localhost default means the app
        isn't pointed at a broker bridge — stay on the synthetic ledger and never
        touch the network (keeps tests offline)."""
        url = get_bridge_url()
        if not url:
            return False
        low = url.lower()
        return "localhost" not in low and "127.0.0.1" not in low

    def _get(self, path: str, timeout: float = 8.0) -> Optional[Any]:
        try:
            resp = httpx.get(f"{get_bridge_url()}{path}", headers=self._headers(), timeout=timeout)
            if resp.status_code != 200:
                return None
            return resp.json()
        except Exception:
            return None

    def _cached(self, key: str, path: str, timeout: float = 8.0) -> Optional[Any]:
        now = _monotonic()
        if key in self._cache and (now - self._cache_at.get(key, 0)) < _DATA_TTL:
            return self._cache[key]
        data = self._get(path, timeout=timeout)
        if data is not None:
            self._cache[key] = data
            self._cache_at[key] = now
        return data

    # ── fetch raw broker data ────────────────────────────────────────

    def fetch_account(self) -> Optional[Dict]:
        return self._cached("account", "/account")

    def fetch_positions(self) -> List[Dict]:
        data = self._cached("positions", "/positions")
        positions = (data or {}).get("positions", []) if isinstance(data, dict) else []
        # Record each open position's money-at-risk so R is computable when it closes.
        self._record_risk(positions)
        return positions

    # ── R-multiple risk tracking ─────────────────────────────────────
    # The broker's closed-deal ledger has no stop-loss, so R can't be recovered
    # after the fact. While a position is OPEN it carries its SL and the broker's
    # live P&L — from which we derive the exact money-at-risk and persist it per
    # ticket. On close, R = realized P&L / that risk.

    def _risk_money(self, pos: Dict) -> Optional[float]:
        try:
            open_p = float(pos.get("open_price") or 0)
            sl = float(pos.get("sl") or 0)
            lot = float(pos.get("lot_size") or 0)
        except (TypeError, ValueError):
            return None
        if not open_p or not sl:
            return None
        dist = abs(open_p - sl)
        if dist <= 0:
            return None
        # Risk = SL distance × the money value of one price unit per lot × lots.
        # Deterministic (the old live-P&L-ratio approach produced nonsense like
        # $93M risk when captured at a tiny price move). Prefer the broker's real
        # tick value; fall back to the static contract spec.
        symbol = str(pos.get("symbol", "")).upper()
        try:
            from app.services.broker_specs import money_per_lot
            mpl = money_per_lot(symbol, dist)  # money for `dist` move, per 1.0 lot
            if mpl and mpl > 0:
                return round(mpl * lot, 2)
        except Exception:
            pass
        from app.services.instrument_config import get_instrument
        cfg = get_instrument(symbol)
        if cfg and cfg.get("tick_size"):
            try:
                per_price_per_lot = float(cfg["tick_value"]) / float(cfg["tick_size"])
                return round(dist * per_price_per_lot * lot, 2)
            except (TypeError, ValueError, ZeroDivisionError):
                return None
        return None

    @staticmethod
    def fixed_risk_per_trade() -> Optional[float]:
        """A user-set fixed $ risk per trade (they size every trade to the same
        risk). When set, R = P&L / this — matching how the trader thinks."""
        try:
            from app.core.database import db
            row = db.find_one("settings", "global") or {}
            v = row.get("risk_per_trade")
            return float(v) if v not in (None, "", 0, "0") and float(v) > 0 else None
        except Exception:
            return None

    def compute_r(self, profit: float, pos: Dict) -> tuple:
        """Return (r, risk_money). Prefers the user's fixed per-trade risk, else
        the stop-loss-derived risk. None when neither is available."""
        fixed = self.fixed_risk_per_trade()
        if fixed:
            return round(profit / fixed, 2), fixed
        risk = self._risk_money(pos)
        if risk and risk > 0:
            return round(profit / risk, 2), risk
        return None, None

    def _record_risk(self, positions: List[Dict]) -> None:
        try:
            from app.core.database import db
        except Exception:
            return
        for p in positions:
            ticket = str(p.get("ticket", ""))
            if not ticket:
                continue
            rm = self._risk_money(p)
            if rm is None or rm <= 0:
                continue
            row = {"id": ticket, "symbol": p.get("symbol"), "open_price": p.get("open_price"),
                   "sl": p.get("sl"), "lot_size": p.get("lot_size"), "risk_money": rm}
            try:
                if db.find_one("mt5_position_risk", ticket):
                    db.update("mt5_position_risk", ticket, row)
                else:
                    db.insert("mt5_position_risk", row)
            except Exception:
                continue

    def _stored_risk(self, ticket: str) -> Optional[float]:
        try:
            from app.core.database import db
            row = db.find_one("mt5_position_risk", str(ticket))
            return float(row["risk_money"]) if row and row.get("risk_money") else None
        except Exception:
            return None

    def fetch_history(self) -> List[Dict]:
        data = self._cached("history", "/history")
        return (data or {}).get("history", []) if isinstance(data, dict) else []

    # ── activation gate ──────────────────────────────────────────────

    def is_active(self) -> bool:
        """True when MT5 should be the trade-data base: a remote bridge is
        configured AND the terminal is connected. Cached for _CONN_TTL so a down
        bridge doesn't cost a network round-trip on every stats call."""
        if not self._configured():
            return False
        now = _monotonic()
        if self._active is not None and (now - self._active_at) < _CONN_TTL:
            return self._active
        account = self.fetch_account()
        active = bool(account and account.get("status") == "connected")
        self._active = active
        self._active_at = now
        return active

    def clear_cache(self) -> None:
        self._cache.clear()
        self._cache_at.clear()
        self._active = None
        self._active_at = 0.0

    # ── normalization ────────────────────────────────────────────────

    def _normalize_closed(self, t: Dict) -> Dict:
        """Broker closed deal -> a trade dict carrying both the MT5 names and the
        synthetic-ledger aliases the frontend/analytics already read."""
        profit = float(t.get("profit", 0) or 0)
        direction = t.get("direction", "")
        ticket = str(t.get("ticket", ""))
        # R from the user's fixed per-trade risk, else the SL recovered off the
        # opening order (deals carry no SL). None when neither — never faked.
        r, risk = self.compute_r(profit, {
            "symbol": t.get("symbol"), "open_price": t.get("open_price"),
            "sl": t.get("sl"), "lot_size": t.get("lot_size"),
        })
        return {
            "id": ticket,
            "ticket": ticket,
            "symbol": t.get("symbol", ""),
            "direction": direction,
            "side": "BUY" if direction == "long" else "SELL",
            "status": "CLOSED",
            "lot_size": t.get("lot_size", 0),
            "quantity": t.get("lot_size", 0),
            "open_price": t.get("open_price", 0),
            "entry_price": t.get("open_price", 0),
            "close_price": t.get("close_price", 0),
            "exit_price": t.get("close_price", 0),
            "profit": round(profit, 2),
            "realized_pnl": round(profit, 2),
            "risk_money": risk,
            "total_r": r if r is not None else 0,
            "r": r,
            "created_at": t.get("closed_at", ""),
            "closed_at": t.get("closed_at", ""),
            "source": "mt5",
        }

    def _normalize_open(self, p: Dict) -> Dict:
        profit = float(p.get("profit", 0) or 0)
        direction = p.get("direction", "")
        r, risk = self.compute_r(profit, p)
        return {
            "id": str(p.get("ticket", "")),
            "ticket": str(p.get("ticket", "")),
            "symbol": p.get("symbol", ""),
            "direction": direction,
            "side": "BUY" if direction == "long" else "SELL",
            "status": "OPEN",
            "lot_size": p.get("lot_size", 0),
            "quantity": p.get("lot_size", 0),
            "remaining_quantity": p.get("lot_size", 0),
            "open_price": p.get("open_price", 0),
            "entry_price": p.get("open_price", 0),
            "current_price": p.get("current_price", 0),
            "stop_loss": p.get("sl", 0),
            "take_profit_1": p.get("tp", 0),
            "profit": round(profit, 2),
            "unrealized_pnl": round(profit, 2),
            "risk_money": risk,
            "r": r,
            "swap": p.get("swap", 0),
            "source": "mt5",
        }

    # ── public: trades ───────────────────────────────────────────────

    def get_open_trades(self) -> List[Dict]:
        return [self._normalize_open(p) for p in self.fetch_positions()]

    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        closed = [self._normalize_closed(t) for t in self.fetch_history()]
        self._journal(closed)
        closed.sort(key=lambda x: x.get("closed_at", ""), reverse=True)
        return closed[:limit]

    def _journal(self, closed: List[Dict]) -> None:
        """Mirror closed trades into the durable journal (best-effort). Uses
        mirror_closed (record + prune) rather than a bare insert so the journal
        converges to MT5's exact set on every tick — stale/duplicate rows from an
        older keying scheme get cleaned up automatically, not just on manual sync."""
        try:
            from app.services.trade_journal_service import trade_journal_service
            trade_journal_service.mirror_closed(closed)
        except Exception:
            pass

    # ── stats (same schema as trade_lifecycle_service.get_trade_stats) ─

    def _session_for_hour(self, hour: int) -> str:
        if 7 <= hour < 10:
            return "London Open"
        if 12 <= hour < 15:
            return "NY AM"
        if 15 <= hour < 17:
            return "NY Lunch"
        if 17 <= hour < 21:
            return "NY PM"
        if hour >= 21 or hour < 8:
            return "Asian"
        return "London Close"

    def get_stats(self) -> Dict[str, Any]:
        positions = self.fetch_positions()
        history = self.fetch_history()
        account = self.fetch_account() or {}

        closed = [self._normalize_closed(t) for t in history]
        self._journal(closed)
        closed.sort(key=lambda x: x.get("closed_at", ""))

        realized = sum(t["realized_pnl"] for t in closed)
        unrealized = round(sum(float(p.get("profit", 0) or 0) for p in positions), 2)
        total_pnl = round(realized + unrealized, 2)

        wins = [t for t in closed if t["realized_pnl"] > 0]
        losses = [t for t in closed if t["realized_pnl"] <= 0]
        n_closed = len(closed)
        win_rate = round(len(wins) / n_closed * 100, 1) if n_closed else 0
        avg_win = round(sum(t["realized_pnl"] for t in wins) / len(wins), 2) if wins else 0
        avg_loss = round(sum(t["realized_pnl"] for t in losses) / len(losses), 2) if losses else 0
        expectancy = round((win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss), 2) if n_closed else 0

        streaks = self._calc_streaks(closed)
        dd = self._calc_drawdown(closed, account)

        # R-multiples over the closed trades whose risk we captured while open.
        r_vals = [t["r"] for t in closed if t.get("r") is not None]
        total_r = round(sum(r_vals), 2)
        avg_r = round(total_r / len(r_vals), 2) if r_vals else 0
        best_r = round(max(r_vals), 2) if r_vals else 0
        worst_r = round(min(r_vals), 2) if r_vals else 0

        by_symbol: Dict[str, Any] = {}
        monthly: Dict[str, Any] = {}
        sessions: Dict[str, Any] = {}
        for t in closed:
            pnl = t["realized_pnl"]
            sym = t["symbol"]
            s = by_symbol.setdefault(sym, {"trades": 0, "wins": 0, "losses": 0, "total_pnl": 0, "best": 0, "worst": 0})
            s["trades"] += 1
            s["total_pnl"] += pnl
            s["wins" if pnl > 0 else "losses"] += 1
            s["best"] = max(s["best"], pnl)
            s["worst"] = min(s["worst"], pnl)

            ts = t.get("closed_at", "") or ""
            month = ts[:7] if ts else "unknown"
            m = monthly.setdefault(month, {"trades": 0, "wins": 0, "losses": 0, "pnl": 0, "win_rate": 0})
            m["trades"] += 1
            m["pnl"] += pnl
            m["wins" if pnl > 0 else "losses"] += 1

            hour = int(ts[11:13]) if len(ts) > 13 else 12
            sess = self._session_for_hour(hour)
            sn = sessions.setdefault(sess, {"count": 0, "wins": 0, "losses": 0, "pnl": 0, "win_rate": 0})
            sn["count"] += 1
            sn["pnl"] += pnl
            sn["wins" if pnl > 0 else "losses"] += 1

        for s in by_symbol.values():
            s["win_rate"] = round(s["wins"] / s["trades"] * 100, 1) if s["trades"] else 0
            s["avg_pnl"] = round(s["total_pnl"] / s["trades"], 2) if s["trades"] else 0
            s["total_pnl"] = round(s["total_pnl"], 2)
        for m in monthly.values():
            m["win_rate"] = round(m["wins"] / m["trades"] * 100, 1) if m["trades"] else 0
            m["pnl"] = round(m["pnl"], 2)
        for sn in sessions.values():
            sn["win_rate"] = round(sn["wins"] / sn["count"] * 100, 1) if sn["count"] else 0
            sn["pnl"] = round(sn["pnl"], 2)

        return {
            "total_trades": n_closed + len(positions),
            "open_trades": len(positions),
            "closed_trades": n_closed,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "realized_pnl": round(realized, 2),
            "unrealized_pnl": unrealized,
            "avg_pnl": round(realized / n_closed, 2) if n_closed else 0,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "expectancy": expectancy,
            "best_trade": round(max((t["realized_pnl"] for t in closed), default=0), 2),
            "worst_trade": round(min((t["realized_pnl"] for t in closed), default=0), 2),
            "avg_r": avg_r,
            "total_r": total_r,
            "best_r": best_r,
            "worst_r": worst_r,
            "r_tracked_trades": len(r_vals),  # of how many closed trades R is real
            "max_win_streak": streaks["max_win"],
            "max_loss_streak": streaks["max_loss"],
            "current_streak": streaks["current"],
            "max_drawdown": dd["max_drawdown"],
            "max_drawdown_duration": dd["max_drawdown_duration"],
            "equity_curve": dd["equity_curve"],
            "by_symbol": by_symbol,
            "monthly": monthly,
            "sessions": sessions,
            "source": "mt5",
            "account": {
                "balance": account.get("balance"),
                "equity": account.get("equity"),
                "currency": account.get("currency"),
            },
        }

    def _calc_streaks(self, closed: List[Dict]) -> Dict:
        if not closed:
            return {"max_win": 0, "max_loss": 0, "current": 0}
        max_win = max_loss = cur_win = cur_loss = current = 0
        for t in closed:
            if t["realized_pnl"] > 0:
                cur_win += 1
                cur_loss = 0
                max_win = max(max_win, cur_win)
                current = cur_win
            else:
                cur_loss += 1
                cur_win = 0
                max_loss = max(max_loss, cur_loss)
                current = -cur_loss
        return {"max_win": max_win, "max_loss": max_loss, "current": current}

    def _calc_drawdown(self, closed: List[Dict], account: Dict) -> Dict:
        if not closed:
            return {"max_drawdown": 0, "max_drawdown_duration": 0, "equity_curve": []}
        realized_total = sum(t["realized_pnl"] for t in closed)
        # Reconstruct the curve so it ENDS at the real current balance.
        balance = account.get("balance")
        start = (float(balance) - realized_total) if balance is not None else _STARTING_EQUITY_FALLBACK
        equity = start
        peak = equity
        max_dd = 0.0
        max_dd_dur = 0
        cur_dur = 0
        curve = []
        for i, t in enumerate(closed):
            equity += t["realized_pnl"]
            curve.append({"trade": i + 1, "equity": round(equity, 2), "pnl": t["realized_pnl"]})
            if equity > peak:
                peak = equity
                cur_dur = 0
            else:
                cur_dur += 1
                dd = (peak - equity) / peak * 100 if peak else 0
                if dd > max_dd:
                    max_dd = dd
                    max_dd_dur = cur_dur
        return {"max_drawdown": round(max_dd, 2), "max_drawdown_duration": max_dd_dur, "equity_curve": curve}

    def get_kelly(self) -> Dict:
        """Kelly criterion over broker realized P&L."""
        from app.services.quant_service import quant_service
        closed = [self._normalize_closed(t) for t in self.fetch_history()]
        kelly = quant_service.calculate_kelly([t["realized_pnl"] for t in closed])
        # Match the lifecycle service's sign convention for avg_loss.
        kelly["avg_loss"] = -abs(kelly["avg_loss"])
        return kelly

    # ── chatbot context ──────────────────────────────────────────────

    def get_context_block(self, recent_limit: int = 5) -> Optional[str]:
        """A compact, factual snapshot of the live account for the chatbot to
        ground answers in. Returns None when MT5 isn't the active base."""
        if not self.is_active():
            return None
        account = self.fetch_account() or {}
        positions = self.fetch_positions()
        recent = self.get_recent_trades(recent_limit)
        stats = self.get_stats()

        lines = ["LIVE MT5 ACCOUNT SNAPSHOT (the user's real broker account):"]
        cur = account.get("currency", "USD")
        lines.append(
            f"- Account: balance {account.get('balance')} {cur}, equity {account.get('equity')} {cur}, "
            f"free margin {account.get('free_margin')}, margin level {account.get('margin_level')}."
        )
        lines.append(
            f"- Performance: total P&L {stats['total_pnl']} {cur} "
            f"(realized {stats['realized_pnl']}, open float {stats['unrealized_pnl']}); "
            f"win rate {stats['win_rate']}% over {stats['closed_trades']} closed trades."
        )
        if positions:
            lines.append(f"- Open positions ({len(positions)}):")
            for p in positions:
                lines.append(
                    f"    · {p.get('symbol')} {p.get('direction')} {p.get('lot_size')} lots @ "
                    f"{p.get('open_price')} (now {p.get('current_price')}), SL {p.get('sl')} TP {p.get('tp')}, "
                    f"float P&L {round(float(p.get('profit', 0) or 0), 2)} {cur}."
                )
        else:
            lines.append("- Open positions: none.")
        if recent:
            lines.append(f"- Recent closed trades (latest {len(recent)}):")
            for t in recent:
                lines.append(
                    f"    · {t['symbol']} {t['direction']} {t['lot_size']} lots, "
                    f"{t['open_price']}→{t['close_price']}, P&L {t['realized_pnl']} {cur} "
                    f"(closed {t['closed_at']})."
                )
        return "\n".join(lines)


mt5_trades_service = Mt5TradesService()
