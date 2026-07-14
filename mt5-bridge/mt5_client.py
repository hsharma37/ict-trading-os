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
        """Initialize the terminal and log in. Safe to call repeatedly."""
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
            raise Mt5ConnectionError(f"account_info() returned nothing: {mt5.last_error()}")
        return info._asdict()

    def positions(self) -> List[Dict[str, Any]]:
        self._ensure_connected()
        positions = mt5.positions_get()
        return [p._asdict() for p in positions] if positions else []

    def history_deals(self, days: int = 30) -> List[Dict[str, Any]]:
        self._ensure_connected()
        since = datetime.now() - timedelta(days=days)
        deals = mt5.history_deals_get(since, datetime.now())
        return [d._asdict() for d in deals] if deals else []

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
            raise Mt5ConnectionError(f"No tick data available for {symbol}.")

        is_buy = direction == "long"
        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        price = tick.ask if is_buy else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 90100,
            "comment": "ict-trading-os",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        if stop_loss is not None:
            request["sl"] = float(stop_loss)
        if take_profit is not None:
            request["tp"] = float(take_profit)

        result = mt5.order_send(request)
        if result is None:
            raise Mt5ConnectionError(f"order_send() returned nothing: {mt5.last_error()}")
        return result._asdict()

    def close_position(self, ticket: int) -> Dict[str, Any]:
        self._ensure_connected()

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            raise Mt5ConnectionError(f"No open position with ticket {ticket}.")
        pos = positions[0]

        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            raise Mt5ConnectionError(f"No tick data available for {pos.symbol}.")

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
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None:
            raise Mt5ConnectionError(f"order_send() (close) returned nothing: {mt5.last_error()}")
        return result._asdict()
