from typing import Dict, Optional
from datetime import datetime
from app.core.database import db
from app.services.market_data import MARKET_SPECS, market_service

class OrderService:
    def calculate_quantity(self, symbol: str, entry_price: float, stop_loss: float, account_balance: float = 10000.0, risk_pct: float = 1.0) -> Dict:
        # Canonicalize the symbol before lookup — MARKET_SPECS is keyed by exact
        # uppercase (e.g. "XAUUSD"). A non-canonical symbol ("xauusd") would miss
        # and fall to point_value=1.0, sizing gold ~100× too large (distance×1
        # instead of distance×100). Reject an unknown symbol rather than guess.
        symbol = (symbol or "").upper()
        spec = MARKET_SPECS.get(symbol)
        if spec is None:
            return {"symbol": symbol, "error": f"Unknown symbol '{symbol}' — cannot size safely without its contract spec."}
        distance = abs(entry_price - stop_loss)
        if distance <= 0:
            return {"symbol": symbol, "error": "Entry and stop loss must differ"}

        risk_amount = max(0.0, account_balance * (risk_pct / 100.0))
        qty = risk_amount / (distance * spec["point_value"])
        qty = max(spec.get("min_qty", 0.01), qty)
        qty = round(qty / spec.get("qty_step", 0.01)) * spec.get("qty_step", 0.01)
        return {
            "symbol": symbol,
            "entry_price": round(entry_price, 5),
            "stop_loss": round(stop_loss, 5),
            "risk_amount": round(risk_amount, 2),
            "risk_per_unit": round(distance * spec["point_value"], 5),
            "quantity": round(qty, 4),
            "unit": spec["unit"],
            "spec": spec
        }

    def create_order(self, order: Dict) -> Dict:
        order_payload = {
            "symbol": order["symbol"],
            "side": order["side"],
            "quantity": order["quantity"],
            "entry_price": order["entry_price"],
            "stop_loss": order.get("stop_loss"),
            "take_profit_1": order.get("take_profit_1"),
            "take_profit_2": order.get("take_profit_2"),
            "take_profit_3": order.get("take_profit_3"),
            "strategy": order.get("strategy"),
            "source": order.get("source", "AutoOrder"),
            "status": "OPEN",
            "created_at": datetime.utcnow().isoformat(),
            "plan_id": order.get("plan_id"),
            "bot_action": order.get("bot_action", False)
        }
        return db.insert("orders", order_payload)

    def list_orders(self, status: Optional[str] = None, symbol: Optional[str] = None) -> list:
        orders = db.get_collection("orders")
        if status:
            orders = [o for o in orders if o.get("status") == status]
        if symbol:
            orders = [o for o in orders if o.get("symbol") == symbol]
        return orders[::-1]

order_service = OrderService()
