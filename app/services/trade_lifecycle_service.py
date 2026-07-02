"""Trade lifecycle service with full position tracking, partial closes, and R-multiple."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from threading import RLock
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import uuid
from app.core.database import db
from app.services.instrument_config import get_instrument
from app.services.market_data import market_service
from app.services.lot_calculator import PIP_SIZES, PIP_VALUES, lot_calculator


ZERO = Decimal("0")


def utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _decimal(value: Any, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return default


def _quantize(value: Any, places: int) -> float:
    quantum = Decimal("1").scaleb(-places)
    return float(_decimal(value).quantize(quantum, rounding=ROUND_HALF_UP))


def _money(value: Any) -> float:
    return _quantize(value, 2)


def _quantity(value: Any) -> float:
    return _quantize(value, 6)


def _price(value: Any, digits: int) -> float:
    return _quantize(value, digits)


class TradeLifecycleService:
    """Manages trade entry, partial closes, and full lifecycle tracking."""

    def __init__(self):
        self._trade_lock = RLock()

    def _validate_stops_and_targets(
        self,
        side: str,
        entry_price: float,
        stop_loss: float,
        take_profits: List[Optional[float]],
    ) -> Optional[str]:
        entry = _decimal(entry_price)
        sl = _decimal(stop_loss)
        if sl <= ZERO:
            return None
        if side == "BUY" and sl >= entry:
            return "Invalid stop loss: For BUY, SL must be below entry price. For SELL, SL must be above entry price."
        if side == "SELL" and sl <= entry:
            return "Invalid stop loss: For BUY, SL must be below entry price. For SELL, SL must be above entry price."

        previous = None
        for index, take_profit in enumerate(take_profits, 1):
            if take_profit is None:
                continue
            tp = _decimal(take_profit)
            if tp <= ZERO:
                return f"Invalid take profit {index}: price must be positive"
            if side == "BUY":
                if tp <= entry:
                    return f"Invalid take profit {index}: For BUY, TP must be above entry price."
                if previous is not None and tp <= previous:
                    return "Invalid take profit sequence: BUY targets must increase away from entry."
            else:
                if tp >= entry:
                    return f"Invalid take profit {index}: For SELL, TP must be below entry price."
                if previous is not None and tp >= previous:
                    return "Invalid take profit sequence: SELL targets must decrease away from entry."
            previous = tp
        return None

    def _weighted_total_r(self, trade: Dict[str, Any]) -> float:
        initial_quantity = _decimal(trade.get("initial_quantity"))
        if initial_quantity <= ZERO:
            return 0.0
        total = ZERO
        for leg in trade.get("legs", []):
            if "r_contribution" in leg:
                total += _decimal(leg.get("r_contribution"))
            else:
                total += _decimal(leg.get("r_multiple")) * (_decimal(leg.get("quantity")) / initial_quantity)
        return _quantize(total, 3)

    def create_trade(
        self,
        symbol: str,
        side: str,
        entry_price: Optional[float] = None,
        stop_loss: float = 0,
        take_profit_1: Optional[float] = None,
        take_profit_2: Optional[float] = None,
        take_profit_3: Optional[float] = None,
        quantity: Optional[float] = None,
        account_balance: float = 10000.0,
        risk_pct: float = 1.0,
        strategy: str = "",
        notes: str = "",
        plan_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new trade with auto lot calculation if quantity not provided."""
        symbol = symbol.upper()
        config = get_instrument(symbol)
        if not config:
            return {"error": f"Unknown symbol: {symbol}"}

        # Fetch live price if entry not provided
        if entry_price is None or entry_price <= 0:
            live = market_service.get_price(symbol)
            entry_price = live.get("price", 0)
        if entry_price <= 0:
            return {"error": f"Could not fetch live price for {symbol}"}

        side = side.upper() if side else "BUY"

        # Validate side
        if side not in ("BUY", "SELL"):
            return {"error": "Invalid side: must be BUY or SELL"}

        validation_error = self._validate_stops_and_targets(
            side,
            entry_price,
            stop_loss,
            [take_profit_1, take_profit_2, take_profit_3],
        )
        if validation_error:
            return {"error": validation_error}

        # Auto-calculate lot size if not provided and SL is valid
        if quantity is None or quantity <= 0:
            if stop_loss > 0 and stop_loss != entry_price:
                calc = lot_calculator.calculate(symbol, entry_price, stop_loss, account_balance, risk_pct)
                if "error" not in calc:
                    quantity = calc.get("lot_size", 0)
                else:
                    return {"error": f"Lot calculation failed: {calc.get('error')}", "calc": calc}
            else:
                return {"error": "Stop loss required for auto lot calculation"}

        if quantity <= 0:
            return {"error": "Invalid quantity"}

        # Calculate risk amount
        risk_amount = _decimal(account_balance) * (_decimal(risk_pct) / Decimal("100"))
        price_distance = abs(_decimal(entry_price) - _decimal(stop_loss)) if stop_loss > 0 else ZERO
        r_unit = price_distance if price_distance > 0 else 1.0
        now = utc_now_iso()
        trade_id = f"TRD-{int(datetime.now(timezone.utc).timestamp()*1000)}-{uuid.uuid4().hex[:6]}"

        trade = {
            "id": trade_id,
            "symbol": symbol,
            "side": side.upper(),
            "entry_price": _price(entry_price, config.get("digits", 5)),
            "stop_loss": _price(stop_loss, config.get("digits", 5)) if stop_loss > 0 else None,
            "take_profit_1": _price(take_profit_1, config.get("digits", 5)) if take_profit_1 else None,
            "take_profit_2": _price(take_profit_2, config.get("digits", 5)) if take_profit_2 else None,
            "take_profit_3": _price(take_profit_3, config.get("digits", 5)) if take_profit_3 else None,
            "quantity": _quantity(quantity),
            "initial_quantity": _quantity(quantity),
            "remaining_quantity": _quantity(quantity),
            "account_balance": account_balance,
            "risk_pct": risk_pct,
            "risk_amount": _money(risk_amount),
            "strategy": strategy,
            "notes": notes,
            "plan_id": plan_id,
            "status": "OPEN",
            "legs": [],
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "total_r": 0.0,
            "r_unit": _price(r_unit, 5),
            "current_price": _price(entry_price, config.get("digits", 5)),
            "created_at": now,
            "closed_at": None,
            "updated_at": now,
            "tp1_hit": False,
            "tp2_hit": False,
            "tp3_hit": False,
            "sl_at_be": False,
        }
        return db.insert("trades", trade)

    def _calc_pnl(self, symbol: str, side: str, entry: float, exit: float, qty: float) -> float:
        """Calculate PnL using instrument pip/contract sizing."""
        symbol = symbol.upper()
        pip_size = _decimal(PIP_SIZES.get(symbol, 0.0001))
        pip_value = _decimal(PIP_VALUES.get(symbol, 10.0))
        entry_d = _decimal(entry)
        exit_d = _decimal(exit)
        qty_d = _decimal(qty)
        price_diff = exit_d - entry_d if side.upper() == "BUY" else entry_d - exit_d
        pip_diff = price_diff / pip_size if pip_size > ZERO else price_diff
        return _money(pip_diff * pip_value * qty_d)

    def _calc_r_multiple(self, side: str, entry: float, exit: float, sl: float) -> float:
        """Calculate R-multiple for a trade leg."""
        r_distance = abs(_decimal(entry) - _decimal(sl)) if sl and sl > 0 else Decimal("1")
        if side == "BUY":
            value = (_decimal(exit) - _decimal(entry)) / r_distance if r_distance > 0 else ZERO
        else:
            value = (_decimal(entry) - _decimal(exit)) / r_distance if r_distance > 0 else ZERO
        return _quantize(value, 3)

    def partial_close(self, trade_id: str, fraction: float, exit_price: float, label: str = "TP") -> Dict[str, Any]:
        """Close a fraction of the trade (e.g., 0.3 at TP1)."""
        with self._trade_lock:
            trade = db.find_one("trades", trade_id)
            if not trade:
                return {"error": "Trade not found"}
            if trade["status"] == "CLOSED":
                return {"error": "Trade already closed"}
            remaining = _decimal(trade.get("remaining_quantity"))
            if remaining <= ZERO:
                return {"error": "No remaining quantity to close"}

            fraction_d = _decimal(fraction)
            if fraction_d <= ZERO or fraction_d > Decimal("1"):
                return {"error": "Close fraction must be greater than 0 and less than or equal to 1"}

            close_qty_d = (remaining * fraction_d).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            if close_qty_d <= ZERO:
                return {"error": "Close quantity is zero"}
            if close_qty_d > remaining:
                return {"error": "Close quantity exceeds remaining quantity"}

            close_qty = _quantity(close_qty_d)
            pnl = self._calc_pnl(trade["symbol"], trade["side"], trade["entry_price"], exit_price, close_qty)
            r = self._calc_r_multiple(trade["side"], trade["entry_price"], exit_price, trade.get("stop_loss", 0))
            digits = get_instrument(trade["symbol"]).get("digits", 5)
            now = utc_now_iso()
            initial_quantity = _decimal(trade.get("initial_quantity"))
            r_contribution = _decimal(r) * (close_qty_d / initial_quantity) if initial_quantity > ZERO else ZERO

            leg = {
                "fraction": _quantize(fraction_d, 4),
                "exit_price": _price(exit_price, digits),
                "quantity": close_qty,
                "pnl": _money(pnl),
                "r_multiple": _quantize(r, 3),
                "r_contribution": _quantize(r_contribution, 3),
                "closed_at": now,
                "label": label,
            }

            trade["legs"].append(leg)
            trade["realized_pnl"] = _money(_decimal(trade.get("realized_pnl", 0)) + _decimal(pnl))
            trade["remaining_quantity"] = _quantity(remaining - close_qty_d)
            trade["total_r"] = self._weighted_total_r(trade)

            if _decimal(trade["remaining_quantity"]) <= Decimal("0.0001"):
                trade["remaining_quantity"] = 0.0
                trade["status"] = "CLOSED"
                trade["closed_at"] = now
            else:
                trade["status"] = f"PARTIAL_{len(trade['legs'])}"

            trade["updated_at"] = now
            expected_version = int(trade.get("version") or 1)
            saved = db.update_if_version("trades", trade_id, expected_version, trade)
            if not saved:
                return {"error": "Trade was modified concurrently; retry close"}
            return saved

    def full_close(self, trade_id: str, exit_price: float) -> Dict[str, Any]:
        """Close all remaining position."""
        with self._trade_lock:
            trade = db.find_one("trades", trade_id)
            if not trade:
                return {"error": "Trade not found"}
            if trade["status"] == "CLOSED":
                return {"error": "Trade already closed"}
            remaining = _decimal(trade.get("remaining_quantity"))
            if remaining <= ZERO:
                return {"error": "No remaining quantity to close"}

            close_qty = _quantity(remaining)
            pnl = self._calc_pnl(trade["symbol"], trade["side"], trade["entry_price"], exit_price, close_qty)
            r = self._calc_r_multiple(trade["side"], trade["entry_price"], exit_price, trade.get("stop_loss", 0))
            initial = _decimal(trade.get("initial_quantity"))
            digits = get_instrument(trade["symbol"]).get("digits", 5)
            now = utc_now_iso()
            r_contribution = _decimal(r) * (remaining / initial) if initial > ZERO else ZERO

            leg = {
                "fraction": _quantize(remaining / initial, 4) if initial > ZERO else 1.0,
                "exit_price": _price(exit_price, digits),
                "quantity": close_qty,
                "pnl": _money(pnl),
                "r_multiple": _quantize(r, 3),
                "r_contribution": _quantize(r_contribution, 3),
                "closed_at": now,
                "label": "CLOSE",
            }

            trade["legs"].append(leg)
            trade["realized_pnl"] = _money(_decimal(trade.get("realized_pnl", 0)) + _decimal(pnl))
            trade["remaining_quantity"] = 0.0
            trade["total_r"] = self._weighted_total_r(trade)
            trade["status"] = "CLOSED"
            trade["exit_price"] = _price(exit_price, digits)
            trade["closed_at"] = now
            trade["updated_at"] = now
            expected_version = int(trade.get("version") or 1)
            saved = db.update_if_version("trades", trade_id, expected_version, trade)
            if not saved:
                return {"error": "Trade was modified concurrently; retry close"}
            return saved

    def get_trade(self, trade_id: str) -> Dict[str, Any]:
        """Get a single trade with updated unrealized PnL."""
        trade = db.find_one("trades", trade_id)
        if not trade:
            return {}
        if trade["status"] != "CLOSED" and trade.get("remaining_quantity", 0) > 0:
            live = market_service.get_price(trade["symbol"])
            current_price = live.get("price", 0)
            if current_price > 0:
                trade["current_price"] = round(current_price, 5)
                unrealized = self._calc_pnl(trade["symbol"], trade["side"], trade["entry_price"], current_price, trade["remaining_quantity"])
                trade["unrealized_pnl"] = _money(unrealized)
                # R for remaining position
                r_unrealized = self._calc_r_multiple(trade["side"], trade["entry_price"], current_price, trade.get("stop_loss", 0))
                initial = _decimal(trade.get("initial_quantity"))
                remaining = _decimal(trade.get("remaining_quantity"))
                weighted_open_r = _decimal(r_unrealized) * (remaining / initial) if initial > ZERO else ZERO
                trade["total_r"] = _quantize(_decimal(self._weighted_total_r(trade)) + weighted_open_r, 3)
        return trade

    def list_trades(self, status: Optional[str] = None, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all trades with updated unrealized PnL."""
        trades = db.get_collection("trades")
        if status:
            trades = [t for t in trades if t.get("status") == status]
        if symbol:
            trades = [t for t in trades if t.get("symbol") == symbol.upper()]
        # Update unrealized for open trades
        for t in trades:
            if t["status"] != "CLOSED" and t.get("remaining_quantity", 0) > 0:
                live = market_service.get_price(t["symbol"])
                current_price = live.get("price", 0)
                if current_price > 0:
                    t["current_price"] = round(current_price, 5)
                    t["unrealized_pnl"] = _money(self._calc_pnl(t["symbol"], t["side"], t["entry_price"], current_price, t["remaining_quantity"]))
        return sorted(trades, key=lambda x: x.get("created_at", ""), reverse=True)

    def move_sl_to_breakeven(self, trade_id: str) -> Dict[str, Any]:
        """Move stop loss to entry price (breakeven)."""
        trade = db.find_one("trades", trade_id)
        if not trade:
            return {"error": "Trade not found"}
        if trade["status"] == "CLOSED":
            return {"error": "Trade already closed"}
        trade["stop_loss"] = trade["entry_price"]
        trade["sl_at_be"] = True
        trade["updated_at"] = utc_now_iso()
        expected_version = int(trade.get("version") or 1)
        saved = db.update_if_version("trades", trade_id, expected_version, trade)
        if not saved:
            return {"error": "Trade was modified concurrently; retry close"}
        return saved

    def check_tp_hits(self) -> List[Dict[str, Any]]:
        """Check all open trades against live prices for TP/SL hits.
        
        Auto-management rules:
        - SL hit: full close (only if SL not already at BE)
        - TP1 hit: 33% partial close, move SL to breakeven
        
        After TP1, the trade is left to flow manually. No auto TP2/TP3 management.
        """
        actions = []
        open_trades = [t for t in db.get_collection("trades") if t.get("status") not in ("CLOSED", None)]
        
        for trade in open_trades:
            if trade.get("remaining_quantity", 0) <= 0:
                continue
                
            symbol = trade["symbol"]
            side = trade["side"]
            current = market_service.get_price(symbol)
            current_price = current.get("price", 0)
            if current_price <= 0:
                continue
                
            sl = trade.get("stop_loss")
            tp1 = trade.get("take_profit_1")
            
            tp1_hit = trade.get("tp1_hit", False)
            sl_at_be = trade.get("sl_at_be", False)
            
            # BUY: SL is below entry → hit when price drops TO or BELOW SL
            # BUY: TP is above entry → hit when price rises TO or ABOVE TP
            # SELL: SL is above entry → hit when price rises TO or ABOVE SL  
            # SELL: TP is below entry → hit when price drops TO or BELOW TP
            
            if side == "BUY":
                sl_hit = sl is not None and current_price <= sl
                tp1_hit_now = tp1 is not None and current_price >= tp1
            else:  # SELL
                sl_hit = sl is not None and current_price >= sl
                tp1_hit_now = tp1 is not None and current_price <= tp1
            
            # SL hit check (only if SL is NOT at BE)
            if sl_hit and not sl_at_be:
                result = self.full_close(trade["id"], current_price)
                actions.append({"trade_id": trade["id"], "action": "SL_CLOSE", "price": current_price, "result": result})
                continue
            
            # TP1 hit: 33% partial, move SL to BE
            if tp1_hit_now and not tp1_hit:
                result = self.partial_close(trade["id"], 0.33, current_price, "TP1")
                actions.append({"trade_id": trade["id"], "action": "TP1_PARTIAL_33", "price": current_price, "result": result})
                # Move SL to BE if not already
                if not sl_at_be and trade.get("stop_loss") != trade["entry_price"]:
                    be_result = self.move_sl_to_breakeven(trade["id"])
                    actions.append({"trade_id": trade["id"], "action": "SL_TO_BE", "result": be_result})
                # Mark TP1 hit on the updated trade
                    updated = db.find_one("trades", trade["id"])
                if updated and updated.get("status") != "CLOSED":
                    updated["tp1_hit"] = True
                    updated["updated_at"] = utc_now_iso()
                    db.update_if_version("trades", trade["id"], int(updated.get("version") or 1), updated)
                continue
        
        return actions

    def get_open_trades(self) -> List[Dict[str, Any]]:
        """Get all open trades with live unrealized PnL. Auto-check TP/SL hits."""
        # Run auto-management checks first
        self.check_tp_hits()
        # Return updated trades
        trades = self.list_trades()
        return [t for t in trades if t["status"] != "CLOSED"]

    def get_trade_stats(self) -> Dict[str, Any]:
        """Compute comprehensive trade statistics."""
        trades = db.get_collection("trades")
        closed = [t for t in trades if t.get("status") == "CLOSED"]
        open_trades = [t for t in trades if t.get("status") != "CLOSED"]

        # Update open trades with current prices for accurate stats
        for t in open_trades:
            if t.get("remaining_quantity", 0) > 0:
                live = market_service.get_price(t["symbol"])
                current_price = live.get("price", 0)
                if current_price > 0:
                    t["current_price"] = round(current_price, 5)
                    t["unrealized_pnl"] = _money(self._calc_pnl(t["symbol"], t["side"], t["entry_price"], current_price, t["remaining_quantity"]))

        # Total P&L includes both closed realized + open unrealized
        closed_pnl = sum(t.get("realized_pnl", 0) for t in closed)
        open_unrealized = sum(t.get("unrealized_pnl", 0) for t in open_trades)
        total_pnl = round(closed_pnl + open_unrealized, 2)
        
        wins = [t for t in closed if t.get("realized_pnl", 0) > 0]
        losses = [t for t in closed if t.get("realized_pnl", 0) <= 0]
        win_rate = round(len(wins) / len(closed) * 100, 1) if closed else 0

        avg_win = round(sum(t.get("realized_pnl", 0) for t in wins) / len(wins), 2) if wins else 0
        avg_loss = round(sum(t.get("realized_pnl", 0) for t in losses) / len(losses), 2) if losses else 0
        expectancy = round((win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss), 2) if closed else 0

        # R stats
        total_r = round(sum(t.get("total_r", 0) for t in closed), 3)
        avg_r = round(total_r / len(closed), 3) if closed else 0
        best_r = max((t.get("total_r", 0) for t in closed), default=0)
        worst_r = min((t.get("total_r", 0) for t in closed), default=0)

        # Streaks
        streaks = self._calc_streaks(closed)

        # Drawdown
        dd = self._calc_drawdown(closed)

        # Symbol performance
        by_symbol = {}
        for t in closed:
            sym = t["symbol"]
            if sym not in by_symbol:
                by_symbol[sym] = {"trades": 0, "wins": 0, "losses": 0, "total_pnl": 0, "best": 0, "worst": 0}
            by_symbol[sym]["trades"] += 1
            by_symbol[sym]["total_pnl"] += t.get("realized_pnl", 0)
            if t.get("realized_pnl", 0) > 0:
                by_symbol[sym]["wins"] += 1
            else:
                by_symbol[sym]["losses"] += 1
            by_symbol[sym]["best"] = max(by_symbol[sym]["best"], t.get("realized_pnl", 0))
            by_symbol[sym]["worst"] = min(by_symbol[sym]["worst"], t.get("realized_pnl", 0))

        for sym in by_symbol:
            s = by_symbol[sym]
            s["win_rate"] = round(s["wins"] / s["trades"] * 100, 1) if s["trades"] > 0 else 0
            s["avg_pnl"] = round(s["total_pnl"] / s["trades"], 2) if s["trades"] > 0 else 0

        # Monthly summary
        monthly = {}
        for t in closed:
            month = t["created_at"][:7] if t["created_at"] else "unknown"
            if month not in monthly:
                monthly[month] = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0, "win_rate": 0}
            monthly[month]["trades"] += 1
            monthly[month]["pnl"] += t.get("realized_pnl", 0)
            if t.get("realized_pnl", 0) > 0:
                monthly[month]["wins"] += 1
            else:
                monthly[month]["losses"] += 1

        for month in monthly:
            m = monthly[month]
            m["win_rate"] = round(m["wins"] / m["trades"] * 100, 1) if m["trades"] > 0 else 0
            m["pnl"] = round(m["pnl"], 2)

        # Session breakdown
        sessions = {}
        for t in closed:
            hour = int(t["created_at"][11:13]) if len(t.get("created_at", "")) > 13 else 12
            if 7 <= hour < 10:
                session = "London Open"
            elif 12 <= hour < 15:
                session = "NY AM"
            elif 15 <= hour < 17:
                session = "NY Lunch"
            elif 17 <= hour < 21:
                session = "NY PM"
            elif hour >= 21 or hour < 8:
                session = "Asian"
            else:
                session = "London Close"
            if session not in sessions:
                sessions[session] = {"count": 0, "wins": 0, "losses": 0, "pnl": 0, "win_rate": 0}
            sessions[session]["count"] += 1
            sessions[session]["pnl"] += t.get("realized_pnl", 0)
            if t.get("realized_pnl", 0) > 0:
                sessions[session]["wins"] += 1
            else:
                sessions[session]["losses"] += 1

        for s in sessions:
            sessions[s]["win_rate"] = round(sessions[s]["wins"] / sessions[s]["count"] * 100, 1) if sessions[s]["count"] > 0 else 0
            sessions[s]["pnl"] = round(sessions[s]["pnl"], 2)

        return {
            "total_trades": len(trades),
            "open_trades": len(open_trades),
            "closed_trades": len(closed),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_pnl": round(total_pnl / len(closed), 2) if closed else 0,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "expectancy": expectancy,
            "best_trade": max((t.get("realized_pnl", 0) for t in closed), default=0),
            "worst_trade": min((t.get("realized_pnl", 0) for t in closed), default=0),
            "avg_r": avg_r,
            "total_r": total_r,
            "best_r": best_r,
            "worst_r": worst_r,
            "max_win_streak": streaks["max_win"],
            "max_loss_streak": streaks["max_loss"],
            "current_streak": streaks["current"],
            "max_drawdown": dd["max_drawdown"],
            "max_drawdown_duration": dd["max_drawdown_duration"],
            "equity_curve": dd["equity_curve"],
            "by_symbol": by_symbol,
            "monthly": monthly,
            "sessions": sessions,
        }

    def _calc_streaks(self, closed_trades: List[Dict]) -> Dict:
        """Calculate win/loss streaks."""
        if not closed_trades:
            return {"max_win": 0, "max_loss": 0, "current": 0}

        sorted_trades = sorted(closed_trades, key=lambda x: x.get("created_at", ""))
        max_win = 0
        max_loss = 0
        current_win = 0
        current_loss = 0
        current = 0

        for t in sorted_trades:
            is_win = t.get("realized_pnl", 0) > 0
            if is_win:
                current_win += 1
                current_loss = 0
                max_win = max(max_win, current_win)
                current = current_win
            else:
                current_loss += 1
                current_win = 0
                max_loss = max(max_loss, current_loss)
                current = -current_loss

        return {"max_win": max_win, "max_loss": max_loss, "current": current}

    def _calc_drawdown(self, closed_trades: List[Dict]) -> Dict:
        """Calculate drawdown and equity curve."""
        if not closed_trades:
            return {"max_drawdown": 0, "max_drawdown_duration": 0, "equity_curve": []}

        sorted_trades = sorted(closed_trades, key=lambda x: x.get("created_at", ""))
        equity = 10000.0
        peak = equity
        max_dd = 0
        max_dd_duration = 0
        current_dd_duration = 0
        equity_curve = []

        for i, t in enumerate(sorted_trades):
            equity += t.get("realized_pnl", 0)
            equity_curve.append({"trade": i + 1, "equity": round(equity, 2), "pnl": t.get("realized_pnl", 0)})
            if equity > peak:
                peak = equity
                current_dd_duration = 0
            else:
                current_dd_duration += 1
                dd = (peak - equity) / peak * 100
                if dd > max_dd:
                    max_dd = dd
                    max_dd_duration = current_dd_duration

        return {
            "max_drawdown": round(max_dd, 2),
            "max_drawdown_duration": max_dd_duration,
            "equity_curve": equity_curve,
        }

    def get_kelly_criterion(self) -> Dict:
        """Calculate Kelly Criterion from trade history."""
        trades = db.get_collection("trades")
        closed = [t for t in trades if t.get("status") == "CLOSED"]
        from app.services.quant_service import quant_service

        kelly = quant_service.calculate_kelly([t.get("realized_pnl", 0) for t in closed])
        # Preserve the historical lifecycle sign convention for avg_loss.
        kelly["avg_loss"] = -abs(kelly["avg_loss"])
        return kelly

    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        """Get recent closed trades."""
        trades = db.get_collection("trades")
        closed = sorted([t for t in trades if t.get("status") == "CLOSED"], key=lambda x: x.get("created_at", ""), reverse=True)
        return closed[:limit]


trade_lifecycle_service = TradeLifecycleService()
