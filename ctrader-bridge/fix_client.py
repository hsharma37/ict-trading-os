"""
cTrader FIX 4.4 client — alternative transport to the Open API (protobuf)
client, for brokers/accounts that only expose FIX credentials.

Two sessions, exactly as Spotware documents them:

- PRICE session (SenderSubID=QUOTE): market data — tick subscriptions.
- TRADE session (SenderSubID=TRADE): orders, positions, security list.

No client id / secret / access token needed: authentication is the FIX
Logon with the account's FIX password (tags 553/554).

Honest capability notes vs the Open API client:
- FIX has NO historical-candle message. get_candles() aggregates live ticks
  into OHLC bars from the moment the bridge starts (documented limitation;
  charts warm up over time).
- FIX has NO deal-history query. history_deals() returns [] — the app's
  journal syncs positions/orders instead.
- SL/TP are carried as standard FIX protective orders (stop/limit siblings
  keyed to the position) rather than position-attached fields, because plain
  FIX 4.4 has no position-attach message.
"""
from __future__ import annotations

import logging
import socket
import ssl
import threading
import time
from collections import defaultdict, deque
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import simplefix
    _FIX_AVAILABLE = True
except ImportError:
    _FIX_AVAILABLE = False

RETCODE_DONE = 10009
RETCODE_PLACED = 10008
RETCODE_REJECTED = 10006

_UNITS_PER_LOT = 100000  # cTrader FIX OrderQty is in units (1 lot = 100k)

_TIMEFRAME_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400,
}


class CTraderConnectionError(RuntimeError):
    pass


