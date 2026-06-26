"""Trades Router."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from app.core.database import db
from datetime import datetime

router = APIRouter(prefix="/trades", tags=["Trades"])

class TradeCreate(BaseModel):
    symbol: str
    side: str
    quantity: float
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    strategy: Optional[str] = None
    source: str = "Manual"
    plan_id: Optional[str] = None
    notes: Optional[str] = None

@router.post("/")
def create_trade(trade: TradeCreate):
    doc = trade.dict()
    doc["status"] = "OPEN"
    doc["realized_pnl"] = 0.0
    return db.insert("trades", doc)

@router.get("/")
def get_trades(status: Optional[str] = None, symbol: Optional[str] = None):
    trades = db.get_collection("trades")
    if status: trades = [t for t in trades if t.get("status") == status]
    if symbol: trades = [t for t in trades if t.get("symbol") == symbol]
    return trades[::-1]  # newest first

@router.post("/{trade_id}/close")
def close_trade(trade_id: str, exit_price: float):
    trade = db.find_one("trades", trade_id)
    if not trade: return {"error": "Trade not found"}

    pnl = (exit_price - trade["entry_price"]) * trade["quantity"] if trade["side"] == "BUY" else (trade["entry_price"] - exit_price) * trade["quantity"]

    db.update("trades", trade_id, {
        "exit_price": exit_price, "status": "CLOSED",
        "realized_pnl": round(pnl, 2), "closed_at": datetime.utcnow().isoformat()
    })
    return db.find_one("trades", trade_id)

@router.get("/stats/summary")
def trade_stats():
    trades = db.get_collection("trades")
    closed = [t for t in trades if t.get("status") == "CLOSED"]
    wins = [t for t in closed if t.get("realized_pnl", 0) > 0]
    return {
        "total_trades": len(trades), "open_trades": len([t for t in trades if t.get("status") == "OPEN"]),
        "closed_trades": len(closed), "winning_trades": len(wins),
        "win_rate": round(len(wins)/len(closed)*100, 1) if closed else 0,
        "total_pnl": round(sum(t.get("realized_pnl", 0) for t in closed), 2),
        "avg_pnl": round(sum(t.get("realized_pnl", 0) for t in closed)/len(closed), 2) if closed else 0
    }
