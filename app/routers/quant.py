"""Quant Lab Router."""
from fastapi import APIRouter
from app.core.database import db
from app.services.quant_service import quant_service

router = APIRouter(prefix="/quant", tags=["Quant Lab"])

@router.get("/metrics")
def get_metrics():
    trades = db.find("trades", status="CLOSED")
    trade_dicts = [{"realized_pnl": t.get("realized_pnl", 0), "symbol": t.get("symbol", "")} for t in trades]
    return quant_service.compute_metrics(trade_dicts)

@router.get("/kelly")
def get_kelly():
    trades = db.find("trades", status="CLOSED")
    trade_dicts = [{"realized_pnl": t.get("realized_pnl", 0)} for t in trades]
    kelly = quant_service.compute_kelly(trade_dicts)
    if not kelly: return {"error": "Need 5+ closed trades with wins and losses"}
    return kelly

@router.post("/monte-carlo")
def monte_carlo(n_simulations: int = 1000, n_trades: int = 100):
    trades = db.find("trades", status="CLOSED")
    trade_dicts = [{"realized_pnl": t.get("realized_pnl", 0)} for t in trades]
    return quant_service.monte_carlo(trade_dicts, n_simulations, n_trades)

@router.get("/coach")
def get_coach():
    trades = db.find("trades", status="CLOSED")
    trade_dicts = [{"realized_pnl": t.get("realized_pnl", 0), "symbol": t.get("symbol", "")} for t in trades]
    from datetime import datetime
    return {
        "recommendations": quant_service.coach(trade_dicts),
        "summary": "Performance coaching active.",
        "last_updated": datetime.utcnow().isoformat()
    }