class _FixSession:
    """One FIX 4.4 socket session with reader thread + heartbeat."""

    def __init__(self, name: str, host: str, port: int, use_ssl: bool,
                 sender_comp_id: str, sub_id: str, account: str, password: str,
                 target_sub_id: Optional[str] = None):
        self.name = name
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.sender_comp_id = sender_comp_id
        self.sub_id = sub_id
        self.target_sub_id = target_sub_id or sub_id
        self.account = account
        self.password = password
        self._sock: Optional[socket.socket] = None
        self._parser = simplefix.FixParser()
        self._send_seq = 1
        self._recv_seq = 1
        self._lock = threading.Lock()
        self._running = False
        self._logged_on = threading.Event()
        self.logon_error = ""
        self._handlers: List[Callable[[simplefix.FixMessage], None]] = []
        self._pending: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._pend_lock = threading.Lock()
        self.last_msg_time = 0.0

    # ── plumbing ─────────────────────────────────────────────────

    def add_handler(self, fn: Callable[[simplefix.FixMessage], None]) -> None:
        self._handlers.append(fn)

    def connect(self, timeout: float = 15.0) -> bool:
        raw = socket.create_connection((self.host, self.port), timeout=timeout)
        if self.use_ssl:
            ctx = ssl.create_default_context()
            self._sock = ctx.wrap_socket(raw, server_hostname=self.host)
        else:
            self._sock = raw
        self._sock.settimeout(1.0)
        self._running = True
        threading.Thread(target=self._reader, name=f"fix-{self.name}",
                         daemon=True).start()
        self._send_logon()
        ok = self._logged_on.wait(timeout=timeout)
        if ok:
            threading.Thread(target=self._heartbeat, name=f"fix-hb-{self.name}",
                             daemon=True).start()
        return ok

    def close(self) -> None:
        self._running = False
        try:
            if self._sock:
                self._send({35: "5"})  # Logout
                self._sock.close()
        except Exception:  # noqa: BLE001
            pass

    def _reader(self) -> None:
        while self._running and self._sock:
            try:
                data = self._sock.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                break
            self._parser.append_buffer(data)
            while True:
                try:
                    msg = self._parser.get_message()
                except Exception as e:  # noqa: BLE001
                    logger.warning("FIX %s parse error: %s; raw=%r",
                                   self.name, e, data[:400])
                    break
                if msg is None:
                    break
                self.last_msg_time = time.time()
                self._on_message(msg)
        self._logged_on.clear()

    def _on_message(self, msg: simplefix.FixMessage) -> None:
        mt = (msg.get(35) or b"").decode()
        try:
            seq = int((msg.get(34) or b"0").decode())
            if seq:
                self._recv_seq = seq + 1
        except (ValueError, TypeError):
            pass
        if mt == "0":      # Heartbeat
            return
        if mt == "1":      # TestRequest -> Heartbeat echo
            self._send({35: "0", 112: (msg.get(112) or b"").decode()})
            return
        if mt == "2":      # ResendRequest -> SequenceReset gap fill
            self._send({35: "4", 36: str(self._send_seq), 123: "Y"})
            return
        if mt == "4":      # SequenceReset
            return
        if mt == "A":      # Logon ack
            self._logged_on.set()
        if mt == "5":      # Logout
            self.logon_error = (msg.get(58) or b"").decode() or "server sent Logout"
        if mt in ("j", "3"):  # Business/Session Reject
            logger.warning("FIX %s reject: %s", self.name,
                           (msg.get(58) or msg.get(371) or b"").decode(errors="replace"))
        for fn in self._handlers:
            try:
                fn(msg)
            except Exception:  # noqa: BLE001
                logger.exception("FIX %s handler error", self.name)

    def _heartbeat(self) -> None:
        while self._running and self._logged_on.is_set():
            time.sleep(20)
            if self._running:
                self._send({35: "0"})

    def _encode(self, fields: Dict[int, str], poss_dup: bool = False) -> bytes:
        m = simplefix.FixMessage()
        m.append_pair(8, "FIX.4.4")
        # MsgType must be the 3rd field; the rest of the standard header
        # follows, then the body (cServer rejects out-of-order headers).
        items = list(fields.items())
        mt = next((v for t, v in items if t == 35), None)
        if mt is not None:
            m.append_pair(35, mt)
        m.append_pair(49, self.sender_comp_id)
        m.append_pair(56, "cServer")
        m.append_pair(50, self.sub_id)
        m.append_pair(57, self.target_sub_id)
        m.append_pair(34, str(self._send_seq))
        m.append_pair(52, time.strftime("%Y%m%d-%H:%M:%S", time.gmtime()))
        if poss_dup:
            m.append_pair(43, "Y")
        for tag, val in items:
            if tag != 35:
                m.append_pair(tag, val)
        return m.encode()

    def _send(self, fields: Dict[int, str]) -> None:
        with self._lock:
            data = self._encode(fields)
            try:
                self._sock.sendall(data)
                self._send_seq += 1
            except OSError as e:
                self._logged_on.clear()
                raise CTraderConnectionError(f"FIX {self.name} send failed: {e}")

    def _send_raw(self, msg_type_tag: int, msg_type: str, body: str) -> None:
        """Send a message whose body is pre-encoded `tag=val<SOH>...` (needed
        when the same tag repeats, e.g. market-data entry types)."""
        with self._lock:
            m = simplefix.FixMessage()
            m.append_pair(8, "FIX.4.4")
            m.append_pair(msg_type_tag, msg_type)
            m.append_pair(49, self.sender_comp_id)
            m.append_pair(56, "cServer")
            m.append_pair(50, self.sub_id)
            m.append_pair(57, self.target_sub_id)
            m.append_pair(34, str(self._send_seq))
            m.append_pair(52, time.strftime("%Y%m%d-%H:%M:%S", time.gmtime()))
            for pair in body.split("\x01"):
                tag, _, val = pair.partition("=")
                m.append_pair(int(tag), val)
            try:
                self._sock.sendall(m.encode())
                self._send_seq += 1
            except OSError as e:
                self._logged_on.clear()
                raise CTraderConnectionError(f"FIX {self.name} send failed: {e}")

    def _send_logon(self) -> None:
        self._send({35: "A", 98: "0", 108: "30", 141: "Y",
                    553: self.account, 554: self.password})

    # ── request/response correlation ──────────────────────────────

    def expect(self, key: Tuple[str, str]) -> Dict[str, Any]:
        """Register interest in a response carrying (tag35, correlation id)."""
        box = {"event": threading.Event(), "messages": []}
        with self._pend_lock:
            self._pending[key] = box
        return box

    def dispatch(self, key: Tuple[str, str], msg: simplefix.FixMessage) -> bool:
        with self._pend_lock:
            box = self._pending.get(key)
        if not box:
            return False
        box["messages"].append(msg)
        box["event"].set()
        return True

    def done(self, key: Tuple[str, str]) -> None:
        with self._pend_lock:
            self._pending.pop(key, None)


