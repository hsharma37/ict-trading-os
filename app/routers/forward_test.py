"""Live paper-forward test endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.forward_test_service import forward_test_service

router = APIRouter(prefix="/forward-tests", tags=["Forward Test"])


class ForwardTestCreate(BaseModel):
    symbol: str
    timeframe: str = "1h"
    target_r: float = 3.0
    session_filter: bool = False
    trend_filter: bool = False
    min_confluence: int = 2
    label: Optional[str] = ""
    name: Optional[str] = ""   # alias for label — "give the strategy a name"
    strategy: str = "ict_confluence"   # ict_confluence or any Strategy Lab key


@router.get("")
def list_forward_tests(refresh: bool = False):
    """All forward tests. Fast by default (stored stats); pass ?refresh=true to
    recompute from current candles. The old always-recompute behaviour re-fetched
    thousands of bars per test per page load and timed out the serverless fn."""
    tests = forward_test_service.list(recompute=refresh)
    return {"forward_tests": tests, "count": len(tests)}


@router.post("")
def create_forward_test(body: ForwardTestCreate):
    """Start tracking a locked config against candles printed from now on."""
    from app.services.strategy_service import STRATEGIES
    if body.strategy != "ict_confluence" and body.strategy not in STRATEGIES:
        raise HTTPException(status_code=422,
                            detail=f"Unknown strategy '{body.strategy}'. Use ict_confluence or one of: "
                                   + ", ".join(sorted(STRATEGIES)))
    res = forward_test_service.create(
        body.symbol, timeframe=body.timeframe, target_r=body.target_r,
        session_filter=body.session_filter, trend_filter=body.trend_filter,
        min_confluence=body.min_confluence, label=(body.name or body.label or ""),
        strategy=body.strategy,
    )
    if res.get("error"):
        raise HTTPException(status_code=422, detail=res["error"])
    return res


@router.post("/{test_id}/refresh")
def refresh_forward_test(test_id: str):
    """Recompute ONE forward test from current candles (bounded fetch)."""
    t = forward_test_service.get(test_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    return t


@router.post("/{test_id}/stop")
def stop_forward_test(test_id: str):
    res = forward_test_service.stop(test_id)
    if res.get("error"):
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.delete("/{test_id}")
def delete_forward_test(test_id: str):
    return forward_test_service.delete(test_id)
