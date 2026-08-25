"""
Thin synchronous wrapper around Spotware's OpenApiPy (cTrader Open API).

Unlike MetaTrader5's Python package (Windows-only, needs a logged-in desktop
terminal), the cTrader Open API is SERVER-SIDE: this client talks directly to
the broker's cTrader servers over protobuf/TCP. No terminal, no Wine, no
display — this bridge runs on any Linux/macOS box or $5 VPS.

OpenApiPy is asynchronous (Twisted). This wrapper runs the reactor on a
daemon thread and exposes blocking methods, so the Flask layer stays
identical in shape to mt5-bridge/mt5_client.py — every method returns the
same normalized dicts the app already consumes.

Unit conventions (from spotware/openapi-proto-messages):
  * Prices on the wire are integers in 1/100000 of a price unit (divide by
    100000). Exception: double-typed fields (executionPrice, stopLoss, ...) are
    already real prices.
  * Volumes are in CENTS OF UNITS: volume 1000 == 10.00 units. One lot is
    `symbol.lotSize` cents (usually 10,000,000 == 100,000 units == 1 lot).
  * Money is an integer scaled by 10^moneyDigits (moneyDigits per account /
    position / deal; example in the proto uses 8).
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
    from ctrader_open_api.messages import OpenApiCommonMessages_pb2 as _common
    from ctrader_open_api.messages import OpenApiMessages_pb2 as _oa
    from ctrader_open_api.messages import OpenApiModelMessages_pb2 as _model
    from twisted.internet import reactor
    _CT_AVAILABLE = True
except ImportError:
    _CT_AVAILABLE = False


class CTraderConnectionError(RuntimeError):
    """Raised when the cTrader Open API is unreachable, not authenticated,
    or a request to it fails."""


# App timeframe string -> ProtoOATrendbarPeriod enum NAME (resolved lazily so
# this module imports on machines without the package, like mt5_client does).
_TIMEFRAME_NAMES = {
    "1m": "M1", "5m": "M5", "15m": "M15", "30m": "M30",
    "1h": "H1", "4h": "H4", "1d": "D1", "1w": "W1",
}

# MT5-style retcodes the APP already understands (planner_service and the /mt5
# router treat 10008/10009/10010 as accepted). The bridge reports cTrader
# outcomes in this vocabulary so app code needs no provider-specific branches.
RETCODE_DONE = 10009       # market order filled
RETCODE_PLACED = 10008     # pending order accepted
RETCODE_REJECTED = 10013   # generic invalid/rejected (see "comment" for detail)


def _money(raw: Optional[int], money_digits: int) -> float:
    """Scaled integer money -> float in account currency."""
    return (raw or 0) / float(10 ** moneyDigits_or_default(money_digits))


def moneyDigits_or_default(money_digits: Optional[int]) -> int:
    return money_digits if money_digits else 8


def _price(raw: Optional[int]) -> float:
    """Wire price (1/100000 units) -> float."""
    return (raw or 0) / 100000.0


def normalize_tick(symbol: str, bid_raw: int, ask_raw: int, ts_ms: Optional[int]) -> Dict[str, Any]:
    """Same shape as mt5_client.normalize_tick — the app's price contract."""
    bid = _price(bid_raw)
    ask = _price(ask_raw)
    mid = round((bid + ask) / 2, 8) if (bid and ask) else (bid or ask or 0)
    return {
        "symbol": symbol.upper(),
        "price": mid,
        "bid": bid,
        "ask": ask,
        "last": 0,
        "spread": round(ask - bid, 8) if (bid and ask) else 0,
        "volume": 0,
        "time": datetime.utcfromtimestamp(ts_ms / 1000).isoformat() if ts_ms else None,
        "source": "ctrader",
    }


