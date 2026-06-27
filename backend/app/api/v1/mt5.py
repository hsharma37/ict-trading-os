from fastapi import APIRouter, HTTPException
import httpx
from typing import Optional
from uuid import UUID

from app.config import settings

router = APIRouter()

MT5_BASE = settings.mt5_bridge_url


@router.post("/trade", summary="Proxy an order to the MT5 bridge")
async def proxy_trade(
    symbol: str,
    direction: str,  # long or short
    lot_size: float,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
):
    """
    Send a trade order to the local MT5 bridge.
    """
    payload = {
        "symbol": symbol,
        "direction": direction,
        "lot_size": lot_size,
    }
    if stop_loss is not None:
        payload["stop_loss"] = stop_loss
    if take_profit is not None:
        payload["take_profit"] = take_profit

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{MT5_BASE}/trade",
                json=payload,
                timeout=30,
            )
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MT5 bridge error: {str(e)}")


@router.get("/account", summary="Get MT5 account summary")
async def get_account():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{MT5_BASE}/account", timeout=10)
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MT5 bridge error: {str(e)}")


@router.get("/positions", summary="Get open positions from MT5")
async def get_positions():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{MT5_BASE}/positions", timeout=10)
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MT5 bridge error: {str(e)}")


@router.get("/status", summary="Check MT5 bridge connectivity")
async def get_bridge_status():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{MT5_BASE}/", timeout=5)
        return {
            "bridge_url": MT5_BASE,
            "reachable": resp.status_code == 200,
            "bridge_response": resp.json() if resp.status_code == 200 else None,
        }
    except Exception as e:
        return {
            "bridge_url": MT5_BASE,
            "reachable": False,
            "error": str(e),
        }
