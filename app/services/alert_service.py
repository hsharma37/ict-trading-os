"""Alert service for price-based alerts."""
import time
import threading
from typing import Dict, List, Optional
from datetime import datetime
from app.core.database import db
from app.services.market_data import market_service


class AlertService:
    """Manage price alerts with triggering logic."""

    def __init__(self):
        self._lock = threading.Lock()
        self._last_check = 0

    def create_alert(
        self,
        symbol: str,
        alert_type: str,
        condition: str,
        threshold: float,
        message: str = "",
    ) -> Dict:
        """Create a new alert."""
        alert = {
            "id": f"ALR-{int(datetime.utcnow().timestamp()*1000)}",
            "symbol": symbol.upper(),
            "alert_type": alert_type,
            "condition": condition,
            "threshold": threshold,
            "message": message or f"{symbol} {condition} {threshold}",
            "is_active": True,
            "triggered_at": None,
            "created_at": datetime.utcnow().isoformat(),
        }
        return db.insert("alerts", alert)

    def list_alerts(self, active_only: bool = False) -> List[Dict]:
        """List all alerts."""
        alerts = db.get_collection("alerts")
        if active_only:
            alerts = [a for a in alerts if a.get("is_active", False)]
        return sorted(alerts, key=lambda x: x.get("created_at", ""), reverse=True)

    def list_history(self) -> List[Dict]:
        """List triggered alert history."""
        alerts = db.get_collection("alerts")
        triggered = [a for a in alerts if a.get("triggered_at") is not None]
        return sorted(triggered, key=lambda x: x.get("triggered_at", ""), reverse=True)

    def delete_alert(self, alert_id: str) -> Dict:
        """Delete an alert."""
        alerts = db.get_collection("alerts")
        for i, a in enumerate(alerts):
            if a.get("id") == alert_id:
                alerts.pop(i)
                return {"deleted": True, "id": alert_id}
        return {"deleted": False, "error": "Alert not found"}

    def toggle_alert(self, alert_id: str) -> Dict:
        """Toggle alert active status."""
        alert = db.find_one("alerts", alert_id)
        if not alert:
            return {"error": "Alert not found"}
        alert["is_active"] = not alert.get("is_active", False)
        alert["updated_at"] = datetime.utcnow().isoformat()
        db.update("alerts", alert_id, alert)
        return alert

    def check_alerts(self) -> List[Dict]:
        """Check all active alerts against current prices and trigger."""
        with self._lock:
            if time.time() - self._last_check < 5:
                return []
            self._last_check = time.time()

        alerts = self.list_alerts(active_only=True)
        triggered = []
        for alert in alerts:
            live = market_service.get_price(alert["symbol"])
            price = live.get("price", 0)
            if price <= 0:
                continue

            condition = alert.get("condition", "")
            threshold = alert.get("threshold", 0)
            triggered_now = False

            if condition == "above" and price > threshold:
                triggered_now = True
            elif condition == "below" and price < threshold:
                triggered_now = True
            elif condition == "crosses_up" and price >= threshold:
                triggered_now = True
            elif condition == "crosses_down" and price <= threshold:
                triggered_now = True
            elif condition == "percent_change" and abs(live.get("change_pct", 0)) >= threshold:
                triggered_now = True

            if triggered_now:
                alert["is_active"] = False
                alert["triggered_at"] = datetime.utcnow().isoformat()
                alert["triggered_price"] = price
                alert["triggered_change_pct"] = live.get("change_pct", 0)
                db.update("alerts", alert["id"], alert)
                triggered.append(alert)

        return triggered

    def get_stats(self) -> Dict:
        """Get alert statistics."""
        all_alerts = db.get_collection("alerts")
        active = len([a for a in all_alerts if a.get("is_active", False)])
        triggered = len([a for a in all_alerts if a.get("triggered_at")])
        total = len(all_alerts)
        return {
            "total": total,
            "active": active,
            "triggered": triggered,
            "inactive": total - active - triggered,
        }


alert_service = AlertService()