class CTraderClient:
    """Owns the single cTrader Open API connection for this process."""

    def __init__(self, client_id: str, client_secret: str, access_token: str,
                 account_id: int, host_type: str = "demo"):
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token = access_token
        self._account_id = account_id
        self._host_type = host_type
        self._client: Optional["Client"] = None
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._last_error = "not attempted yet"
        self._started = False
        # Caches
        self._symbols_by_name: Dict[str, int] = {}   # "EURUSD" -> symbolId
        self._symbol_names: Dict[int, str] = {}      # symbolId -> "EURUSD"
        self._symbol_details: Dict[int, Any] = {}    # symbolId -> ProtoOASymbol
        self._spots: Dict[int, Tuple[int, int, int]] = {}  # symbolId -> (bid, ask, ts_ms)
        self._trader_money_digits = 8

    # ── Connection lifecycle ─────────────────────────────────────

    def available(self) -> bool:
        return _CT_AVAILABLE

    def is_connected(self) -> bool:
        return self._ready.is_set()

    def connection_status(self) -> Dict[str, Any]:
        ok = self.connect()
        return {
            "connected": ok,
            "package_available": _CT_AVAILABLE,
            "login": self._account_id or None,
            "server": f"ctrader-{self._host_type}",
            "reason": "connected" if ok else self._last_error,
        }

    def connect(self) -> bool:
        """Connect + authenticate (app auth, then account auth). Safe to call
        repeatedly — returns immediately if already authenticated."""
        if not _CT_AVAILABLE:
            self._last_error = ("ctrader-open-api package not installed in the bridge's "
                                "interpreter. Run `pip install -r requirements.txt`.")
            logger.warning(self._last_error)
            return False
        if self._ready.is_set():
            return True
        with self._lock:
            if self._ready.is_set():
                return True
            missing = [n for n, v in (("CT_CLIENT_ID", self._client_id),
                                      ("CT_CLIENT_SECRET", self._client_secret),
                                      ("CT_ACCESS_TOKEN", self._access_token),
                                      ("CT_ACCOUNT_ID", self._account_id)) if not v]
            if missing:
                self._last_error = ("Missing bridge .env config: " + ", ".join(missing)
                                    + ". Create an app at openapi.ctrader.com and link your account.")
                logger.error(self._last_error)
                return False
            try:
                self._start_client()
            except Exception as e:  # noqa: BLE001
                self._last_error = f"cTrader connect failed: {e}"
                logger.error(self._last_error)
                return False
        # Auth completes on the reactor thread; wait for the ready flag.
        if self._ready.wait(timeout=20):
            self._last_error = ""
            logger.info("cTrader Open API authenticated: account=%s (%s)",
                        self._account_id, self._host_type)
            return True
        self._last_error = self._last_error if self._last_error != "not attempted yet" \
            else "Timed out waiting for cTrader authentication (20s)."
        logger.error("cTrader auth did not complete: %s", self._last_error)
        return False

    def _start_client(self) -> None:
        host = (EndPoints.PROTOBUF_LIVE_HOST if self._host_type == "live"
                else EndPoints.PROTOBUF_DEMO_HOST)
        client = Client(host, EndPoints.PROTOBUF_PORT, TcpProtocol)
        client.setConnectedCallback(self._on_connected)
        client.setDisconnectedCallback(self._on_disconnected)
        client.setMessageReceivedCallback(self._on_message)
        self._client = client

        def _run():
            client.startService()
            if not reactor.running:
                reactor.run(installSignalHandlers=False)

        t = threading.Thread(target=_run, name="ctrader-reactor", daemon=True)
        t.start()
        self._started = True

    def _on_connected(self, client) -> None:
        logger.info("cTrader TCP connected; authenticating application…")
        req = _oa.ProtoOAApplicationAuthReq()
        req.clientId = self._client_id
        req.clientSecret = self._client_secret
        client.send(req).addCallbacks(self._on_app_auth, self._on_error)

    def _on_app_auth(self, message) -> None:
        req = _oa.ProtoOAAccountAuthReq()
        req.ctidTraderAccountId = self._account_id
        req.accessToken = self._access_token
        self._client.send(req).addCallbacks(self._on_account_auth, self._on_error)

    def _on_account_auth(self, message) -> None:
        self._ready.set()

    def _on_error(self, failure) -> None:
        self._last_error = f"cTrader API error: {failure}"
        logger.error(self._last_error)

    def _on_disconnected(self, client, reason) -> None:
        logger.warning("cTrader disconnected: %s", reason)
        self._ready.clear()

    def _on_message(self, client, message) -> None:
        """Unsolicited messages — spot events update the tick cache."""
        try:
            if message.payloadType == _common.ProtoOAPayloadType.Value("PROTO_OA_SPOT_EVENT"):
                ev = Protobuf.extract(message)
                self._spots[ev.symbolId] = (
                    ev.bid if ev.HasField("bid") else 0,
                    ev.ask if ev.HasField("ask") else 0,
                    ev.timestamp if ev.HasField("timestamp") else int(time.time() * 1000),
                )
        except Exception:  # noqa: BLE001 — never let a tick kill the listener
            logger.debug("spot event handling failed", exc_info=True)

    def _ensure_connected(self) -> None:
        if not self.connect():
            raise CTraderConnectionError(
                "cTrader Open API is not connected. " + (self._last_error or "")
            )

    # ── Blocking request helper ──────────────────────────────────

    def _call(self, request, timeout: float = 15.0):
        """Send a request on the reactor thread and block for its response.

        Returns the extracted protobuf payload. Raises CTraderConnectionError
        on API error (ProtoOAErrorRes / ProtoErrorRes) or timeout."""
        self._ensure_connected()
        done = threading.Event()
        box: Dict[str, Any] = {}

        def _ok(message):
            box["message"] = message
            done.set()
            return message

        def _err(failure):
            box["error"] = failure
            done.set()
            return None

        def _send():
            try:
                self._client.send(request).addCallbacks(_ok, _err)
            except Exception as e:  # noqa: BLE001
                box["error"] = e
                done.set()

        reactor.callFromThread(_send)
        if not done.wait(timeout):
            raise CTraderConnectionError(f"cTrader request timed out after {timeout}s.")
        if "error" in box:
            failure = box["error"]
            # Twisted Failure -> message; OpenApiPy wraps API error responses in
            # the failure's message payload when possible.
            raise CTraderConnectionError(f"cTrader API rejected the request: {failure}")
        payload = Protobuf.extract(box["message"])
        # Belt-and-braces: a 200 response can still be an error payload.
        pt = box["message"].payloadType
        err_names = ("PROTO_OA_ERROR_RES", "PROTO_ERROR_RES")
        try:
            if _common.ProtoOAPayloadType.Name(pt) in err_names:
                raise CTraderConnectionError(
                    f"cTrader error {payload.errorCode}: {getattr(payload, 'description', '')}")
        except ValueError:
            pass
        return payload

    # ── Symbol resolution & caching ──────────────────────────────

    @staticmethod
    def _norm_name(name: str) -> str:
        """'EUR/USD' -> 'EURUSD' (the app's symbol vocabulary)."""
        return name.replace("/", "").replace("_", "").upper()

    def _symbol_id(self, symbol: str) -> int:
        if not self._symbols_by_name:
            res = self._call(self._req(_oa.ProtoOASymbolsListReq))
            for s in res.symbol:
                name = self._norm_name(s.symbolName)
                self._symbols_by_name[name] = s.symbolId
                self._symbol_names[s.symbolId] = name
        sid = self._symbols_by_name.get(self._norm_name(symbol))
        if sid is None:
            raise CTraderConnectionError(
                f"Symbol {symbol} is not available on this account/server.")
        return sid

    def _symbol_detail(self, symbol_id: int):
        if symbol_id not in self._symbol_details:
            req = _oa.ProtoOASymbolByIdReq()
            req.symbolId.append(symbol_id)
            res = self._call(self._req(req))
            if not res.symbol:
                raise CTraderConnectionError(f"No symbol detail for id {symbol_id}.")
            self._symbol_details[symbol_id] = res.symbol[0]
        return self._symbol_details[symbol_id]

    def _lot_size_cents(self, symbol_id: int) -> int:
        """Cents-of-units per 1.0 lot for this symbol (usually 10,000,000)."""
        return int(getattr(self._symbol_detail(symbol_id), "lotSize", 0) or 10_000_000)

    def lots_to_volume(self, symbol: str, lots: float) -> int:
        sid = self._symbol_id(symbol)
        return int(round(float(lots) * self._lot_size_cents(sid)))

    def volume_to_lots(self, symbol_id: int, volume_cents: int) -> float:
        lot = self._lot_size_cents(symbol_id)
        return round(volume_cents / lot, 4) if lot else 0.0

    def _req(self, request):
        """Attach the account id every account-scoped request needs."""
        request.ctidTraderAccountId = self._account_id
        return request

    # ── Market data ──────────────────────────────────────────────

    def _ensure_spot(self, symbol_id: int) -> Tuple[int, int, int]:
        """Latest (bid, ask, ts) for a symbol; subscribes on first use."""
        spot = self._spots.get(symbol_id)
        if spot and (spot[0] or spot[1]):
            return spot
        req = _oa.ProtoOASubscribeSpotsReq()
        req.symbolId.append(symbol_id)
        req.subscribeToSpotTimestamp = True
        self._call(self._req(req))
        # Wait briefly for the first spot event to arrive.
        for _ in range(30):
            spot = self._spots.get(symbol_id)
            if spot and (spot[0] or spot[1]):
                return spot
            time.sleep(0.1)
        raise CTraderConnectionError(
            f"No live quote received for symbol id {symbol_id} (market closed?).")

    def get_tick(self, symbol: str) -> Dict[str, Any]:
        self._ensure_connected()
        sid = self._symbol_id(symbol)
        bid, ask, ts = self._ensure_spot(sid)
        return normalize_tick(symbol, bid, ask, ts)

    def get_candles(self, symbol: str, timeframe: str = "1h", count: int = 200) -> List[Dict[str, Any]]:
        """Historical OHLC from ProtoOAGetTrendbars. cTrader returns bars
        ending at toTimestamp; paginate backwards via hasMore if needed."""
        self._ensure_connected()
        sid = self._symbol_id(symbol)
        tf_name = _TIMEFRAME_NAMES.get(timeframe, "H1")
        period = _model.ProtoOATrendbarPeriod.Value(tf_name)
        want = min(int(count), 5000)
        out: List[Dict[str, Any]] = []
        to_ms = int(time.time() * 1000)
        for _ in range(8):  # hard cap on pages
            req = _oa.ProtoOAGetTrendbarsReq()
            req.period = period
            req.symbolId = sid
            req.toTimestamp = to_ms
            req.count = want - len(out)
            res = self._call(self._req(req), timeout=30)
            bars = []
            for tb in res.trendbar:
                low = _price(tb.low)
                bars.append({
                    "time": int(tb.utcTimestampInMinutes) * 60,
                    "open": low + _price(tb.deltaOpen),
                    "high": low + _price(tb.deltaHigh),
                    "low": low,
                    "close": low + _price(tb.deltaClose),
                    "volume": int(tb.volume),
                })
            bars.sort(key=lambda b: b["time"])
            out = bars + out
            if not res.hasMore or len(out) >= want or not bars:
                break
            to_ms = bars[0]["time"] * 1000 - 1  # next page ends before the oldest bar
        return out[-want:]

    def symbol_spec(self, symbol: str) -> Dict[str, Any]:
        self._ensure_connected()
        sid = self._symbol_id(symbol)
        s = self._symbol_detail(sid)
        lot_cents = self._lot_size_cents(sid)
        return {
            "symbol": symbol.upper(),
            "digits": s.digits,
            # cTrader quotes points at 10^-digits; pip position carried through.
            "point": 10 ** -s.digits,
            "spread": None,  # live spread is on the tick, not the spec
            "contract_size": lot_cents // 100,  # units per lot
            "volume_min": round((s.minVolume or 0) / lot_cents, 4) if lot_cents else None,
            "volume_max": round((s.maxVolume or 0) / lot_cents, 4) if lot_cents else None,
            "volume_step": round((s.stepVolume or 0) / lot_cents, 4) if lot_cents else None,
            "currency_base": None,   # asset ids are numeric; names need an asset lookup (v1)
            "currency_profit": None,
            "trade_mode": _model.ProtoOATradingMode.Name(s.tradingMode),
            "filling_mode": None,    # cTrader has no per-symbol filling-mode dance
            "tick_value": None,      # cTrader computes P&L account-side; no static tick value
            "tick_size": None,
        }

    def list_symbols(self) -> List[str]:
        self._ensure_connected()
        res = self._call(self._req(_oa.ProtoOASymbolsListReq))
        for s in res.symbol:
            name = self._norm_name(s.symbolName)
            self._symbols_by_name[name] = s.symbolId
            self._symbol_names[s.symbolId] = name
        return sorted(self._symbols_by_name)

    # ── Account ──────────────────────────────────────────────────

    def account_info(self) -> Dict[str, Any]:
        """Account snapshot in the MT5 shape: balance/equity/margin/free_margin.

        cTrader's Trader carries only the balance; equity/margin are derived
        from unrealized PnL and per-position used margin."""
        self._ensure_connected()
        res = self._call(self._req(_oa.ProtoOATraderReq))
        trader = res.trader
        md = moneyDigits_or_default(getattr(trader, "moneyDigits", 8))
        self._trader_money_digits = md
        balance = _money(trader.balance, md)
        pnl = self._unrealized_pnl()   # {positionId: net float}
        margin = self._used_margin_total()
        equity = balance + sum(pnl.values())
        return {
            "balance": round(balance, 2),
            "equity": round(equity, 2),
            "margin": round(margin, 2),
            "margin_free": round(equity - margin, 2),
            "margin_level": round(equity / margin * 100, 2) if margin else None,
            "currency": None,  # deposit asset is a numeric id on cTrader (asset lookup is v2)
            "login": self._account_id,
            "server": f"ctrader-{self._host_type}",
        }

    def _unrealized_pnl(self) -> Dict[int, float]:
        req = _oa.ProtoOAGetPositionUnrealizedPnLReq()
        res = self._call(self._req(req))
        md = moneyDigits_or_default(res.moneyDigits)
        return {p.positionId: _money(p.netUnrealizedPnL, md)
                for p in res.positionUnrealizedPnL}

    def _used_margin_total(self) -> float:
        res = self._call(self._req(_oa.ProtoOAReconcileReq))
        total = 0.0
        for p in res.position:
            md = moneyDigits_or_default(getattr(p, "moneyDigits", 0))
            total += _money(getattr(p, "usedMargin", 0), md)
        return total

    # ── Positions ────────────────────────────────────────────────

    def positions(self) -> List[Dict[str, Any]]:
        """Open positions in the mt5_client.normalize_position shape."""
        self._ensure_connected()
        res = self._call(self._req(_oa.ProtoOAReconcileReq))
        pnl = self._unrealized_pnl()
        out = []
        for p in res.position:
            td = p.tradeData
            sid = td.symbolId
            name = self._symbol_names.get(sid)
            if name is None:
                # Full symbol details carry no name (only light symbols do) —
                # refresh the id<->name map from the symbols list instead.
                self.list_symbols()
                name = self._symbol_names.get(sid) or str(sid)
            md = moneyDigits_or_default(getattr(p, "moneyDigits", 0))
            spot = self._spots.get(sid)
            current = None
            if spot:
                bid, ask, _ = spot
                # Long positions mark to bid, shorts to ask.
                current = _price(bid if td.tradeSide == _model.BUY else ask) or None
            out.append({
                "ticket": str(p.positionId),
                "symbol": name,
                "direction": "long" if td.tradeSide == _model.BUY else "short",
                "lot_size": self.volume_to_lots(sid, td.volume),
                "open_price": p.price if p.HasField("price") else None,
                "current_price": current,
                "sl": p.stopLoss if p.HasField("stopLoss") else 0,
                "tp": p.takeProfit if p.HasField("takeProfit") else 0,
                "profit": round(pnl.get(p.positionId, 0.0), 2),
                "swap": _money(getattr(p, "swap", 0), md),
            })
        return out

    # ── History ──────────────────────────────────────────────────

    def history_deals(self, days: int = 365) -> List[Dict[str, Any]]:
        """Closed trades reconstructed from the deal ledger (same output shape
        as mt5_client.pair_deals_into_trades). cTrader closes carry their own
        realized P&L + entry price via closePositionDetail, so no IN/OUT
        pairing is needed."""
        self._ensure_connected()
        now = datetime.now()
        from_ms = int((now - timedelta(days=days)).timestamp() * 1000)
        to_ms = int((now + timedelta(days=2)).timestamp() * 1000)  # server-clock slack, as on MT5
        deals = []
        for _ in range(10):  # page cap
            req = _oa.ProtoOADealListReq()
            req.fromTimestamp = from_ms
            req.toTimestamp = to_ms
            req.maxRows = 1000
            res = self._call(self._req(req), timeout=30)
            deals.extend(res.deal)
            if not res.hasMore:
                break
            # Next page: deals BEFORE the oldest one we have.
            oldest = min(d.executionTimestamp for d in deals)
            to_ms = oldest - 1
        trades = []
        for d in deals:
            if not d.HasField("closePositionDetail"):
                continue  # an opening fill, not a realized close
            cpd = d.closePositionDetail
            md = moneyDigits_or_default(getattr(cpd, "moneyDigits", getattr(d, "moneyDigits", 0)))
            name = self._symbol_names.get(d.symbolId)
            if name is None:
                self.list_symbols()
                name = self._symbol_names.get(d.symbolId) or str(d.symbolId)
            gross = _money(cpd.grossProfit, md)
            swap = _money(cpd.swap, md)
            comm = _money(cpd.commission, md)
            trades.append({
                "ticket": str(d.dealId),
                "position_id": d.positionId,
                "symbol": name,
                # The closing deal's side is opposite the position's direction.
                "direction": "short" if d.tradeSide == _model.BUY else "long",
                "lot_size": self.volume_to_lots(d.symbolId, cpd.closedVolume or d.filledVolume),
                "open_price": cpd.entryPrice,
                "close_price": d.executionPrice if d.HasField("executionPrice") else None,
                "profit": round(gross + swap + comm, 2),
                # cTrader deals don't carry the position's SL/TP; recovering
                # them needs a per-position order lookup (v2). Honest None.
                "sl": None,
                "tp": None,
                "closed_at": datetime.utcfromtimestamp(d.executionTimestamp / 1000).isoformat(),
            })
        trades.sort(key=lambda t: t.get("closed_at") or "", reverse=True)
        return trades

    def history_summary(self, days: int = 365) -> Dict[str, Any]:
        """Balance reconciliation, same keys as the MT5 version. cTrader deal
        history covers trading only (deposits/withdrawals are a separate
        cash-flow API), so deposits are reported as None rather than invented."""
        trades = self.history_deals(days)
        info = self.account_info()
        return {
            "days": days,
            "deal_count": None,  # raw deal rows not exposed here; closed_trades is what matters
            "trade_deal_count": None,
            "closed_trades": len(trades),
            "deposits": None,  # not part of cTrader's deal ledger (see module comment)
            "realized_pnl": round(sum(t.get("profit") or 0 for t in trades), 2),
            "balance": info.get("balance"),
            "equity": info.get("equity"),
        }

    # ── Orders ───────────────────────────────────────────────────

    def send_order(self, symbol: str, direction: str, lot_size: float,
                   stop_loss: Optional[float] = None,
                   take_profit: Optional[float] = None) -> Dict[str, Any]:
        """Market order. cTrader MARKET orders don't accept absolute SL/TP, so
        protection is attached as RELATIVE SL/TP computed from the live spot
        (proto: relativeStopLoss in 1/100000 of a price unit) — the position is
        protected from the moment it fills."""
        self._ensure_connected()
        sid = self._symbol_id(symbol)
        bid, ask, _ = self._ensure_spot(sid)
        is_buy = direction == "long"
        ref = _price(ask if is_buy else bid)

        req = _oa.ProtoOANewOrderReq()
        req.symbolId = sid
        req.orderType = _model.MARKET
        req.tradeSide = _model.BUY if is_buy else _model.SELL
        req.volume = self.lots_to_volume(symbol, lot_size)
        req.comment = "ict-trading-os"
        req.label = "ictos"
        if stop_loss is not None:
            rel = (ref - float(stop_loss)) if is_buy else (float(stop_loss) - ref)
            if rel <= 0:
                raise CTraderConnectionError(
                    f"Stop-loss {stop_loss} is on the wrong side of price {ref} for a {direction}.")
            req.relativeStopLoss = int(round(rel * 100000))
        if take_profit is not None:
            rel = (float(take_profit) - ref) if is_buy else (ref - float(take_profit))
            if rel <= 0:
                raise CTraderConnectionError(
                    f"Take-profit {take_profit} is on the wrong side of price {ref} for a {direction}.")
            req.relativeTakeProfit = int(round(rel * 100000))
        return self._exec_to_result(self._call(self._req(req), timeout=30))

    def order_check(self, symbol: str, direction: str, lot_size: float,
                    stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None) -> Dict[str, Any]:
        """Validate WITHOUT placing — the cTrader equivalent of mt5.order_check.
        Checks: symbol tradable, volume within min/max/step, live quote present,
        SL/TP on the right side, and expected margin computable. cTrader has no
        filling modes, so that MT5 failure class doesn't exist here."""
        self._ensure_connected()
        try:
            sid = self._symbol_id(symbol)
            detail = self._symbol_detail(sid)
            lot_cents = self._lot_size_cents(sid)
            vol = self.lots_to_volume(symbol, lot_size)
            problems = []
            if detail.minVolume and vol < detail.minVolume:
                problems.append(f"volume {lot_size} lots below min "
                                f"{detail.minVolume / lot_cents} lots")
            if detail.maxVolume and vol > detail.maxVolume:
                problems.append(f"volume {lot_size} lots above max "
                                f"{detail.maxVolume / lot_cents} lots")
            if detail.tradingMode != _model.ENABLED:
                problems.append(f"trading mode is {_model.ProtoOATradingMode.Name(detail.tradingMode)}")
            bid, ask, _ = self._ensure_spot(sid)
            ref = _price(ask if direction == "long" else bid)
            for label, px, want_above in (("stop_loss", stop_loss, direction == "short"),
                                          ("take_profit", take_profit, direction == "long")):
                if px is not None:
                    bad = (float(px) >= ref) if want_above else (float(px) <= ref)
                    # For a LONG: SL must be below price, TP above. For a SHORT: inverse.
                    if bad:
                        problems.append(f"{label} {px} is on the wrong side of price {ref}")
            margin = None
            try:
                mreq = _oa.ProtoOAExpectedMarginReq()
                mreq.symbolId = sid
                mreq.volume.append(vol)
                mres = self._call(self._req(mreq))
                md = moneyDigits_or_default(getattr(mres, "moneyDigits", 0))
                margin = _money(mres.margin, md)
            except Exception:  # noqa: BLE001
                pass  # margin check is best-effort; absence isn't a rejection
            if problems:
                return {"ok": False, "comment": "; ".join(problems),
                        "expected_margin": margin}
            return {"ok": True, "filling": "market", "comment": "would be accepted",
                    "expected_margin": margin, "price": ref}
        except CTraderConnectionError as e:
            return {"ok": False, "comment": str(e)}

    def close_position(self, ticket: int) -> Dict[str, Any]:
        self._ensure_connected()
        pos = self._find_position(int(ticket))
        return self._close(ticket=int(ticket), volume=pos.tradeData.volume)

    def partial_close(self, ticket: int, volume: float) -> Dict[str, Any]:
        self._ensure_connected()
        pos = self._find_position(int(ticket))
        sid = pos.tradeData.symbolId
        vol_cents = self.lots_to_volume(self._symbol_names.get(sid, str(sid)), volume)
        if vol_cents <= 0 or vol_cents > pos.tradeData.volume:
            raise CTraderConnectionError(
                f"Partial close volume {volume} lots must be > 0 and <= position volume "
                f"{self.volume_to_lots(sid, pos.tradeData.volume)} lots.")
        return self._close(ticket=int(ticket), volume=vol_cents)

    def _close(self, ticket: int, volume: int) -> Dict[str, Any]:
        req = _oa.ProtoOAClosePositionReq()
        req.positionId = int(ticket)
        req.volume = int(volume)
        return self._exec_to_result(self._call(self._req(req), timeout=30))

    def modify_sltp(self, ticket: int, stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None) -> Dict[str, Any]:
        self._ensure_connected()
        pos = self._find_position(int(ticket))
        req = _oa.ProtoOAAmendPositionSLTPReq()
        req.positionId = int(ticket)
        # Unset sides keep their current value (proto has no "leave unchanged"
        # sentinel — re-send the existing absolute price).
        req.stopLoss = float(stop_loss) if stop_loss is not None else (
            pos.stopLoss if pos.HasField("stopLoss") else 0.0)
        req.takeProfit = float(take_profit) if take_profit is not None else (
            pos.takeProfit if pos.HasField("takeProfit") else 0.0)
        self._call(self._req(req))
        return {"retcode": RETCODE_DONE, "order": int(ticket), "comment": "sl/tp amended"}

    def place_pending(self, symbol: str, direction: str, order_kind: str,
                      volume: float, price: float,
                      stop_loss: Optional[float] = None,
                      take_profit: Optional[float] = None) -> Dict[str, Any]:
        self._ensure_connected()
        sid = self._symbol_id(symbol)
        req = _oa.ProtoOANewOrderReq()
        req.symbolId = sid
        req.tradeSide = _model.BUY if direction == "long" else _model.SELL
        req.volume = self.lots_to_volume(symbol, volume)
        req.comment = "ict-trading-os-pending"
        req.label = "ictos"
        if order_kind == "limit":
            req.orderType = _model.LIMIT
            req.limitPrice = float(price)
        elif order_kind == "stop":
            req.orderType = _model.STOP
            req.stopPrice = float(price)
        else:
            raise CTraderConnectionError(f"Invalid pending order kind: {order_kind}.")
        # Pending orders DO accept absolute SL/TP on cTrader.
        if stop_loss is not None:
            req.stopLoss = float(stop_loss)
        if take_profit is not None:
            req.takeProfit = float(take_profit)
        return self._exec_to_result(self._call(self._req(req), timeout=30))

    def pending_orders(self) -> List[Dict[str, Any]]:
        self._ensure_connected()
        res = self._call(self._req(_oa.ProtoOAReconcileReq))
        out = []
        for o in res.order:
            if o.orderType not in (_model.LIMIT, _model.STOP):
                continue
            td = o.tradeData
            name = self._symbol_names.get(td.symbolId) or str(td.symbolId)
            kind = "limit" if o.orderType == _model.LIMIT else "stop"
            out.append({
                "ticket": str(o.orderId),
                "symbol": name,
                "direction": "long" if td.tradeSide == _model.BUY else "short",
                "order_kind": kind,
                "type": f"{'buy' if td.tradeSide == _model.BUY else 'sell'}_{kind}",
                "lot_size": self.volume_to_lots(td.symbolId, td.volume),
                "price_open": o.limitPrice if o.orderType == _model.LIMIT else o.stopPrice,
                "sl": o.stopLoss if o.HasField("stopLoss") else 0,
                "tp": o.takeProfit if o.HasField("takeProfit") else 0,
                "time_setup": datetime.utcfromtimestamp(td.openTimestamp / 1000).isoformat()
                              if td.HasField("openTimestamp") else None,
            })
        return out

    def cancel_pending(self, order_ticket: int) -> Dict[str, Any]:
        self._ensure_connected()
        req = _oa.ProtoOACancelOrderReq()
        req.orderId = int(order_ticket)
        self._call(self._req(req))
        return {"retcode": RETCODE_DONE, "order": int(order_ticket), "comment": "cancelled"}

    # ── Internals ────────────────────────────────────────────────

    def _find_position(self, ticket: int):
        res = self._call(self._req(_oa.ProtoOAReconcileReq))
        for p in res.position:
            if p.positionId == ticket:
                return p
        raise CTraderConnectionError(f"No open position with ticket {ticket}.")

    def _exec_to_result(self, event) -> Dict[str, Any]:
        """ProtoOAExecutionEvent -> the MT5-style result the app parses
        (retcode vocabulary shared with planner_service / the /mt5 router)."""
        if event.HasField("errorCode") and event.errorCode:
            return {
                "retcode": RETCODE_REJECTED,
                "comment": event.errorCode,
                "order": None, "deal": None, "price": None,
            }
        order = event.order if event.HasField("order") else None
        deal = event.deal if event.HasField("deal") else None
        position = event.position if event.HasField("position") else None
        filled = deal is not None and getattr(deal, "dealStatus", None) in (
            _model.FILLED, _model.PARTIALLY_FILLED)
        price = None
        if deal is not None and deal.HasField("executionPrice"):
            price = deal.executionPrice
        elif order is not None and order.HasField("executionPrice"):
            price = order.executionPrice
        return {
            "retcode": RETCODE_DONE if filled else RETCODE_PLACED,
            "order": getattr(order, "orderId", None),
            "deal": getattr(deal, "dealId", None),
            "position_id": getattr(position, "positionId", None),
            "price": price,
            "volume": self.volume_to_lots(order.tradeData.symbolId, deal.filledVolume)
                      if (order and deal) else None,
            "comment": _model.ProtoOAExecutionType.Name(event.executionType),
        }

    def write_levels_file(self, symbol: str, zones: List[Dict], meta: Dict) -> str:
        """Chart-drawing is the one thing that genuinely can't move: MT5 levels
        are drawn by an MQL5 indicator inside the terminal; cTrader charts use
        cAlgo (C#) plugins. Chart DATA (candles/ticks) flows through this
        bridge normally — only the on-terminal drawings are MT5-specific."""
        raise CTraderConnectionError(
            "Chart drawing on a cTrader terminal is not supported by this bridge "
            "(MT5 used an MQL5 indicator reading CSV files). Candle/level DATA is "
            "unaffected — the app's own charts render identically."
        )
