from typing import Dict, List, Optional
from datetime import datetime
from app.core.database import db

class PlanService:
    def create_plan(self, plan: Dict) -> Dict:
        payload = {
            "symbol": plan["symbol"],
            "bias": plan.get("bias", "NEUTRAL"),
            "entry_zone": plan.get("entry_zone"),
            "stop_loss": plan.get("stop_loss"),
            "take_profit_1": plan.get("take_profit_1"),
            "take_profit_2": plan.get("take_profit_2"),
            "take_profit_3": plan.get("take_profit_3"),
            "strategy": plan.get("strategy", "ICT"),
            "narrative": plan.get("narrative", ""),
            "tags": plan.get("tags", []),
            "session": plan.get("session", ""),
            "status": plan.get("status", "OPEN"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        return db.insert("plans", payload)

    def list_plans(self, status: Optional[str] = None, symbol: Optional[str] = None) -> List[Dict]:
        plans = db.get_collection("plans")
        if status:
            plans = [p for p in plans if p.get("status") == status]
        if symbol:
            plans = [p for p in plans if p.get("symbol") == symbol]
        return plans[::-1]

    def get_plan(self, plan_id: str) -> Dict:
        return next((p for p in db.get_collection("plans") if p.get("id") == plan_id), {})

    def update_plan(self, plan_id: str, updates: Dict) -> Dict:
        plan = self.get_plan(plan_id)
        if not plan:
            return {}
        merged = {**plan, **updates, "updated_at": datetime.utcnow().isoformat()}
        return db.update("plans", plan_id, merged)

plan_service = PlanService()
