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

# Plain-English help for the retcodes users actually hit, so the UI can show a
# fix instead of a bare number.
_MT5_RETCODE_HELP = {
    10027: "AutoTrading is disabled in the MT5 terminal. Turn it on: click the "
           "\"Algo Trading\" button in the toolbar (or press Ctrl+E) so it's green, then retry.",
    10018: "The market is closed for this symbol right now.",
    10019: "Not enough free margin to open this position (try a smaller lot).",
    10016: "Invalid stop-loss/take-profit — too close to price or on the wrong side.",
    10015: "Invalid price for the order.",
    10014: "Invalid lot size for this symbol.",
    10013: "Invalid order request.",
    10009: "",  # done
}


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
            help_text = _MT5_RETCODE_HELP.get(retcode)
            comment = body.get("comment") or ""
            detail = help_text or f"Broker rejected the order (retcode {retcode}) {comment}".strip()
            raise HTTPException(status_code=400, detail=detail)
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


def _reference_price(symbol: str) -> Optional[float]:
    try:
        from app.services.market_data import market_service
        quote = market_service.get_price(symbol)
        return quote.get("price") if quote else None
    except Exception:
        return None


async def _execute_market(symbol, direction, lot_size, stop_loss, take_profit, ref_price):
    """Validate + place a single market order; raise HTTPException on any failure."""
    try:
        validated = validate_trade(symbol, direction, lot_size, stop_loss, take_profit, reference_price=ref_price)
    except Mt5ValidationError as e:
        _audit_execution_intent({"symbol": symbol, "direction": direction, "lot_size": lot_size,
                                 "stop_loss": stop_loss, "take_profit": take_profit,
                                 "status": "rejected", "reason": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    payload = {"symbol": validated["symbol"], "direction": validated["direction"], "lot_size": validated["lot_size"]}
    if stop_loss is not None:
        payload["stop_loss"] = stop_loss
    if take_profit is not None:
        payload["take_profit"] = take_profit
    _audit_execution_intent({**payload, "status": "accepted"})
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{_base()}/trade", json=payload, headers=_bridge_headers(), timeout=30)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MT5 bridge unreachable: {str(e)}")
    return _result_or_raise(resp)


@router.post("/trade", summary="Send trade to MT5")
async def proxy_trade(
    symbol: str,
    direction: str,  # long or short
    lot_size: float,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
):
    """Send a single market order to the local MT5 bridge, after safety validation."""
    ref = _reference_price(symbol) if (stop_loss is not None or take_profit is not None) else None
    return await _execute_market(symbol, direction, lot_size, stop_loss, take_profit, ref)


@router.post("/scaled-trade", summary="Scaled market order — one position per take-profit")
async def scaled_trade(
    symbol: str,
    direction: str,
    lot_size: float,               # TOTAL lot across all targets
    take_profits: str,             # comma-separated, e.g. "1.1450,1.1470,1.1490"
    stop_loss: Optional[float] = None,
):
    """Book profit in stages: an MT5 position has only ONE take-profit, so to
    exit at TP1/TP2/TP3 we split the total lot into one native position PER
    target, each with the same stop-loss and its own TP. The broker then closes
    each leg at its own level (instead of the whole trade closing at TP1)."""
    tps = [float(t) for t in take_profits.split(",") if t.strip()]
    if not tps:
        raise HTTPException(status_code=400, detail="Provide at least one take-profit.")
    n = len(tps)

    # Lot must split into >= min-lot legs.
    from app.services.instrument_config import get_instrument
    cfg = get_instrument(symbol.upper()) or {}
    min_lot = float(cfg.get("min_qty", 0.01) or 0.01)
    step = float(cfg.get("qty_step", 0.01) or 0.01)
    if lot_size < n * min_lot - 1e-9:
        raise HTTPException(
            status_code=400,
            detail=f"Lot {lot_size} is too small to split across {n} targets "
                   f"(need ≥ {round(n * min_lot, 2)}). Increase the lot or use fewer targets.",
        )

    def _round_step(v: float) -> float:
        return round(round(v / step) * step, 8)

    per = _round_step(lot_size / n)
    if per < min_lot:
        per = min_lot
    legs = [per] * n
    # Put any rounding remainder on the last leg so the total matches.
    legs[-1] = _round_step(lot_size - per * (n - 1))
    if legs[-1] < min_lot:
        legs[-1] = min_lot

    ref = _reference_price(symbol)
    results = []
    for lot, tp in zip(legs, sorted(tps, key=lambda x: x, reverse=(direction == "short"))):
        # For longs, nearest TP first (ascending); for shorts, highest first.
        try:
            res = await _execute_market(symbol, direction, lot, stop_loss, tp, ref)
            results.append({"take_profit": tp, "lot": lot, "status": "executed",
                            "ticket": res.get("order"), "price": res.get("price")})
        except HTTPException as e:
            results.append({"take_profit": tp, "lot": lot, "status": "failed", "error": e.detail})
    executed = [r for r in results if r["status"] == "executed"]
    return {"symbol": symbol, "direction": direction, "legs": len(legs),
            "executed": len(executed), "positions": results,
            "total_lot": round(sum(r["lot"] for r in executed), 2)}


@router.post("/order-check", summary="Validate an order without placing it")
async def order_check(
    symbol: str,
    direction: str,
    lot_size: float,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
):
    """Diagnose whether an order would fill (filling mode, stops, margin, market
    hours) without actually executing it."""
    payload = {"symbol": symbol, "direction": direction, "lot_size": lot_size}
    if stop_loss is not None:
        payload["stop_loss"] = stop_loss
    if take_profit is not None:
        payload["take_profit"] = take_profit
    # Not an execution -> the strict retcode check in _bridge_post doesn't apply;
    # order_check returns its own {ok, tried:[...]} shape.
    last = None
    for _ in range(2):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{_base()}/order-check", json=payload, headers=_bridge_headers(), timeout=20)
            return resp.json()
        except Exception as e:
            last = e
    raise HTTPException(status_code=503, detail=f"MT5 bridge unreachable: {last}")


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
