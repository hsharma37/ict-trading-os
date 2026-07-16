"""Planner Router — plan trades from signals/events, arm, and auto-execute."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.database import db
from app.services.planner_service import planner_service

router = APIRouter(prefix="/planner", tags=["Planner"])


class PlanCreate(BaseModel):
    symbol: str
    side: str = "BUY"
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profits: List[float] = []
    account_balance: Optional[float] = None
    risk_pct: Optional[float] = None
    lot_size: Optional[float] = None
    trigger_type: str = "price"           # price | time | now
    trigger_time: Optional[str] = None    # ISO for time trigger
    is_event: bool = False
    event_name: Optional[str] = None
    source: str = "manual"
    source_signal_id: Optional[str] = None
    notes: Optional[str] = None


class PlanUpdate(BaseModel):
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profits: Optional[List[float]] = None
    risk_pct: Optional[float] = None
    lot_size: Optional[float] = None
    trigger_type: Optional[str] = None
    trigger_time: Optional[str] = None
    is_event: Optional[bool] = None
    notes: Optional[str] = None


@router.get("/plans")
def list_plans(status: Optional[str] = None):
    return {"plans": planner_service.list_plans(status)}


@router.post("/plans")
def create_plan(body: PlanCreate):
    return planner_service.create_plan(body.dict())


@router.post("/from-signal/{signal_id:path}")
def plan_from_signal(signal_id: str, body: Optional[PlanCreate] = None):
    """Create a plan seeded from a Telegram signal, then REMOVE the signal from
    the feed (so acknowledged/planned signals don't pile up)."""
    sig = db.find_one("telegram_signals", signal_id)
    if not sig:
        raise HTTPException(status_code=404, detail="Signal not found")
    override = body.dict(exclude_unset=True) if body else {}
    tps = sig.get("take_profits") or []
    entries = sig.get("entry_prices") or []
    seed = {
        "symbol": sig.get("symbol") or override.get("symbol"),
        "side": sig.get("side") or "BUY",
        "entry_price": entries[0] if entries else None,
        "stop_loss": sig.get("stop_loss"),
        "take_profits": tps,
        "source": "telegram",
        "source_signal_id": signal_id,
        "notes": (sig.get("raw_text") or "")[:400],
    }
    seed.update({k: v for k, v in override.items() if v is not None})
    if not seed.get("symbol"):
        raise HTTPException(status_code=400, detail="Signal has no symbol; set one to plan it.")
    plan = planner_service.create_plan(seed)
    # Remove the signal now that it's been turned into a plan.
    db.delete("telegram_signals", signal_id)
    return {"plan": plan, "signal_removed": signal_id}


@router.post("/plans/{plan_id}/update")
def update_plan(plan_id: str, body: PlanUpdate):
    plan = planner_service.update_plan(plan_id, body.dict(exclude_unset=True))
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.post("/plans/{plan_id}/arm")
def arm_plan(plan_id: str):
    result = planner_service.arm(plan_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/plans/{plan_id}/cancel")
def cancel_plan(plan_id: str):
    result = planner_service.cancel(plan_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: str):
    ok = db.delete("trade_plans", plan_id)
    return {"deleted": ok, "id": plan_id}


@router.get("/run-due", summary="Execute due time-triggered plans (cron/bridge)")
def run_due(request: Request):
    """Fire armed time-triggered plans whose time has passed. Meant to be called
    on a short interval by the always-on bridge (or a cron). Guarded by
    CRON_SECRET when set."""
    secret = settings.CRON_SECRET
    if secret:
        if request.headers.get("authorization", "") != f"Bearer {secret}":
            raise HTTPException(status_code=401, detail="Unauthorized")
    result = planner_service.run_due()
    # Piggyback on the bridge's 60s tick to keep the trade journal current even
    # when nobody has the app open.
    try:
        from app.services.trade_journal_service import trade_journal_service
        result["journal"] = trade_journal_service.sync_from_mt5()
    except Exception:
        pass
    # Advance live paper-forward tests as new candles print (skips when unchanged).
    try:
        from app.services.forward_test_service import forward_test_service
        result["forward_tests"] = forward_test_service.tick_all()
    except Exception:
        pass
    return result
