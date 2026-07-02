"""Orders Router — Order entry with lot calculation and execution."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.services.lot_calculator import lot_calculator
from app.services.trade_lifecycle_service import trade_lifecycle_service
from app.services.market_data import market_service

router = APIRouter(prefix="/orders", tags=["Orders"])


class CalculateLotRequest(BaseModel):
    symbol: str
    entry_price: Optional[float] = None
    stop_loss: float
    account_balance: float = 10000.0
    risk_pct: float = 1.0


class QuickLotRequest(BaseModel):
    symbol: str
    sl_pips: float
    account_balance: float = 10000.0
    risk_pct: float = 1.0


class OrderCreate(BaseModel):
    symbol: str
    side: str = Field(default="BUY", description="BUY or SELL")
    entry_price: Optional[float] = None
    stop_loss: float
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    account_balance: float = 10000.0
    risk_pct: float = 1.0
    strategy: Optional[str] = None
    notes: Optional[str] = None
    plan_id: Optional[str] = None


class OrderExecute(BaseModel):
    exit_price: float


@router.post("/calculate-lot")
def calculate_lot(request: CalculateLotRequest):
    """Calculate lot size based on risk, price, and leverage."""
    try:
        if request.entry_price is None or request.entry_price <= 0:
            live = market_service.get_price(request.symbol)
            entry_price = live.get("price", 0)
            if entry_price <= 0:
                raise HTTPException(status_code=400, detail="Could not fetch live price for the symbol")
        else:
            entry_price = request.entry_price

        result = lot_calculator.calculate(
            symbol=request.symbol,
            entry_price=entry_price,
            stop_loss=request.stop_loss,
            account_balance=request.account_balance,
            risk_pct=request.risk_pct,
        )
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick-lot")
def quick_lot(request: QuickLotRequest):
    """Quick lot calculation using pip distance from current live price."""
    try:
        result = lot_calculator.quick_lot(
            symbol=request.symbol,
            account_balance=request.account_balance,
            risk_pct=request.risk_pct,
            sl_pips=request.sl_pips,
        )
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_order(order: OrderCreate):
    """Create an order (auto-calculates lot size if not specified)."""
    try:
        result = trade_lifecycle_service.create_trade(
            symbol=order.symbol,
            side=order.side,
            entry_price=order.entry_price,
            stop_loss=order.stop_loss,
            take_profit_1=order.take_profit_1,
            take_profit_2=order.take_profit_2,
            take_profit_3=order.take_profit_3,
            account_balance=order.account_balance,
            risk_pct=order.risk_pct,
            strategy=order.strategy,
            notes=order.notes,
            plan_id=order.plan_id,
        )
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def list_orders(status: Optional[str] = None, symbol: Optional[str] = None):
    """List all orders."""
    try:
        return {"orders": trade_lifecycle_service.list_trades(status, symbol)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{order_id}")
def get_order(order_id: str):
    """Get a single order."""
    try:
        order = trade_lifecycle_service.get_trade(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return order
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{order_id}/execute")
def execute_order(order_id: str, request: OrderExecute):
    """Execute (close) an order at a price."""
    try:
        result = trade_lifecycle_service.full_close(order_id, request.exit_price)
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{order_id}")
def delete_order(order_id: str):
    """Delete an order."""
    try:
        order = trade_lifecycle_service.get_trade(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        # Mark as cancelled in DB
        from app.core.database import db
        db.update("trades", order_id, {"status": "CANCELLED", "updated_at": datetime.utcnow().isoformat()})
        return {"deleted": True, "id": order_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
