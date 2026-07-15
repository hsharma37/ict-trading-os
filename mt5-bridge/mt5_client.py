"""
Thin wrapper around the MetaTrader5 Python package.

MetaTrader5's Python API only works on Windows, next to a running terminal
logged into the target account — MetaQuotes has no cloud/REST API for this.
This wrapper degrades gracefully when the package (or a live terminal
connection) isn't available, so the rest of this bridge — and this file, when
read/imported on a non-Windows dev machine — still works without crashing.
"""
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5  # type: ignore
    _MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    _MT5_AVAILABLE = False


class Mt5ConnectionError(RuntimeError):
    """Raised when the MetaTrader5 terminal is unavailable, not logged in,
    or a request to it fails."""


# MT5's DEAL_TYPE_BUY / DEAL_TYPE_SELL (and ORDER_TYPE_BUY / ORDER_TYPE_SELL,
# which share the same 0/1 values) -- deal types >= 2 are non-trade entries
# (balance, credit, etc.) and are ignored when reconstructing trade history.
_TYPE_BUY, _TYPE_SELL = 0, 1
_DEAL_ENTRY_IN, _DEAL_ENTRY_OUT = 0, 1

# App timeframe string -> MetaTrader5 TIMEFRAME_* constant name. Resolved to
# the real value lazily (mt5 may be absent on this dev machine).
_TIMEFRAME_NAMES = {
    "1m": "TIMEFRAME_M1", "5m": "TIMEFRAME_M5", "15m": "TIMEFRAME_M15",
    "30m": "TIMEFRAME_M30", "1h": "TIMEFRAME_H1", "4h": "TIMEFRAME_H4",
    "1d": "TIMEFRAME_D1", "1w": "TIMEFRAME_W1",
}

# MT5 pending order type name -> constant name. long/short + limit/stop.
_PENDING_TYPE_NAMES = {
    ("long", "limit"): "ORDER_TYPE_BUY_LIMIT",
    ("short", "limit"): "ORDER_TYPE_SELL_LIMIT",
    ("long", "stop"): "ORDER_TYPE_BUY_STOP",
    ("short", "stop"): "ORDER_TYPE_SELL_STOP",
}


def normalize_tick(symbol: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a raw MT5 tick into the app's price shape (mirrors the
    /market/price response: symbol, price=mid, bid, ask, plus spread)."""
    bid = raw.get("bid", 0) or 0
    ask = raw.get("ask", 0) or 0
    mid = round((bid + ask) / 2, 8) if (bid and ask) else (bid or ask or raw.get("last", 0))
    ts = raw.get("time")
    return {
        "symbol": symbol.upper(),
        "price": mid,
        "bid": bid,
        "ask": ask,
        "last": raw.get("last", 0),
        "spread": round(ask - bid, 8) if (bid and ask) else 0,
        "volume": raw.get("volume", 0),
        "time": datetime.fromtimestamp(ts).isoformat() if ts else None,
        "source": "mt5",
    }


def normalize_position(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Translate a raw MetaTrader5 position dict (volume, price_open,
    price_current, type as 0/1, ...) into the field names the frontend
    (MT5Terminal.tsx's MT5Position) actually expects.

    Without this, the app renders MT5's own field names directly: `direction`
    is always undefined (MT5 has no such field, only an int `type`), so
    `pos.direction.toUpperCase()` throws on every render once a real position
    exists -- which, on a page that polls every 5s, looks like the page
    repeatedly crashing/reloading.
    """
    return {
        "ticket": str(raw.get("ticket", "")),
        "symbol": raw.get("symbol", ""),
        "direction": "long" if raw.get("type") == _TYPE_BUY else "short",
        "lot_size": raw.get("volume", 0),
        "open_price": raw.get("price_open", 0),
        "current_price": raw.get("price_current"),
        "sl": raw.get("sl", 0),
        "tp": raw.get("tp", 0),
        "profit": raw.get("profit", 0),
        "swap": raw.get("swap", 0),
    }


