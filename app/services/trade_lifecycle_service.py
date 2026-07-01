"""Trade lifecycle service with full position tracking, partial closes, and R-multiple."""
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from app.core.database import db
from app.services.instrument_config import get_instrument
from app.services.market_data import market_service
from app.services.lot_calculator import lot_calculator


class TradeLifecycleService:
    """Manages trade entry, partial closes, and full lifecycle tracking."""

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

        # Validate stop loss direction relative to entry
        if stop_loss > 0:
            if side == "BUY" and stop_loss >= entry_price:
                return {"error": "Invalid stop loss: For BUY, SL must be below entry price. For SELL, SL must be above entry price."}
            if side == "SELL" and stop_loss <= entry_price:
                return {"error": "Invalid stop loss: For BUY, SL must be below entry price. For SELL, SL must be above entry price."}

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
        risk_amount = account_balance * (risk_pct / 100.0)
        price_distance = abs(entry_price - stop_loss) if stop_loss > 0 else 0
        r_unit = price_distance if price_distance > 0 else 1.0

        trade = {
            "id": f"TRD-{int(datetime.utcnow().timestamp()*1000)}",
            "symbol": symbol,
            "side": side.upper(),
            "entry_price": round(entry_price, config.get("digits", 5)),
            "stop_loss": round(stop_loss, config.get("digits", 5)) if stop_loss > 0 else None,
            "take_profit_1": round(take_profit_1, config.get("digits", 5)) if take_profit_1 else None,
            "take_profit_2": round(take_profit_2, config.get("digits", 5)) if take_profit_2 else None,
            "take_profit_3": round(take_profit_3, config.get("digits", 5)) if take_profit_3 else None,
            "quantity": round(quantity, 6),
            "initial_quantity": round(quantity, 6),
            "remaining_quantity": round(quantity, 6),
            "account_balance": account_balance,
            "risk_pct": risk_pct,
            "risk_amount": round(risk_amount, 2),
            "strategy": strategy,
            "notes": notes,
            "plan_id": plan_id,
            "status": "OPEN",
            "legs": [],
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "total_r": 0.0,
            "r_unit": round(r_unit, 5),
            "current_price": round(entry_price, config.get("digits", 5)),
            "created_at": datetime.utcnow().isoformat(),
            "closed_at": None,
            "updated_at": datetime.utcnow().isoformat(),
            "tp1_hit": False,
            "tp2_hit": False,
            "tp3_hit": False,
            "sl_at_be": False,
        }
        return db.insert("trades", trade)

    def _calc_pnl(self, symbol: str, side: str, entry: float, exit: float, qty: float) -> float:
        """Calculate PnL using lot_calculator for correct pip/contract sizing."""
        result = lot_calculator.calculate_pnl(symbol, entry, exit, qty, side)
        return result.get("pnl", 0.0)

    def _calc_r_multiple(self, side: str, entry: float, exit: float, sl: float) -> float:
        """Calculate R-multiple for a trade leg."""
        r_distance = abs(entry - sl) if sl and sl > 0 else 1.0
        if side == "BUY":
            return (exit - entry) / r_distance if r_distance > 0 else 0
        else:
            return (entry - exit) / r_distance if r_distance > 0 else 0

    def partial_close(self, trade_id: str, fraction: float, exit_price: float, label: str = "TP") -> Dict[str, Any]:
        """Close a fraction of the trade (e.g., 0.3 at TP1)."""
        trade = db.find_one("trades", trade_id)
        if not trade:
            return {"error": "Trade not found"}
        if trade["status"] == "CLOSED":
            return {"error": "Trade already closed"}
        if trade["remaining_quantity"] <= 0:
            return {"error": "No remaining quantity to close"}

        fraction = max(0.0, min(1.0, fraction))
        close_qty = round(trade["remaining_quantity"] * fraction, 6)
        if close_qty <= 0:
            return {"error": "Close quantity is zero"}

        pnl = self._calc_pnl(trade["symbol"], trade["side"], trade["entry_price"], exit_price, close_qty)
        r = self._calc_r_multiple(trade["side"], trade["entry_price"], exit_price, trade.get("stop_loss", 0))

        leg = {
            "fraction": round(fraction, 4),
            "exit_price": round(exit_price, 5),
            "quantity": close_qty,
            "pnl": round(pnl, 2),
            "r_multiple": round(r, 3),
            "closed_at": datetime.utcnow().isoformat(),
            "label": label,
        }

        trade["legs"].append(leg)
        trade["realized_pnl"] = round(trade.get("realized_pnl", 0) + pnl, 2)
        trade["remaining_quantity"] = round(trade["remaining_quantity"] - close_qty, 6)
        trade["total_r"] = round(sum(l["r_multiple"] for l in trade["legs"]), 3)

        if trade["remaining_quantity"] <= 0.0001:
            trade["status"] = "CLOSED"
            trade["closed_at"] = datetime.utcnow().isoformat()
        else:
            trade["status"] = f"PARTIAL_{len(trade['legs'])}"

        trade["updated_at"] = datetime.utcnow().isoformat()
        db.update("trades", trade_id, trade)
        return trade

    def full_close(self, trade_id: str, exit_price: float) -> Dict[str, Any]:
        """Close all remaining position."""
        trade = db.find_one("trades", trade_id)
        if not trade:
            return {"error": "Trade not found"}
        if trade["status"] == "CLOSED":
            return {"error": "Trade already closed"}
        if trade["remaining_quantity"] <= 0:
            return {"error": "No remaining quantity to close"}

        pnl = self._calc_pnl(trade["symbol"], trade["side"], trade["entry_price"], exit_price, trade["remaining_quantity"])
        r = self._calc_r_multiple(trade["side"], trade["entry_price"], exit_price, trade.get("stop_loss", 0))

        leg = {
            "fraction": round(trade["remaining_quantity"] / trade["initial_quantity"], 4) if trade["initial_quantity"] > 0 else 1.0,
            "exit_price": round(exit_price, 5),
            "quantity": trade["remaining_quantity"],
            "pnl": round(pnl, 2),
            "r_multiple": round(r, 3),
            "closed_at": datetime.utcnow().isoformat(),
            "label": "CLOSE",
        }

        trade["legs"].append(leg)
        trade["realized_pnl"] = round(trade.get("realized_pnl", 0) + pnl, 2)
        trade["remaining_quantity"] = 0.0
        trade["total_r"] = round(sum(l["r_multiple"] for l in trade["legs"]), 3)
        trade["status"] = "CLOSED"
        trade["exit_price"] = round(exit_price, 5)
        trade["closed_at"] = datetime.utcnow().isoformat()
        trade["updated_at"] = datetime.utcnow().isoformat()
        db.update("trades", trade_id, trade)
        return trade

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
                trade["unrealized_pnl"] = round(unrealized, 2)
                # R for remaining position
                r_unrealized = self._calc_r_multiple(trade["side"], trade["entry_price"], current_price, trade.get("stop_loss", 0))
                trade["total_r"] = round(sum(l["r_multiple"] for l in trade["legs"]) + r_unrealized, 3)
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
                    t["unrealized_pnl"] = round(self._calc_pnl(t["symbol"], t["side"], t["entry_price"], current_price, t["remaining_quantity"]), 2)
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
        trade["updated_at"] = datetime.utcnow().isoformat()
        db.update("trades", trade_id, trade)
        return trade

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
            
            # BE stop loss hit check
            if sl_at_be:
                be_hit = (side == "BUY" and current_price <= trade["entry_price"]) or (side == "SELL" and current_price >= trade["entry_price"])
                if be_hit:
                    result = self.full_close(trade["id"], current_price)
                    actions.append({"trade_id": trade["id"], "action": "BE_CLOSE", "price": current_price, "result": result})
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
                if updated:
                    updated["tp1_hit"] = True
                    updated["updated_at"] = datetime.utcnow().isoformat()
                    db.update("trades", trade["id"], updated)
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
                    t["unrealized_pnl"] = round(self._calc_pnl(t["symbol"], t["side"], t["entry_price"], current_price, t["remaining_quantity"]), 2)

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
        if not closed:
            return {"win_rate": 0, "avg_win": 0, "avg_loss": 0, "kelly_fraction": 0, "kelly_half": 0}

        wins = [t for t in closed if t.get("realized_pnl", 0) > 0]
        losses = [t for t in closed if t.get("realized_pnl", 0) <= 0]
        win_rate = len(wins) / len(closed) if closed else 0
        avg_win = sum(t.get("realized_pnl", 0) for t in wins) / len(wins) if wins else 0
        avg_loss = abs(sum(t.get("realized_pnl", 0) for t in losses) / len(losses)) if losses else 0

        # Kelly: f = (bp - q) / b where b = avg_win/avg_loss, p = win_rate, q = 1-p
        b = avg_win / avg_loss if avg_loss > 0 else 0
        p = win_rate
        q = 1 - p
        kelly = (b * p - q) / b if b > 0 else 0
        kelly = max(0, min(1, kelly))

        return {
            "win_rate": round(win_rate, 4),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(-avg_loss, 2),
            "kelly_fraction": round(kelly, 4),
            "kelly_half": round(kelly / 2, 4),
        }

    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        """Get recent closed trades."""
        trades = db.get_collection("trades")
        closed = sorted([t for t in trades if t.get("status") == "CLOSED"], key=lambda x: x.get("created_at", ""), reverse=True)
        return closed[:limit]


trade_lifecycle_service = TradeLifecycleService()
