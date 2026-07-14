"""Research Router — Instrument technical analysis and market overview."""
from fastapi import APIRouter, HTTPException
from typing import Optional
from app.services.research_service import research_service
from app.services.instrument_config import get_instrument, get_all_instruments
from app.services.mt5_trades_service import mt5_trades_service

router = APIRouter(prefix="/research", tags=["Research"])


@router.get("/instrument/{symbol}")
def analyze_instrument(symbol: str):
    """Get full technical analysis for an instrument."""
    try:
        result = research_service.analyze_instrument(symbol)
        if result.get("error"):
            raise HTTPException(status_code=404, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all")
def analyze_all():
    """Get analysis for all instruments."""
    try:
        return {"instruments": research_service.analyze_all()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/correlation")
def get_correlation():
    """Get correlation matrix between instruments."""
    try:
        return research_service.get_correlation_matrix()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
def get_market_summary():
    """Get market-wide summary, annotated with the user's live MT5 holdings."""
    try:
        summary = research_service.get_market_summary()
        if isinstance(summary, dict) and mt5_trades_service.is_active():
            summary["open_positions"] = mt5_trades_service.get_open_trades()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instruments")
def list_instruments():
    """List all available instruments with config."""
    return {"instruments": get_all_instruments()}
