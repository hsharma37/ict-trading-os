from typing import Dict, Optional
from datetime import datetime
from app.services.signal_engine import signal_engine
from app.services.order_service import order_service
from app.services.plan_service import plan_service
from app.services.market_data import market_service
from app.core.database import db

class BotEngine:
    def __init__(self):
        self.config = {
            "enabled": False,
            "risk_pct": 1.0,
            "account_balance": 10000.0,
            "max_trades_per_day": 3,
            "trades_today": 0,
            "last_reset": datetime.utcnow().date().isoformat()
        }

    def _reset_daily(self):
        today = datetime.utcnow().date().isoformat()
        if self.config["last_reset"] != today:
            self.config["last_reset"] = today
            self.config["trades_today"] = 0

    def set_config(self, config: Dict) -> Dict:
        self.config.update({k: v for k, v in config.items() if k in self.config})
        self._reset_daily()
        return self.config

    def status(self) -> Dict:
        self._reset_daily()
        return self.config

    def scan(self, auto_execute: bool = False) -> Dict:
        self._reset_daily()
        results = []
        symbols = ["NQ1!", "ES1!", "EURUSD", "GBPUSD", "XAUUSD", "USDJPY", "BTCUSD", "CL1!"]
        for symbol in symbols:
            signal = signal_engine.analyze(symbol)
            if signal:
                results.append(signal)
                if auto_execute:
                    self._try_execute_signal(signal)
        return {"scanned": len(symbols), "signals": results, "bot_status": self.config}

    def _try_execute_signal(self, signal: Dict) -> Optional[Dict]:
        if not self.config["enabled"] or self.config["trades_today"] >= self.config["max_trades_per_day"]:
            return None

        plan = self._find_live_plan(signal["symbol"], signal["sentiment"].upper())
        if not plan:
            return None

        current_price = market_service.get_price(signal["symbol"]).get("price", 0)
        entry_target = plan.get("entry_zone") or signal.get("entry_zone")
        if not entry_target:
            return None

        if abs(current_price - entry_target) / max(entry_target, 1) > 0.01:
            return None

        estimate = order_service.calculate_quantity(
            signal["symbol"], entry_target, plan.get("stop_loss"),
            account_balance=self.config["account_balance"], risk_pct=self.config["risk_pct"]
        )

        order = {
            "symbol": signal["symbol"],
            "side": "BUY" if signal["sentiment"] == "bullish" else "SELL",
            "quantity": estimate.get("quantity", 0),
            "entry_price": entry_target,
            "stop_loss": plan.get("stop_loss"),
            "take_profit_1": plan.get("take_profit_1"),
            "take_profit_2": plan.get("take_profit_2"),
            "take_profit_3": plan.get("take_profit_3"),
            "strategy": plan.get("strategy", "ICT"),
            "source": "AUTO-BOT",
            "plan_id": plan.get("id"),
            "bot_action": True
        }
        created = order_service.create_order(order)
        self.config["trades_today"] += 1
        plan_service.update_plan(plan.get("id"), {"status": "TRIGGERED", "signal_id": signal.get("id"), "updated_at": datetime.utcnow().isoformat()})
        return created

    def _find_live_plan(self, symbol: str, bias: str) -> Optional[Dict]:
        plans = plan_service.list_plans(status="OPEN", symbol=symbol)
        for plan in plans:
            if plan.get("bias") == bias:
                return plan
        return None

bot_engine = BotEngine()