# ──────────────────────────────────────────────────────────────────
# Public client — same interface as CTraderClient (Open API version)
# ──────────────────────────────────────────────────────────────────


class CTraderFixClient:
    """Drop-in replacement for CTraderClient over cTrader FIX 4.4."""

    def __init__(self, host: str, ssl_port: int, plain_port: int,
                 sender_comp_id: str, account: str, password: str,
                 use_ssl: bool = True, host_type: str = "demo"):
        self._host = host
        self._port = ssl_port if use_ssl else plain_port
        self._use_ssl = use_ssl
        self._sender_comp_id = sender_comp_id
        self._account = account
        self._password = password
        self._host_type = host_type
        self._lock = threading.Lock()
        self._started = False
        self._last_error = "not attempted yet"
        self._ready = threading.Event()

        self._price: Optional[_FixSession] = None
        self._trade: Optional[_FixSession] = None

        self._req_seq = int(time.time()) % 100000
        self._spots: Dict[str, Tuple[float, float, float]] = {}  # sym -> bid,ask,ts
        self._symbols: List[str] = []
        self._sym_id_by_name: Dict[str, str] = {}   # "EURUSD" -> "1"
        self._sym_name_by_id: Dict[str, str] = {}   # "1" -> "EURUSD"
        self._sym_digits: Dict[str, int] = {}       # "1" -> 5
        self._candles: Dict[Tuple[str, str], Deque[Dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=2000))
        self._positions_cache: List[Dict[str, Any]] = []
        self._clord_map: Dict[str, Dict[str, Any]] = {}  # ClOrdID -> order ctx

    # ── lifecycle ────────────────────────────────────────────────

    def available(self) -> bool:
        return _FIX_AVAILABLE

    def is_connected(self) -> bool:
        return self._ready.is_set()

    def connection_status(self) -> Dict[str, Any]:
        ok = self.connect()
        return {
            "connected": ok,
            "package_available": _FIX_AVAILABLE,
            "login": int(self._account) if self._account.isdigit() else None,
            "server": f"ctrader-fix-{self._host_type}",
            "reason": "connected" if ok else self._last_error,
        }

    def connect(self) -> bool:
        if not _FIX_AVAILABLE:
            self._last_error = ("simplefix package not installed. "
                                "Run `pip install -r requirements.txt`.")
            return False
        if self._ready.is_set():
            return True
        with self._lock:
            if self._ready.is_set():
                return True
            missing = [n for n, v in (("CT_FIX_HOST", self._host),
                                      ("CT_FIX_PASSWORD", self._password),
                                      ("CT_FIX_SENDER_COMP_ID", self._sender_comp_id),
                                      ("CT_ACCOUNT_ID", self._account)) if not v]
            if missing:
                self._last_error = "Missing FIX config: " + ", ".join(missing)
                logger.error(self._last_error)
                return False
            try:
                self._start()
            except Exception as e:  # noqa: BLE001
                self._last_error = f"FIX connect failed: {e}"
                logger.error(self._last_error)
                return False
        if self._ready.wait(timeout=30):
            self._last_error = ""
            logger.info("cTrader FIX logged on: account=%s host=%s:%s",
                        self._account, self._host, self._port)
            return True
        self._last_error = self._last_error if self._last_error != "not attempted yet" \
            else "Timed out waiting for FIX Logon ack (30s)."
        logger.error("FIX logon did not complete: %s", self._last_error)
        return False

    def _start(self) -> None:
        def boot():
            try:
                price = _FixSession("price", self._host, self._port, self._use_ssl,
                                    self._sender_comp_id, "QUOTE",
                                    self._account, self._password)
                if not price.connect():
                    self._last_error = f"price session logon failed: {price.logon_error or 'timeout'}"
                    return
                trade = _FixSession("trade", self._host, self._port, self._use_ssl,
                                    self._sender_comp_id, "TRADE",
                                    self._account, self._password,
                                    target_sub_id="QUOTE")
                if not trade.connect():
                    self._last_error = f"trade session logon failed: {trade.logon_error or 'timeout'}"
                    return
                price.add_handler(self._on_price_msg)
                trade.add_handler(self._on_trade_msg)
                self._price = price
                self._trade = trade
                self._ready.set()
                try:
                    self.list_symbols()
                except Exception:  # noqa: BLE001
                    pass  # symbol list is warm-up; failure isn't fatal
            except Exception as e:  # noqa: BLE001
                self._last_error = f"FIX connect failed: {e}"
        threading.Thread(target=boot, name="fix-boot", daemon=True).start()

    def _ensure_connected(self) -> None:
        if not self.connect():
            raise CTraderConnectionError(self._last_error)

    def _sid(self, symbol: str) -> str:
        name = symbol.upper()
        if not self._sym_id_by_name:
            self.list_symbols()
        sid = self._sym_id_by_name.get(name)
        if not sid:
            raise CTraderConnectionError(f"Unknown symbol {symbol}.")
        return sid

    def _next_id(self, prefix: str) -> str:
        self._req_seq += 1
        return f"{prefix}-{int(time.time())}-{self._req_seq}"

    # ── message handlers ─────────────────────────────────────────

    def _on_price_msg(self, msg) -> None:
        mt = (msg.get(35) or b"").decode()
        if mt in ("W", "X"):  # snapshot / incremental refresh
            sym_id = (msg.get(55) or b"").decode()
            sym = self._sym_name_by_id.get(sym_id, sym_id)
            bid, ask = self._spots.get(sym, (0.0, 0.0, 0.0))[:2]
            ts = time.time()
            # group 268/269/270: NoMDEntries / MDEntryType / MDEntryPx
            try:
                count = int((msg.get(268) or b"0").decode())
            except ValueError:
                count = 0
            for i in range(1, max(count, 1) + 1):
                ty = msg.get(269, nth=i)
                px = msg.get(270, nth=i)
                if not (ty and px):
                    if count:
                        continue
                    break
                if ty == b"0":
                    bid = float(px.decode())
                elif ty == b"1":
                    ask = float(px.decode())
            if bid or ask:
                self._spots[sym] = (bid, ask, ts)
                self._aggregate(sym, bid, ask, ts)
            req_id = (msg.get(262) or b"").decode()
            if req_id:
                self._price.dispatch(("W", req_id), msg)

    def _on_trade_msg(self, msg) -> None:
        mt = (msg.get(35) or b"").decode()
        if mt == "y":  # SecurityList
            try:
                n = int((msg.get(146) or b"0").decode())
            except ValueError:
                n = 0
            for i in range(1, n + 1):
                sid = msg.get(55, nth=i)
                name = msg.get(1007, nth=i)
                digits = msg.get(1008, nth=i)
                if not (sid and name):
                    continue
                sid, name = sid.decode(), name.decode()
                self._sym_id_by_name[name.upper()] = sid
                self._sym_name_by_id[sid] = name.upper()
                if digits:
                    try:
                        self._sym_digits[sid] = int(digits.decode())
                    except ValueError:
                        pass
            self._symbols = sorted(self._sym_id_by_name)
            req_id = (msg.get(320) or b"").decode()
            if req_id:
                self._trade.dispatch(("y", req_id), msg)
        elif mt == "AP":  # PositionReport
            req_id = (msg.get(710) or b"").decode()
            if req_id:
                self._trade.dispatch(("AP", req_id), msg)
        elif mt == "8":  # ExecutionReport
            cl = (msg.get(11) or b"").decode()
            if cl:
                self._trade.dispatch(("8", cl), msg)

    # ── market data ──────────────────────────────────────────────

    def _aggregate(self, sym: str, bid: float, ask: float, ts: float) -> None:
        mid = (bid + ask) / 2 if bid and ask else bid or ask
        for tf, secs in _TIMEFRAME_SECONDS.items():
            bucket = int(ts // secs) * secs
            dq = self._candles[(sym, tf)]
            if dq and dq[-1]["time"] == bucket:
                bar = dq[-1]
                bar["high"] = max(bar["high"], mid)
                bar["low"] = min(bar["low"], mid)
                bar["close"] = mid
                bar["volume"] += 1
            else:
                dq.append({"time": bucket, "open": mid, "high": mid,
                           "low": mid, "close": mid, "volume": 1})

    def _subscribe(self, symbol: str, timeout: float = 10.0) -> Tuple[float, float, float]:
        symbol = symbol.upper()
        if symbol in self._spots:
            return self._spots[symbol]
        self._ensure_connected()
        if not self._sym_id_by_name:
            self.list_symbols()
        sid = self._sym_id_by_name.get(symbol)
        if not sid:
            raise CTraderConnectionError(f"Unknown symbol {symbol}.")
        req_id = self._next_id("md")
        box = self._price.expect(("W", req_id))
        # Repeating tags can't go in the dict helper; encode manually.
        # NB: cTrader FIX wants the NUMERIC symbol id in tag 55.
        body = (f"262={req_id}\x01263=1\x01264=1\x01267=2\x01269=0\x01269=1"
                f"\x01146=1\x0155={sid}")
        self._price._send_raw(35, "V", body)
        box["event"].wait(timeout)
        self._price.done(("W", req_id))
        spot = self._spots.get(symbol)
        if not spot:
            raise CTraderConnectionError(f"No quote received for {symbol}.")
        return spot

    def get_tick(self, symbol: str) -> Dict[str, Any]:
        """Live tick in the exact shape the app expects (mirrors the MT5
        bridge's normalize_tick: price=mid, bid, ask, spread, ISO time)."""
        symbol = symbol.upper()
        bid, ask, ts = self._subscribe(symbol)
        mid = round((bid + ask) / 2, 8) if (bid and ask) else (bid or ask or 0)
        return {
            "symbol": symbol,
            "price": mid,
            "bid": bid,
            "ask": ask,
            "last": mid,
            "spread": round(ask - bid, 8) if (bid and ask) else 0,
            "volume": 0,
            "time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)) if ts else None,
            "source": "ctrader",
        }

    def get_candles(self, symbol: str, timeframe: str = "1h",
                    count: int = 200) -> List[Dict[str, Any]]:
        """Aggregated from live ticks since bridge start (FIX carries no
        historical bars — see module docstring)."""
        symbol = symbol.upper()
        self._subscribe(symbol)
        bars = list(self._candles.get((symbol, timeframe), []))
        return bars[-min(int(count), 2000):]

    # ── symbols / spec ───────────────────────────────────────────

    def list_symbols(self) -> List[str]:
        self._ensure_connected()
        if self._symbols:
            return list(self._symbols)
        req_id = self._next_id("sec")
        box = self._trade.expect(("y", req_id))
        self._trade._send({35: "x", 320: req_id, 559: "0"})
        box["event"].wait(15)
        self._trade.done(("y", req_id))
        return list(self._symbols)

    def _digits(self, price: float) -> int:
        s = f"{price:.10f}".rstrip("0")
        return max(len(s.split(".")[1]) if "." in s else 0, 1)

    def symbol_spec(self, symbol: str) -> Dict[str, Any]:
        symbol = symbol.upper()
        bid, ask, _ = self._subscribe(symbol)
        sid = self._sym_id_by_name.get(symbol)
        digits = self._sym_digits.get(sid, self._digits(bid))
        return {
            "symbol": symbol,
            "digits": digits,
            "point": 10 ** -digits,
            "spread": round(ask - bid, digits) if bid and ask else None,
            "contract_size": _UNITS_PER_LOT,
            "volume_min": 0.01,
            "volume_max": None,
            "volume_step": 0.01,
            "currency_base": symbol[:3] if len(symbol) >= 6 else None,
            "currency_profit": symbol[3:6] if len(symbol) >= 6 else None,
            "trade_mode": None,   # FIX carries no trading-mode field
            "filling_mode": None,
            "tick_value": None,
            "tick_size": None,
        }

    # ── account / positions ──────────────────────────────────────

    def positions(self) -> List[Dict[str, Any]]:
        self._ensure_connected()
        req_id = self._next_id("pos")
        box = self._trade.expect(("AP", req_id))
        self._trade._send({35: "AN", 710: req_id, 724: "0", 263: "0"})
        box["event"].wait(15)
        self._trade.done(("AP", req_id))
        out = []
        for msg in box["messages"]:
            sym = self._sym_name_by_id.get((msg.get(55) or b"").decode(),
                                           (msg.get(55) or b"").decode())
            try:
                long_qty = float((msg.get(704) or b"0").decode())
                short_qty = float((msg.get(705) or b"0").decode())
            except (TypeError, ValueError):
                long_qty = short_qty = 0.0
            qty = long_qty or short_qty
            if not qty:
                continue
            out.append({
                "ticket": (msg.get(721) or b"").decode(),
                "symbol": sym,
                "direction": "long" if long_qty else "short",
                "volume": round(qty / _UNITS_PER_LOT, 4),
                "price_open": float((msg.get(730) or b"0").decode()),
                "profit": None,
                "sl": None, "tp": None,
            })
        self._positions_cache = out
        return out

    def account_info(self) -> Dict[str, Any]:
        """FIX carries no balance query on standard sessions; report what the
        session knows and mark the rest None rather than inventing numbers."""
        self._ensure_connected()
        return {
            "balance": None,
            "equity": None,
            "margin": None,
            "margin_free": None,
            "margin_level": None,
            "currency": None,
            "login": int(self._account) if self._account.isdigit() else None,
            "server": f"ctrader-fix-{self._host_type}",
        }

    def history_deals(self, days: int = 365) -> List[Dict[str, Any]]:
        """FIX has no deal-history message. Empty list, honestly."""
        return []

    def history_summary(self, days: int = 365) -> Dict[str, Any]:
        info = self.account_info()
        return {
            "days": days, "deal_count": None, "trade_deal_count": None,
            "closed_trades": 0, "deposits": None, "realized_pnl": None,
            "balance": info.get("balance"), "equity": info.get("equity"),
        }

    # ── orders ───────────────────────────────────────────────────

    def send_order(self, symbol: str, direction: str, lot_size: float,
                   stop_loss: Optional[float] = None,
                   take_profit: Optional[float] = None) -> Dict[str, Any]:
        """Market order via FIX NewOrderSingle. SL/TP are placed as sibling
        protective stop/limit orders (standard FIX — no position attach)."""
        self._ensure_connected()
        symbol = symbol.upper()
        bid, ask, _ = self._subscribe(symbol)
        is_buy = direction == "long"
        ref = ask if is_buy else bid
        for label, px, want_above in (("stop_loss", stop_loss, not is_buy),
                                      ("take_profit", take_profit, is_buy)):
            if px is not None:
                bad = (float(px) <= ref) if want_above else (float(px) >= ref)
                if bad:
                    raise CTraderConnectionError(
                        f"{label} {px} is on the wrong side of price {ref} for a {direction}.")
        qty = int(round(lot_size * _UNITS_PER_LOT))
        cl = self._next_id("ord")
        box = self._trade.expect(("8", cl))
        self._trade._send({35: "D", 11: cl, 55: self._sid(symbol), 54: "1" if is_buy else "2",
                           60: time.strftime("%Y%m%d-%H:%M:%S", time.gmtime()),
                           40: "1", 38: str(qty)})
        box["event"].wait(20)
        self._trade.done(("8", cl))
        result = self._exec_report_to_result(box["messages"], cl)
        if result["retcode"] == RETCODE_DONE:
            pos_ticket = result.get("position_id") or result.get("order")
            if stop_loss is not None:
                self._place_protection(symbol, direction, qty, "stop", float(stop_loss),
                                       pos_ticket)
            if take_profit is not None:
                self._place_protection(symbol, direction, qty, "limit", float(take_profit),
                                       pos_ticket)
        return result

    def _place_protection(self, symbol: str, direction: str, qty: int,
                          kind: str, price: float, pos_ticket) -> None:
        """Sibling protective order: opposite side, stop or limit."""
        is_buy = direction == "long"
        cl = self._next_id(kind)
        fields = {35: "D", 11: cl, 55: self._sid(symbol), 54: "2" if is_buy else "1",
                  60: time.strftime("%Y%m%d-%H:%M:%S", time.gmtime()),
                  38: str(qty)}
        if kind == "stop":
            fields[40] = "3"
            fields[99] = str(price)
        else:
            fields[40] = "2"
            fields[44] = str(price)
        box = self._trade.expect(("8", cl))
        self._trade._send(fields)
        box["event"].wait(15)
        self._trade.done(("8", cl))
        self._clord_map[cl] = {"kind": kind, "position": pos_ticket,
                               "symbol": symbol, "price": price}

    def _exec_report_to_result(self, messages, cl: str) -> Dict[str, Any]:
        if not messages:
            return {"retcode": RETCODE_REJECTED, "comment": "no ExecutionReport received",
                    "order": None, "deal": None, "price": None}
        msg = messages[-1]
        ord_status = (msg.get(39) or b"").decode()
        text = (msg.get(58) or b"").decode()
        if ord_status == "8":  # Rejected
            return {"retcode": RETCODE_REJECTED, "comment": text or "rejected",
                    "order": None, "deal": None, "price": None}
        filled = ord_status == "2"
        px = msg.get(6) or msg.get(31)  # AvgPx / LastPx
        return {
            "retcode": RETCODE_DONE if filled else RETCODE_PLACED,
            "order": (msg.get(37) or b"").decode() or None,
            "deal": (msg.get(17) or b"").decode() or None,
            "position_id": (msg.get(37) or b"").decode() or None,
            "price": float(px.decode()) if px else None,
            "volume": None,
            "comment": text or ("filled" if filled else "placed"),
        }

    def order_check(self, symbol: str, direction: str, lot_size: float,
                    stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None) -> Dict[str, Any]:
        """Validate WITHOUT placing: live quote present, volume sane, SL/TP on
        the right side. Mirrors the Open API version's return shape."""
        try:
            symbol = symbol.upper()
            bid, ask, _ = self._subscribe(symbol)
            ref = ask if direction == "long" else bid
            problems = []
            if lot_size < 0.01:
                problems.append(f"volume {lot_size} lots below min 0.01 lots")
            for label, px, want_above in (("stop_loss", stop_loss, direction == "short"),
                                          ("take_profit", take_profit, direction == "long")):
                if px is not None:
                    bad = (float(px) <= ref) if want_above else (float(px) >= ref)
                    if bad:
                        problems.append(f"{label} {px} is on the wrong side of price {ref}")
            if problems:
                return {"ok": False, "comment": "; ".join(problems), "expected_margin": None}
            return {"ok": True, "filling": "market", "comment": "would be accepted",
                    "expected_margin": None, "price": ref}
        except CTraderConnectionError as e:
            return {"ok": False, "comment": str(e)}

    def close_position(self, ticket: int) -> Dict[str, Any]:
        pos = self._find_position(ticket)
        return self._close(ticket, int(round(pos["volume"] * _UNITS_PER_LOT)))

    def partial_close(self, ticket: int, volume: float) -> Dict[str, Any]:
        pos = self._find_position(ticket)
        qty = int(round(volume * _UNITS_PER_LOT))
        full = int(round(pos["volume"] * _UNITS_PER_LOT))
        if qty <= 0 or qty > full:
            raise CTraderConnectionError(
                f"Partial close volume {volume} lots must be > 0 and <= {pos['volume']} lots.")
        return self._close(ticket, qty)

    def _close(self, ticket: int, qty: int) -> Dict[str, Any]:
        pos = self._find_position(ticket)
        opposite = "2" if pos["direction"] == "long" else "1"
        cl = self._next_id("cls")
        box = self._trade.expect(("8", cl))
        self._trade._send({35: "D", 11: cl, 55: self._sid(pos["symbol"]), 54: opposite,
                           60: time.strftime("%Y%m%d-%H:%M:%S", time.gmtime()),
                           40: "1", 38: str(qty)})
        box["event"].wait(20)
        self._trade.done(("8", cl))
        return self._exec_report_to_result(box["messages"], cl)

    def _find_position(self, ticket: int) -> Dict[str, Any]:
        for p in self.positions():
            if str(p["ticket"]) == str(ticket):
                return p
        raise CTraderConnectionError(f"No open position with ticket {ticket}.")

    def modify_sltp(self, ticket: int, stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None) -> Dict[str, Any]:
        """Replace the sibling protective orders for a position."""
        pos = self._find_position(ticket)
        qty = int(round(pos["volume"] * _UNITS_PER_LOT))
        for cl, ctx in list(self._clord_map.items()):
            if str(ctx.get("position")) == str(ticket):
                self._trade._send({35: "F", 11: self._next_id("cxl"), 41: cl,
                                   55: ctx["symbol"], 54: "2" if ctx["kind"] == "stop" else "1",
                                   60: time.strftime("%Y%m%d-%H:%M:%S", time.gmtime())})
                del self._clord_map[cl]
        if stop_loss is not None:
            self._place_protection(pos["symbol"], pos["direction"], qty, "stop",
                                   float(stop_loss), ticket)
        if take_profit is not None:
            self._place_protection(pos["symbol"], pos["direction"], qty, "limit",
                                   float(take_profit), ticket)
        return {"retcode": RETCODE_DONE, "comment": "protection updated"}

    def place_pending(self, symbol: str, direction: str, order_kind: str,
                      lot_size: float, price: float,
                      stop_loss: Optional[float] = None,
                      take_profit: Optional[float] = None) -> Dict[str, Any]:
        self._ensure_connected()
        symbol = symbol.upper()
        qty = int(round(lot_size * _UNITS_PER_LOT))
        is_buy = direction == "long"
        kind = (order_kind or "limit").lower()
        cl = self._next_id("pnd")
        fields = {35: "D", 11: cl, 55: self._sid(symbol), 54: "1" if is_buy else "2",
                  60: time.strftime("%Y%m%d-%H:%M:%S", time.gmtime()), 38: str(qty)}
        if kind == "stop":
            fields[40] = "3"
            fields[99] = str(price)
        else:
            fields[40] = "2"
            fields[44] = str(price)
        box = self._trade.expect(("8", cl))
        self._trade._send(fields)
        box["event"].wait(20)
        self._trade.done(("8", cl))
        return self._exec_report_to_result(box["messages"], cl)

    def pending_orders(self) -> List[Dict[str, Any]]:
        return [dict(v, cl_ord_id=k) for k, v in self._clord_map.items()]

    def cancel_pending(self, order_ticket: int) -> Dict[str, Any]:
        for cl, ctx in list(self._clord_map.items()):
            if str(ctx.get("position")) == str(order_ticket) or cl == str(order_ticket):
                self._trade._send({35: "F", 11: self._next_id("cxl"), 41: cl,
                                   55: ctx["symbol"],
                                   54: "1",
                                   60: time.strftime("%Y%m%d-%H:%M:%S", time.gmtime())})
                del self._clord_map[cl]
                return {"retcode": RETCODE_DONE, "comment": "cancel sent"}
        raise CTraderConnectionError(f"No known pending order {order_ticket}.")

    def write_levels_file(self, symbol: str, zones: List[Dict], meta: Dict) -> str:
        raise CTraderConnectionError(
            "Chart drawing on a cTrader terminal is not supported by this bridge. "
            "Candle/level DATA is unaffected — the app's own charts render identically.")
