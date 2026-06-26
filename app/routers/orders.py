"""Orders Router."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services.order_service import order_service

router = APIRouter(prefix="/orders", tags=["Orders"])

class OrderCreate(BaseModel):
    symbol: str
    side: str
    quantity: float
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    strategy: Optional[str] = None
    source: Optional[str] = "Manual"
    plan_id: Optional[str] = None
    bot_action: Optional[bool] = False

@router.post("/")
def create_order(order: OrderCreate):
    return order_service.create_order(order.dict())

@router.get("/")
def list_orders(status: Optional[str] = None, symbol: Optional[str] = None):
    return order_service.list_orders(status=status, symbol=symbol)

@router.get("/quantity")
def calculate_quantity(symbol: str, entry_price: float, stop_loss: float, account_balance: float = 10000.0, risk_pct: float = 1.0):
    return order_service.calculate_quantity(symbol, entry_price, stop_loss, account_balance, risk_pct)
