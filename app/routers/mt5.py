"""MT5 Router — Proxy to the MT5 Flask bridge."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
import httpx
from typing import Optional

from app.core.config import settings
from app.services.mt5_guard import validate_trade, Mt5ValidationError
from app.services.bridge_config import get_bridge_url, get_bridge_api_key

router = APIRouter(prefix="/mt5", tags=["MT5 Terminal"])


def _base() -> str:
    """Effective bridge base URL (DB override -> env), resolved per call."""
    return get_bridge_url()


def _bridge_headers() -> dict:
    """Headers for every bridge call.

    - X-Bridge-Key: shared secret the bridge enforces (it's tunnelled to the
      internet, independent of this app's X-Api-Key gate).
    - ngrok-skip-browser-warning: bypasses ngrok's free-tier interstitial.
    """
    h = {"ngrok-skip-browser-warning": "true"}
    key = get_bridge_api_key()
    if key:
        h["X-Bridge-Key"] = key
    return h


# MT5 order_send retcodes that mean the request was accepted.
_MT5_OK_RETCODES = {10008, 10009, 10010}  # PLACED, DONE, DONE_PARTIAL


def _result_or_raise(resp: "httpx.Response") -> dict:
    """Turn a bridge response into data, or raise so callers see the failure.

    The bridge returns non-200 (e.g. 503) or a 200 body carrying
    ``status: "error"`` / a bad broker ``retcode`` when an order doesn't go
    through. Returning that verbatim made the frontend show a false success — so
    detect it here and raise a real HTTP error instead."""
    try:
        body = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail=f"MT5 bridge returned non-JSON ({resp.status_code}).")
    if resp.status_code != 200:
        detail = (body.get("error") if isinstance(body, dict) else None) or f"MT5 bridge error {resp.status_code}"
        raise HTTPException(status_code=502, detail=detail)
    if isinstance(body, dict):
        if body.get("status") == "error" or body.get("error"):
            raise HTTPException(status_code=400, detail=body.get("error") or "MT5 reported an error.")
        retcode = body.get("retcode")
        if retcode is not None and retcode not in _MT5_OK_RETCODES:
            comment = body.get("comment") or ""
            raise HTTPException(status_code=400, detail=f"Broker rejected the order (retcode {retcode}) {comment}".strip())
    return body


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
    """Check if the MT5 bridge is reachable and get its status (with retry)."""
    base = _base()
    last = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{base}/", headers=_bridge_headers(), timeout=12)
            return {
                "bridge_url": base,
                "reachable": resp.status_code == 200,
                "bridge_response": resp.json() if resp.status_code == 200 else None,
            }
        except Exception as e:
            last = e
    return {"bridge_url": base, "reachable": False, "error": f"{type(last).__name__}: {last}"}


@router.get("/account", summary="Get MT5 account summary")
async def get_account():
    """Get MT5 account info (balance, equity, margin, etc.)."""
    return await _bridge_get("/account")


@router.get("/positions", summary="Get open positions from MT5")
async def get_positions():
    """Get currently open positions on MT5."""
    return await _bridge_get("/positions")


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
                f"{_base()}/trade",
                json=payload,
                headers=_bridge_headers(),
                timeout=30,
            )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MT5 bridge unreachable: {str(e)}")
    return _result_or_raise(resp)


@router.post("/close", summary="Close a position on MT5")
async def close_position(ticket_id: str):
    """Close an open position by ticket ID."""
    return await _bridge_post("/close", {"ticket_id": ticket_id})


@router.get("/history", summary="Get trade history from MT5")
async def get_history():
    """Get closed trade history from MT5."""
    return await _bridge_get("/history")


# ── Generic proxy helpers for the read/manage endpoints ──────────

async def _bridge_get(path: str, params: dict = None, timeout: float = 20, retries: int = 2):
    # Tunnels (esp. free ngrok) drop the occasional connection; a quick retry
    # turns a transient timeout into a success instead of a 503.
    last = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{_base()}{path}", params=params, headers=_bridge_headers(), timeout=timeout)
            return resp.json()
        except Exception as e:
            last = e
    raise HTTPException(status_code=503, detail=f"MT5 bridge unreachable: {type(last).__name__}: {last}")


async def _bridge_post(path: str, payload: dict, timeout: float = 30, retries: int = 1):
    last = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{_base()}{path}", json=payload, headers=_bridge_headers(), timeout=timeout)
            # Surface broker/bridge errors instead of returning a false success.
            return _result_or_raise(resp)
        except HTTPException:
            raise
        except Exception as e:
            last = e
    raise HTTPException(status_code=503, detail=f"MT5 bridge unreachable: {type(last).__name__}: {last}")


# ── Market data ──────────────────────────────────────────────

@router.get("/tick/{symbol}", summary="Live bid/ask/last from the broker feed")
async def get_tick(symbol: str):
    return await _bridge_get(f"/tick/{symbol}")


@router.get("/candles/{symbol}", summary="Historical OHLC candles")
async def get_candles(symbol: str, timeframe: str = "1h", count: int = 200):
    return await _bridge_get(f"/candles/{symbol}", params={"timeframe": timeframe, "count": count})


@router.get("/symbol/{symbol}", summary="Contract specification for a symbol")
async def get_symbol_spec(symbol: str):
    return await _bridge_get(f"/symbol/{symbol}")


@router.get("/symbols", summary="List tradable symbols on the account")
async def get_symbols():
    return await _bridge_get("/symbols")


@router.get("/orders", summary="List working pending orders")
async def get_pending_orders():
    return await _bridge_get("/orders")


# ── Order & position management ──────────────────────────────

@router.post("/modify", summary="Modify SL/TP on an open position")
async def modify_position(
    ticket: str,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
):
    if stop_loss is None and take_profit is None:
        raise HTTPException(status_code=400, detail="Provide stop_loss and/or take_profit to modify.")
    if (stop_loss is not None and stop_loss <= 0) or (take_profit is not None and take_profit <= 0):
        raise HTTPException(status_code=400, detail="stop_loss/take_profit must be positive prices.")
    _audit_execution_intent({"action": "modify", "ticket": ticket,
                             "stop_loss": stop_loss, "take_profit": take_profit, "status": "accepted"})
    return await _bridge_post("/modify", {"ticket": ticket, "stop_loss": stop_loss, "take_profit": take_profit})


@router.post("/partial-close", summary="Close part of an open position")
async def partial_close(ticket: str, volume: float):
    if volume <= 0:
        raise HTTPException(status_code=400, detail="volume must be greater than 0.")
    _audit_execution_intent({"action": "partial_close", "ticket": ticket, "volume": volume, "status": "accepted"})
    return await _bridge_post("/partial-close", {"ticket": ticket, "volume": volume})


@router.post("/pending", summary="Place a pending limit/stop order")
async def place_pending(
    symbol: str,
    direction: str,       # long | short
    order_kind: str,      # limit | stop
    volume: float,
    price: float,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
):
    if order_kind not in ("limit", "stop"):
        raise HTTPException(status_code=400, detail="order_kind must be 'limit' or 'stop'.")
    # Same guardrails as market orders (symbol allowlist, lot caps, side-aware
    # SL/TP), validated against the pending order's own entry price.
    try:
        validated = validate_trade(symbol, direction, volume, stop_loss, take_profit, reference_price=price)
    except Mt5ValidationError as e:
        _audit_execution_intent({"action": "pending", "symbol": symbol, "direction": direction,
                                 "status": "rejected", "reason": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    _audit_execution_intent({"action": "pending", "symbol": validated["symbol"],
                             "direction": validated["direction"], "order_kind": order_kind, "status": "accepted"})
    return await _bridge_post("/pending", {
        "symbol": validated["symbol"], "direction": validated["direction"], "order_kind": order_kind,
        "volume": validated["lot_size"], "price": price, "stop_loss": stop_loss, "take_profit": take_profit,
    })


@router.post("/pending/cancel", summary="Cancel a pending order")
async def cancel_pending(order_ticket: str):
    _audit_execution_intent({"action": "cancel_pending", "order_ticket": order_ticket, "status": "accepted"})
    return await _bridge_post("/pending/cancel", {"order_ticket": order_ticket})
