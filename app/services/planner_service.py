"""Trade planner — turn a signal (or an event) into an armed, auto-executing plan.

Flow: create a draft plan (editable entry/SL/TP, risk-sized) → ARM it (one
confirmation) → it fires on its trigger:
  • price  → a native MT5 pending order (the broker triggers at the limit/stop).
  • time   → executed by run_due() when the scheduled time passes.
  • now    → executed immediately as a market order.

Event plans carry a reduced risk %. Nothing hits the account until armed.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.core.database import db
from app.services.bridge_config import get_bridge_url, get_bridge_api_key
from app.services.instrument_config import get_instrument
from app.services.mt5_guard import validate_trade, Mt5ValidationError

_COLL = "trade_plans"
_EVENT_RISK_FACTOR = 0.5  # event trades run at half the normal risk


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PlannerService:
    # ── bridge helpers (sync) ────────────────────────────────────────

    def _headers(self) -> dict:
        h = {"ngrok-skip-browser-warning": "true"}
        key = get_bridge_api_key()
        if key:
            h["X-Bridge-Key"] = key
        return h

    def _current_price(self, symbol: str) -> Optional[float]:
        try:
            from app.services.market_data import market_service
            q = market_service.get_price(symbol)
            return q.get("price") if q else None
        except Exception:
            return None

    def _post(self, path: str, payload: dict) -> Dict[str, Any]:
        base = get_bridge_url()
        resp = httpx.post(f"{base}{path}", json=payload, headers=self._headers(), timeout=30)
        try:
            body = resp.json()
        except Exception:
            raise RuntimeError(f"Bridge returned non-JSON ({resp.status_code})")
        if resp.status_code != 200 or (isinstance(body, dict) and (body.get("status") == "error" or body.get("error"))):
            raise RuntimeError((body.get("error") if isinstance(body, dict) else None) or f"Bridge error {resp.status_code}")
        retcode = body.get("retcode") if isinstance(body, dict) else None
        if retcode is not None and retcode not in (10008, 10009, 10010):
            raise RuntimeError(f"Broker rejected the order (retcode {retcode}) {body.get('comment','')}".strip())
        return body

    # ── sizing ───────────────────────────────────────────────────────

    def _lot_legs(self, symbol: str, total_lot: float, n_tps: int) -> List[float]:
        cfg = get_instrument(symbol.upper()) or {}
        min_lot = float(cfg.get("min_qty", 0.01) or 0.01)
        step = float(cfg.get("qty_step", 0.01) or 0.01)
        n = max(1, min(n_tps, int(total_lot / min_lot + 1e-9)))
        per = round(round((total_lot / n) / step) * step, 8)
        per = max(per, min_lot)
        legs = [per] * n
        legs[-1] = max(min_lot, round(round((total_lot - per * (n - 1)) / step) * step, 8))
        return legs

    def compute_lot(self, symbol: str, entry: float, stop_loss: float,
                    account_balance: float, risk_pct: float) -> float:
        from app.services.lot_calculator import lot_calculator
        try:
            res = lot_calculator.calculate(symbol, entry, stop_loss, account_balance, risk_pct)
            return float(res.get("lot_size") or 0)
        except Exception:
            return 0.0

    # ── CRUD ─────────────────────────────────────────────────────────

    def create_plan(self, data: Dict[str, Any]) -> Dict[str, Any]:
        symbol = str(data.get("symbol", "")).upper()
        side = str(data.get("side", "BUY")).upper()
        direction = "long" if side == "BUY" else "short"
        entry = float(data.get("entry_price") or 0) or self._current_price(symbol) or 0
        stop_loss = float(data["stop_loss"]) if data.get("stop_loss") not in (None, "") else None
        tps = [float(t) for t in (data.get("take_profits") or []) if str(t).strip()]
        account_balance = float(data.get("account_balance") or 10000)
        risk_pct = float(data.get("risk_pct") or 1.0)
        is_event = bool(data.get("is_event"))
        if is_event:
            risk_pct = round(risk_pct * _EVENT_RISK_FACTOR, 3)
        lot = float(data["lot_size"]) if data.get("lot_size") else (
            self.compute_lot(symbol, entry, stop_loss, account_balance, risk_pct) if stop_loss else 0.0)

        plan = {
            "id": data.get("id") or f"plan_{uuid.uuid4().hex[:12]}",
            "symbol": symbol, "side": side, "direction": direction,
            "entry_price": round(entry, 6) if entry else None,
            "stop_loss": stop_loss, "take_profits": tps,
            "account_balance": account_balance, "risk_pct": risk_pct, "lot_size": lot,
            "trigger_type": data.get("trigger_type", "price"),  # price | time | now
            "trigger_time": data.get("trigger_time"),
            "is_event": is_event, "event_name": data.get("event_name"),
            "status": "draft",
            "source": data.get("source", "manual"),
            "source_signal_id": data.get("source_signal_id"),
            "notes": data.get("notes"),
            "mt5_tickets": [], "result": None,
            "created_at": _now(), "updated_at": _now(),
        }
        db.insert(_COLL, plan)
        return plan

    def list_plans(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        plans = db.get_collection(_COLL)
        if status:
            plans = [p for p in plans if p.get("status") == status]
        return sorted(plans, key=lambda p: p.get("created_at", ""), reverse=True)

    def update_plan(self, plan_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        plan = db.find_one(_COLL, plan_id)
        if not plan:
            return None
        if plan.get("status") not in ("draft",):
            return plan  # only drafts are editable
        allowed = {"entry_price", "stop_loss", "take_profits", "risk_pct", "lot_size",
                   "trigger_type", "trigger_time", "is_event", "notes"}
        clean = {k: v for k, v in updates.items() if k in allowed}
        db.update(_COLL, plan_id, {**clean, "updated_at": _now()})
        return db.find_one(_COLL, plan_id)

    def cancel(self, plan_id: str) -> Dict[str, Any]:
        plan = db.find_one(_COLL, plan_id)
        if not plan:
            return {"error": "Plan not found"}
        # Cancel any resting pending orders on the broker.
        for ticket in plan.get("mt5_tickets", []):
            try:
                self._post("/pending/cancel", {"order_ticket": ticket})
            except Exception:
                pass
        db.update(_COLL, plan_id, {"status": "cancelled", "updated_at": _now()})
        return db.find_one(_COLL, plan_id)

    # ── arming + execution ───────────────────────────────────────────

    def arm(self, plan_id: str) -> Dict[str, Any]:
        plan = db.find_one(_COLL, plan_id)
        if not plan:
            return {"error": "Plan not found"}
        if plan.get("status") not in ("draft",):
            return {"error": f"Plan is {plan.get('status')}, not armable"}
        if not plan.get("lot_size"):
            return {"error": "Plan has no lot size — set a stop loss (for risk sizing) or a manual lot."}

        trigger = plan.get("trigger_type", "price")
        db.update(_COLL, plan_id, {"status": "armed", "armed_at": _now(), "updated_at": _now()})
        if trigger == "now":
            return self._execute(plan_id, kind="market")
        if trigger == "price":
            return self._execute(plan_id, kind="pending")
        # time trigger: wait for run_due().
        return db.find_one(_COLL, plan_id)

    def _order_kind(self, side: str, entry: float, current: float) -> str:
        """limit = trigger back toward better price; stop = breakout beyond price."""
        if side == "BUY":
            return "limit" if entry <= current else "stop"
        return "limit" if entry >= current else "stop"

    def _execute(self, plan_id: str, kind: str) -> Dict[str, Any]:
        plan = db.find_one(_COLL, plan_id)
        if not plan:
            return {"error": "Plan not found"}
        symbol, direction, side = plan["symbol"], plan["direction"], plan["side"]
        sl = plan.get("stop_loss")
        tps = plan.get("take_profits") or [None]
        current = self._current_price(symbol) or plan.get("entry_price") or 0
        # SL/TP are validated against the price the order fills at: the entry for
        # a pending order, the current price for a market order.
        ref = plan.get("entry_price") if kind == "pending" else current
        legs_lots = self._lot_legs(symbol, plan["lot_size"], max(1, len([t for t in tps if t])) or 1)
        tp_list = [t for t in tps if t] or [None]
        # Pair each lot leg with a target (so each exits at its own TP).
        pairs = list(zip(legs_lots, (tp_list + tp_list)[:len(legs_lots)]))

        results = []
        tickets = []
        for lot, tp in pairs:
            try:
                validate_trade(symbol, direction, lot, sl, tp, reference_price=ref)
                if kind == "market":
                    body = self._post("/trade", {"symbol": symbol, "direction": direction,
                                                 "lot_size": lot, "stop_loss": sl, "take_profit": tp})
                else:
                    ok = self._order_kind(side, plan["entry_price"], current)
                    body = self._post("/pending", {"symbol": symbol, "direction": direction,
                                                   "order_kind": ok, "volume": lot, "price": plan["entry_price"],
                                                   "stop_loss": sl, "take_profit": tp})
                tk = body.get("order")
                if tk:
                    tickets.append(tk)
                results.append({"lot": lot, "tp": tp, "status": "ok", "ticket": tk})
            except (Mt5ValidationError, RuntimeError, Exception) as e:  # noqa: BLE001
                results.append({"lot": lot, "tp": tp, "status": "failed", "error": str(e)})

        ok_any = any(r["status"] == "ok" for r in results)
        status = ("placed" if kind == "pending" else "executed") if ok_any else "failed"
        db.update(_COLL, plan_id, {"status": status, "mt5_tickets": tickets,
                                   "result": results, "executed_at": _now(), "updated_at": _now()})
        return db.find_one(_COLL, plan_id)

    def run_due(self) -> Dict[str, Any]:
        """Execute armed TIME-triggered plans whose time has passed. Called by the
        bridge scheduler (or a cron)."""
        now = datetime.now(timezone.utc)
        fired = []
        for plan in self.list_plans(status="armed"):
            if plan.get("trigger_type") != "time" or not plan.get("trigger_time"):
                continue
            try:
                due = datetime.fromisoformat(str(plan["trigger_time"]).replace("Z", "+00:00"))
            except Exception:
                continue
            if due.astimezone(timezone.utc) <= now:
                self._execute(plan["id"], kind="market")
                fired.append(plan["id"])
        return {"ok": True, "fired": len(fired), "plan_ids": fired}


planner_service = PlannerService()
