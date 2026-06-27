from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date
import logging

from app.database import get_db
from app.models.alert import Alert
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)
router = APIRouter()

# ────────────────────────────────────────────────
# Alert Rules
# ────────────────────────────────────────────────

@router.get("/")
async def list_alerts(
    user_id: UUID,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """List alerts for a user."""
    statement = select(Alert).where(Alert.user_id == user_id)
    if is_active is not None:
        statement = statement.where(Alert.is_active == is_active)
    statement = statement.order_by(Alert.created_at.desc())
    alerts = db.exec(statement).all()
    return [
        {
            "id": a.id,
            "symbol": a.symbol,
            "alert_type": a.alert_type,
            "condition": a.condition,
            "message": a.message,
            "is_active": a.is_active,
            "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in alerts
    ]

@router.post("/", status_code=201)
async def create_alert(
    user_id: UUID,
    symbol: str,
    alert_type: str,  # price, ict_pattern, sentiment, risk, custom
    condition: Dict[str, Any],
    message: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Create a new alert rule."""
    alert = Alert(
        id=UUID(int=0),  # Will be auto-generated
        user_id=user_id,
        symbol=symbol,
        alert_type=alert_type,
        condition=condition,
        message=message,
        is_active=True,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return {
        "id": alert.id,
        "symbol": alert.symbol,
        "alert_type": alert.alert_type,
        "condition": alert.condition,
        "is_active": alert.is_active,
    }

@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete an alert rule."""
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.delete(alert)
    db.commit()
    return {"status": "deleted", "alert_id": alert_id}

# ────────────────────────────────────────────────
# Sentiment Analysis
# ────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_sentiment(
    text: str,
    context: Optional[str] = None,
):
    """
    Analyze sentiment of news, social media, or market commentary.
    """
    ai = AIService()

    system_prompt = """You are a financial sentiment analyst specializing in forex and ICT trading.
Analyze the provided text for market sentiment. Consider:
- Overall tone (bullish, bearish, neutral)
- Key themes and drivers
- Fear/greed indicators
- ICT-specific signals (liquidity mentions, structure break mentions, etc.)

Respond in JSON format:
{
  "sentiment": "bullish|bearish|neutral",
  "confidence": 0.0-1.0,
  "tone": "...",
  "key_themes": ["..."],
  "fear_greed_score": 1-100,
  "ict_signals": ["..."],
  "summary": "..."
}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Analyze this market text:\n\n{text}\n\n{context or ''}"},
    ]

    try:
        response = await ai.chat(messages, temperature=0.3)
        content = response.get("message", {}).get("content", "")

        import json
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = json.loads(content)
        return result
    except Exception as e:
        logger.error(f"Sentiment analysis error: {e}")
        return {"error": str(e), "raw_response": content if 'content' in dir() else None}
    finally:
        await ai.close()
