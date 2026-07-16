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


@router.get("")
def list_forward_tests():
    """All forward tests, each recomputed from current candles (live stats)."""
    tests = forward_test_service.list(recompute=True)
    return {"forward_tests": tests, "count": len(tests)}


@router.post("")
def create_forward_test(body: ForwardTestCreate):
    """Start tracking a locked config against candles printed from now on."""
    res = forward_test_service.create(
        body.symbol, timeframe=body.timeframe, target_r=body.target_r,
        session_filter=body.session_filter, trend_filter=body.trend_filter,
        min_confluence=body.min_confluence, label=body.label or "",
    )
    if res.get("error"):
        raise HTTPException(status_code=422, detail=res["error"])
    return res


@router.post("/{test_id}/stop")
def stop_forward_test(test_id: str):
    res = forward_test_service.stop(test_id)
    if res.get("error"):
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.delete("/{test_id}")
def delete_forward_test(test_id: str):
    return forward_test_service.delete(test_id)
