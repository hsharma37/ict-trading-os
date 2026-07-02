"""Alerts Router — Price alert management."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from app.services.alert_service import alert_service

router = APIRouter(prefix="/alerts", tags=["Alerts"])


class CreateAlertRequest(BaseModel):
    symbol: str
    alert_type: str = Field(default="price", description="Type: price, percent_change, trend")
    condition: str = Field(default="above", description="Condition: above, below, crosses_up, crosses_down, percent_change")
    threshold: float
    message: Optional[str] = None


class CheckAlertsResponse(BaseModel):
    triggered: List[dict]
    checked: int


@router.post("")
def create_alert(request: CreateAlertRequest):
    """Create a new price alert."""
    try:
        return alert_service.create_alert(
            symbol=request.symbol,
            alert_type=request.alert_type,
            condition=request.condition,
            threshold=request.threshold,
            message=request.message,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def list_alerts(active_only: bool = False):
    """List all alerts."""
    try:
        return {"alerts": alert_service.list_alerts(active_only), "stats": alert_service.get_stats()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
def list_history():
    """List triggered alert history."""
    try:
        return {"history": alert_service.list_history()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{alert_id}")
def delete_alert(alert_id: str):
    """Delete an alert."""
    try:
        result = alert_service.delete_alert(alert_id)
        if not result.get("deleted"):
            raise HTTPException(status_code=404, detail=result.get("error", "Alert not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{alert_id}/toggle")
def toggle_alert(alert_id: str):
    """Toggle alert active status."""
    try:
        result = alert_service.toggle_alert(alert_id)
        if result.get("error"):
            raise HTTPException(status_code=404, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check")
def check_alerts():
    """Manually check all alerts and trigger if conditions met."""
    try:
        triggered = alert_service.check_alerts()
        return {"triggered": triggered, "checked": len(alert_service.list_alerts(active_only=True)) + len(triggered)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
