from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
import json
import logging

from app.database import get_db
from app.models.alert_history import AlertHistory
from app.models.alert import Alert
from app.core.event_bus import event_bus, AlertTriggeredEvent

logger = logging.getLogger(__name__)
router = APIRouter()

# ────────────────────────────────────────────────
# WebSocket: Alert Stream
# ────────────────────────────────────────────────

active_connections: List[WebSocket] = []


@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """WebSocket for real-time alert delivery."""
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Keep connection alive, receive ping from client
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception:
        if websocket in active_connections:
            active_connections.remove(websocket)


async def broadcast_alert(alert_data: Dict[str, Any]):
    """Broadcast an alert to all connected WebSocket clients."""
    message = json.dumps({"type": "alert", "data": alert_data})
    disconnected = []
    for conn in active_connections:
        try:
            await conn.send_text(message)
        except Exception:
            disconnected.append(conn)
    for conn in disconnected:
        if conn in active_connections:
            active_connections.remove(conn)


# ────────────────────────────────────────────────
# Alert History
# ────────────────────────────────────────────────

@router.get("/history", summary="Alert trigger history")
async def list_alert_history(
    user_id: UUID,
    alert_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    statement = select(AlertHistory).where(AlertHistory.user_id == user_id)
    if alert_type:
        statement = statement.where(AlertHistory.alert_type == alert_type)
    statement = statement.order_by(AlertHistory.triggered_at.desc()).offset(skip).limit(limit)
    return db.exec(statement).all()


@router.post("/trigger", summary="Trigger an alert (for testing)")
async def trigger_alert(
    user_id: UUID,
    alert_id: UUID,
    trigger_price: Optional[float] = None,
    trigger_data: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
):
    """Manually trigger an alert and record it in history."""
    alert = db.get(Alert, alert_id)
    if not alert:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alert not found")

    history = AlertHistory(
        user_id=user_id,
        alert_id=alert_id,
        symbol=alert.symbol,
        alert_type=alert.alert_type,
        message=alert.message,
        severity="info",
        trigger_price=trigger_price,
        trigger_data=trigger_data or {},
        delivery_status="delivered",
    )
    db.add(history)
    db.commit()
    db.refresh(history)

    # Publish event
    event_bus.publish_alert_triggered(
        AlertTriggeredEvent(
            alert_id=str(alert_id),
            symbol=alert.symbol,
            alert_type=alert.alert_type,
            message=alert.message or "Alert triggered",
            triggered_at=datetime.utcnow().isoformat() + "Z",
            severity="info",
        )
    )

    return {"status": "triggered", "history_id": history.id}
