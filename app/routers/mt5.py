"""MT5 Router — Proxy to the MT5 Flask bridge."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
import httpx
from typing import Optional

from app.core.config import settings
from app.services.mt5_guard import validate_trade, Mt5ValidationError

router = APIRouter(prefix="/mt5", tags=["MT5 Terminal"])

MT5_BASE = settings.MT5_BRIDGE_URL


def _audit_execution_intent(record: dict) -> None:
    """Best-effort audit log of every MT5 execution intent (never blocks a trade)."""
    try:
        from app.core.database import db
        db.insert("audit_logs", {
            "action": "mt5_trade_intent",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **record,
        })
    except Exception:
        pass


@router.get("/status", summary="Check MT5 bridge connectivity")
async def get_bridge_status():
    """Check if the MT5 bridge is reachable and get its status."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{MT5_BASE}/", timeout=5)
        data = resp.json() if resp.status_code == 200 else None
        return {
            "bridge_url": MT5_BASE,
            "reachable": resp.status_code == 200,
            "bridge_response": data,
        }
    except Exception as e:
        return {
            "bridge_url": MT5_BASE,
            "reachable": False,
            "error": str(e),
        }


@router.get("/account", summary="Get MT5 account summary")
async def get_account():
    """Get MT5 account info (balance, equity, margin, etc.)."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{MT5_BASE}/account", timeout=10)
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MT5 bridge unreachable: {str(e)}")


@router.get("/positions", summary="Get open positions from MT5")
async def get_positions():
    """Get currently open positions on MT5."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{MT5_BASE}/positions", timeout=10)
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MT5 bridge unreachable: {str(e)}")


@router.post("/trade", summary="Send trade to MT5")
async def proxy_trade(
    symbol: str,
    direction: str,  # long or short
    lot_size: float,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
):
    """Send a trade order to the local MT5 bridge, after safety validation."""
    # Fetch the current price for side-aware SL/TP validation (best-effort).
    reference_price = None
    if stop_loss is not None or take_profit is not None:
        try:
            from app.services.market_data import market_service
            quote = market_service.get_price(symbol)
            reference_price = quote.get("price") if quote else None
        except Exception:
            reference_price = None

    try:
        validated = validate_trade(
            symbol, direction, lot_size, stop_loss, take_profit, reference_price=reference_price
        )
    except Mt5ValidationError as e:
        _audit_execution_intent({
            "symbol": symbol, "direction": direction, "lot_size": lot_size,
            "stop_loss": stop_loss, "take_profit": take_profit,
            "status": "rejected", "reason": str(e),
        })
        raise HTTPException(status_code=400, detail=str(e))

    payload = {
        "symbol": validated["symbol"],
        "direction": validated["direction"],
        "lot_size": validated["lot_size"],
    }
    if stop_loss is not None:
        payload["stop_loss"] = stop_loss
    if take_profit is not None:
        payload["take_profit"] = take_profit

    _audit_execution_intent({**payload, "status": "accepted"})

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{MT5_BASE}/trade",
                json=payload,
                timeout=30,
            )
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MT5 bridge unreachable: {str(e)}")


@router.post("/close", summary="Close a position on MT5")
async def close_position(ticket_id: str):
    """Close an open position by ticket ID."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{MT5_BASE}/close",
                json={"ticket_id": ticket_id},
                timeout=30,
            )
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MT5 bridge unreachable: {str(e)}")


@router.get("/history", summary="Get trade history from MT5")
async def get_history():
    """Get closed trade history from MT5."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{MT5_BASE}/history", timeout=10)
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MT5 bridge unreachable: {str(e)}")