def pair_deals_into_trades(deals: List[Dict[str, Any]], sltp: Dict[Any, Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Reconstruct closed-trade records from MT5's deal ledger.

    MetaTrader5's history_deals_get() returns individual deals, not trades.
    Every *close* is an OUT deal carrying the realized profit; the matching
    *open* is an IN deal sharing the same position_id. This is driven by the
    OUT deals — one closed-trade record per close — so a trade shows even when
    its opening deal isn't in the window and even when position_id linking is
    imperfect (the earlier pair-both-legs approach silently dropped such
    closes). The open price is filled from the matching IN deal when available.

    Note: a partially-closed position produces multiple OUT deals and therefore
    multiple rows (one per partial close), which is the honest history.
    """
    opens: Dict[Any, Dict[str, Any]] = {}
    closes: List[Dict[str, Any]] = []
    for d in deals:
        if d.get("type") not in (_TYPE_BUY, _TYPE_SELL):
            continue  # skip balance/credit/other non-trade ledger entries
        if d.get("entry") == _DEAL_ENTRY_IN:
            opens[d.get("position_id")] = d
        else:  # DEAL_ENTRY_OUT / OUT_BY / INOUT — a realized close
            closes.append(d)

    sltp = sltp or {}
    trades: List[Dict[str, Any]] = []
    for d in closes:
        pid = d.get("position_id")
        in_deal = opens.get(pid)
        ts = d.get("time")
        levels = sltp.get(pid, {})
        # Realized P&L as MT5 books it = deal profit + swap + commission.
        net = (d.get("profit", 0) or 0) + (d.get("swap", 0) or 0) + (d.get("commission", 0) or 0)
        trades.append({
            "ticket": str(pid or d.get("ticket", "")),
            "symbol": d.get("symbol", ""),
            # An OUT deal's type is the *closing* side; the position it closed
            # was the opposite direction.
            "direction": "short" if d.get("type") == _TYPE_BUY else "long",
            "lot_size": d.get("volume", 0),
            "open_price": (in_deal or {}).get("price"),
            "close_price": d.get("price", 0),
            "profit": round(net, 2),
            # SL/TP recovered from the opening order (deals don't carry them) so
            # R is computable for historical trades.
            "sl": levels.get("sl") or None,
            "tp": levels.get("tp") or None,
            "closed_at": datetime.fromtimestamp(ts).isoformat() if ts else None,
        })

    trades.sort(key=lambda t: t.get("closed_at") or "", reverse=True)
    return trades


class Mt5Client:
    """Owns the single MetaTrader5 terminal connection for this process."""

    def __init__(self, login: int, password: str, server: str, terminal_path: str = ""):
        self._login = login
        self._password = password
        self._server = server
        self._terminal_path = terminal_path or None
        self._lock = threading.Lock()
        self._connected = False

    def available(self) -> bool:
        """Whether the MetaTrader5 package is installed (Windows only)."""
        return _MT5_AVAILABLE

    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        """Initialize the terminal and log in. Safe to call repeatedly —
        returns immediately if already connected."""
        if not _MT5_AVAILABLE:
            logger.warning(
                "MetaTrader5 package not installed (it's Windows-only) — "
                "running without a terminal connection."
            )
            return False
        with self._lock:
            if self._connected:
                return True
            if not self._login or not self._password or not self._server:
                logger.error("MT5_LOGIN/MT5_PASSWORD/MT5_SERVER are not fully configured.")
                return False
            kwargs = {"login": self._login, "password": self._password, "server": self._server}
            if self._terminal_path:
                kwargs["path"] = self._terminal_path
            if not mt5.initialize(**kwargs):
                logger.error("MT5 initialize() failed: %s", mt5.last_error())
                return False
            self._connected = True
            logger.info("MT5 terminal connected: login=%s server=%s", self._login, self._server)
            return True

    def disconnect(self) -> None:
        if _MT5_AVAILABLE and self._connected:
            mt5.shutdown()
        self._connected = False

    def _mark_disconnected(self) -> None:
        """Drop the cached connected flag so the *next* call re-attempts a
        fresh mt5.initialize() instead of assuming a dead IPC link is fine.

        Without this, a connection that drops after the first successful
        connect() (terminal closed, PC slept, IPC hiccup) stays marked
        connected forever, and this bridge silently keeps failing until
        someone manually restarts the process.
        """
        self._connected = False

    def _ensure_connected(self) -> None:
        if not self.connect():
            raise Mt5ConnectionError(
                "MetaTrader5 terminal is not connected. Check that the terminal is "
                "running and logged in, and that MT5_LOGIN/MT5_PASSWORD/MT5_SERVER "
                "are correct."
            )

    def account_info(self) -> Dict[str, Any]:
        self._ensure_connected()
        info = mt5.account_info()
        if info is None:
            self._mark_disconnected()
            raise Mt5ConnectionError(f"account_info() returned nothing: {mt5.last_error()}")
        return info._asdict()

    def positions(self) -> List[Dict[str, Any]]:
        self._ensure_connected()
        positions = mt5.positions_get()
        # positions_get() returns None on a call/IPC failure but an empty
        # tuple when there are genuinely zero open positions -- these must
        # not be treated the same, or a dropped connection silently looks
        # like "no open positions" instead of an honest error.
        if positions is None:
            self._mark_disconnected()
            raise Mt5ConnectionError(f"positions_get() failed: {mt5.last_error()}")
        return [normalize_position(p._asdict()) for p in positions]

    def history_deals(self, days: int = 365) -> List[Dict[str, Any]]:
        """Closed trades over the last `days` (default a year, so nothing recent
        is dropped by a short window). SL/TP are recovered from the opening
        orders and attached so R is computable."""
        self._ensure_connected()
        now = datetime.now()
        since = now - timedelta(days=days)
        deals = mt5.history_deals_get(since, now)
        if deals is None:
            self._mark_disconnected()
            raise Mt5ConnectionError(f"history_deals_get() failed: {mt5.last_error()}")
        # Opening orders carry the SL/TP the deal ledger lacks — map by position.
        sltp: Dict[Any, Dict[str, Any]] = {}
        try:
            orders = mt5.history_orders_get(since, now) or ()
            for o in orders:
                od = o._asdict()
                pid = od.get("position_id")
                sl, tp = od.get("sl") or 0, od.get("tp") or 0
                if pid and (sl or tp) and pid not in sltp:
                    sltp[pid] = {"sl": sl or None, "tp": tp or None}
        except Exception:
            pass
        return pair_deals_into_trades([d._asdict() for d in deals], sltp)

    def send_order(
        self,
        symbol: str,
        direction: str,
        lot_size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        self._ensure_connected()

        info = mt5.symbol_info(symbol)
        if info is None or not info.visible:
            if not mt5.symbol_select(symbol, True):
                raise Mt5ConnectionError(f"Symbol {symbol} is not available on this account/server.")

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            self._mark_disconnected()
            raise Mt5ConnectionError(f"No tick data available for {symbol}: {mt5.last_error()}")

        is_buy = direction == "long"
        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        price = tick.ask if is_buy else tick.bid

        base = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 90100,
            "comment": "ict-trading-os",
            "type_time": mt5.ORDER_TIME_GTC,
        }
        if stop_loss is not None:
            base["sl"] = float(stop_loss)
        if take_profit is not None:
            base["tp"] = float(take_profit)

        return self._send_deal(base, symbol, info)

    def _send_deal(self, base: Dict[str, Any], symbol: str, info=None) -> Dict[str, Any]:
        """order_send a deal, trying each supported filling mode until one is
        accepted. The broker rejects a wrong filling mode with retcode 10030
        (Unsupported filling) — which is why market/close/partial orders silently
        failed before. Used by open, close, and partial-close."""
        if info is None:
            info = mt5.symbol_info(symbol)
        last = None
        for fill in self._filling_modes(info):
            result = mt5.order_send({**base, "type_filling": fill})
            if result is None:
                self._mark_disconnected()
                raise Mt5ConnectionError(f"order_send() returned nothing: {mt5.last_error()}")
            last = result
            if result.retcode != mt5.TRADE_RETCODE_INVALID_FILL:
                return result._asdict()
        return last._asdict()

    @staticmethod
    def _filling_modes(info) -> List[int]:
        """Ordered list of order filling modes to try for a symbol.

        `symbol_info().filling_mode` is a bitmask of supported modes
        (bit0 = FOK, bit1 = IOC). We try the advertised ones first, then
        RETURN as a last resort (valid for market orders on most servers)."""
        modes: List[int] = []
        fm = getattr(info, "filling_mode", 0) or 0
        if fm & 1:  # SYMBOL_FILLING_FOK
            modes.append(mt5.ORDER_FILLING_FOK)
        if fm & 2:  # SYMBOL_FILLING_IOC
            modes.append(mt5.ORDER_FILLING_IOC)
        for fallback in (mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN):
            if fallback not in modes:
                modes.append(fallback)
        return modes

    def order_check(
        self,
        symbol: str,
        direction: str,
        lot_size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Validate an order WITHOUT placing it (mt5.order_check). Returns the
        retcode/comment the broker would give — used to diagnose why an order
        would be rejected (filling, stops, margin, market hours) safely."""
        self._ensure_connected()
        info = mt5.symbol_info(symbol)
        if info is None or not info.visible:
            if not mt5.symbol_select(symbol, True):
                raise Mt5ConnectionError(f"Symbol {symbol} is not available on this account/server.")
            info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise Mt5ConnectionError(f"No tick data available for {symbol}: {mt5.last_error()}")
        is_buy = direction == "long"
        base = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
            "price": tick.ask if is_buy else tick.bid,
            "deviation": 20,
            "magic": 90100,
            "comment": "ict-os-check",
            "type_time": mt5.ORDER_TIME_GTC,
        }
        if stop_loss is not None:
            base["sl"] = float(stop_loss)
        if take_profit is not None:
            base["tp"] = float(take_profit)
        checks = []
        for fill in self._filling_modes(info):
            res = mt5.order_check({**base, "type_filling": fill})
            entry = {"filling": fill, "retcode": getattr(res, "retcode", None),
                     "comment": getattr(res, "comment", None)}
            checks.append(entry)
            if entry["retcode"] == 0:  # 0 = would succeed
                return {"ok": True, "filling": fill, "comment": entry["comment"], "tried": checks}
        return {"ok": False, "tried": checks,
                "supported_filling_bitmask": getattr(info, "filling_mode", None),
                "price": base["price"], "volume_min": info.volume_min, "volume_step": info.volume_step}

    def close_position(self, ticket: int) -> Dict[str, Any]:
        self._ensure_connected()

        positions = mt5.positions_get(ticket=ticket)
        if positions is None:
            self._mark_disconnected()
            raise Mt5ConnectionError(f"positions_get() failed: {mt5.last_error()}")
        if not positions:
            raise Mt5ConnectionError(f"No open position with ticket {ticket}.")
        pos = positions[0]

        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            self._mark_disconnected()
            raise Mt5ConnectionError(f"No tick data available for {pos.symbol}: {mt5.last_error()}")

        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 90100,
            "comment": "ict-trading-os-close",
            "type_time": mt5.ORDER_TIME_GTC,
        }
        return self._send_deal(request, pos.symbol)

    # ── Market data ──────────────────────────────────────────────

    def _select_symbol(self, symbol: str) -> None:
        """Ensure a symbol is selected/visible in Market Watch before querying."""
        info = mt5.symbol_info(symbol)
        if info is None or not info.visible:
            if not mt5.symbol_select(symbol, True):
                raise Mt5ConnectionError(f"Symbol {symbol} is not available on this account/server.")

    def get_tick(self, symbol: str) -> Dict[str, Any]:
        """Live bid/ask/last for a symbol, from the broker's own feed."""
        self._ensure_connected()
        self._select_symbol(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            self._mark_disconnected()
            raise Mt5ConnectionError(f"No tick data for {symbol}: {mt5.last_error()}")
        return normalize_tick(symbol, tick._asdict())

    def get_candles(self, symbol: str, timeframe: str = "1h", count: int = 200) -> List[Dict[str, Any]]:
        """Historical OHLC candles for a symbol at the given timeframe."""
        self._ensure_connected()
        self._select_symbol(symbol)
        tf_name = _TIMEFRAME_NAMES.get(timeframe, "TIMEFRAME_H1")
        tf = getattr(mt5, tf_name)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, min(int(count), 5000))
        if rates is None:
            self._mark_disconnected()
            raise Mt5ConnectionError(f"copy_rates_from_pos() failed for {symbol}: {mt5.last_error()}")
        return [
            {
                "time": int(r["time"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": int(r["tick_volume"]),
            }
            for r in rates
        ]

    def symbol_spec(self, symbol: str) -> Dict[str, Any]:
        """Contract specification for a symbol (digits, contract size, ...)."""
        self._ensure_connected()
        self._select_symbol(symbol)
        info = mt5.symbol_info(symbol)
        if info is None:
            raise Mt5ConnectionError(f"symbol_info() returned nothing for {symbol}: {mt5.last_error()}")
        d = info._asdict()
        return {
            "symbol": symbol.upper(),
            "digits": d.get("digits"),
            "point": d.get("point"),
            "spread": d.get("spread"),
            "contract_size": d.get("trade_contract_size"),
            "volume_min": d.get("volume_min"),
            "volume_max": d.get("volume_max"),
            "volume_step": d.get("volume_step"),
            "currency_base": d.get("currency_base"),
            "currency_profit": d.get("currency_profit"),
            "trade_mode": d.get("trade_mode"),
            "filling_mode": d.get("filling_mode"),
            # Broker's real per-tick value in the ACCOUNT currency + tick size —
            # the exact basis for lot/risk sizing (no static approximation).
            "tick_value": d.get("trade_tick_value"),
            "tick_size": d.get("trade_tick_size"),
            "contract_size": d.get("trade_contract_size"),
        }

    def list_symbols(self) -> List[str]:
        """All tradable symbol names on this account/server."""
        self._ensure_connected()
        symbols = mt5.symbols_get()
        if symbols is None:
            self._mark_disconnected()
            raise Mt5ConnectionError(f"symbols_get() failed: {mt5.last_error()}")
        return [s.name for s in symbols]

    # ── Order & position management ──────────────────────────────

    def modify_sltp(
        self, ticket: int, stop_loss: Optional[float] = None, take_profit: Optional[float] = None
    ) -> Dict[str, Any]:
        """Modify the stop-loss / take-profit on an open position."""
        self._ensure_connected()
        positions = mt5.positions_get(ticket=ticket)
        if positions is None:
            self._mark_disconnected()
            raise Mt5ConnectionError(f"positions_get() failed: {mt5.last_error()}")
        if not positions:
            raise Mt5ConnectionError(f"No open position with ticket {ticket}.")
        pos = positions[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": pos.symbol,
            "position": ticket,
            "sl": float(stop_loss) if stop_loss is not None else pos.sl,
            "tp": float(take_profit) if take_profit is not None else pos.tp,
        }
        result = mt5.order_send(request)
        if result is None:
            self._mark_disconnected()
            raise Mt5ConnectionError(f"order_send() (modify) returned nothing: {mt5.last_error()}")
        return result._asdict()

    def partial_close(self, ticket: int, volume: float) -> Dict[str, Any]:
        """Close part of an open position (a smaller volume than the whole)."""
        self._ensure_connected()
        positions = mt5.positions_get(ticket=ticket)
        if positions is None:
            self._mark_disconnected()
            raise Mt5ConnectionError(f"positions_get() failed: {mt5.last_error()}")
        if not positions:
            raise Mt5ConnectionError(f"No open position with ticket {ticket}.")
        pos = positions[0]
        vol = float(volume)
        if vol <= 0 or vol > pos.volume:
            raise Mt5ConnectionError(
                f"Partial close volume {vol} must be > 0 and <= position volume {pos.volume}."
            )
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            self._mark_disconnected()
            raise Mt5ConnectionError(f"No tick data for {pos.symbol}: {mt5.last_error()}")
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": vol,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 90100,
            "comment": "ict-trading-os-partial",
            "type_time": mt5.ORDER_TIME_GTC,
        }
        return self._send_deal(request, pos.symbol)

    def place_pending(
        self, symbol: str, direction: str, order_kind: str, volume: float, price: float,
        stop_loss: Optional[float] = None, take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Place a pending limit/stop order (direction: long|short, kind: limit|stop)."""
        self._ensure_connected()
        self._select_symbol(symbol)
        type_name = _PENDING_TYPE_NAMES.get((direction, order_kind))
        if type_name is None:
            raise Mt5ConnectionError(f"Invalid pending order: {direction}/{order_kind}.")
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": float(volume),
            "type": getattr(mt5, type_name),
            "price": float(price),
            "deviation": 20,
            "magic": 90100,
            "comment": "ict-trading-os-pending",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        if stop_loss is not None:
            request["sl"] = float(stop_loss)
        if take_profit is not None:
            request["tp"] = float(take_profit)
        result = mt5.order_send(request)
        if result is None:
            self._mark_disconnected()
            raise Mt5ConnectionError(f"order_send() (pending) returned nothing: {mt5.last_error()}")
        return result._asdict()

    def pending_orders(self) -> List[Dict[str, Any]]:
        """List currently working pending orders."""
        self._ensure_connected()
        orders = mt5.orders_get()
        if orders is None:
            self._mark_disconnected()
            raise Mt5ConnectionError(f"orders_get() failed: {mt5.last_error()}")
        return [o._asdict() for o in orders]

    def cancel_pending(self, order_ticket: int) -> Dict[str, Any]:
        """Cancel a working pending order by its ticket."""
        self._ensure_connected()
        request = {"action": mt5.TRADE_ACTION_REMOVE, "order": int(order_ticket)}
        result = mt5.order_send(request)
        if result is None:
            self._mark_disconnected()
            raise Mt5ConnectionError(f"order_send() (cancel) returned nothing: {mt5.last_error()}")
        return result._asdict()
