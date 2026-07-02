"""Analytics Router — Trade performance metrics and insights."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.analytics_service import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


class RecentRequest(BaseModel):
    limit: Optional[int] = 10


@router.get("/summary")
def get_summary():
    """Get full analytics summary."""
    try:
        return analytics_service.get_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expectancy")
def get_expectancy():
    """Get expectancy metrics."""
    try:
        return analytics_service.get_expectancy()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/heatmap")
def get_heatmap():
    """Get session performance heatmap."""
    try:
        return analytics_service.get_heatmap()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drawdown")
def get_drawdown():
    """Get drawdown and equity curve."""
    try:
        return analytics_service.get_drawdown()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kelly")
def get_kelly():
    """Get Kelly criterion."""
    try:
        return analytics_service.get_kelly()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/symbols")
def get_symbols():
    """Get per-symbol performance."""
    try:
        return analytics_service.get_symbols()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monthly")
def get_monthly():
    """Get monthly performance breakdown."""
    try:
        return analytics_service.get_monthly()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent")
def get_recent(limit: int = 10):
    """Get recent trades."""
    try:
        return {"trades": analytics_service.get_recent(limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
