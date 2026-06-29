"""
Event Bus — Redis pub/sub for cross-service communication.

All services publish events here; downstream services subscribe
and react. Events are typed dataclasses for structured routing.
"""
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

import redis
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TradeOpenedEvent:
    trade_id: str
    symbol: str
    direction: str
    entry_price: Optional[float]
    lot_size: Optional[float]
    leverage: int
    risk_amount: Optional[float]
    timestamp: str
    source: str = "manual"


@dataclass
class TradeClosedEvent:
    trade_id: str
    exit_price: Optional[float]
    pnl: Optional[float]
    pnl_pips: Optional[float]
    outcome: Optional[str]
    exit_time: str
    timestamp: str


@dataclass
class AlertTriggeredEvent:
    alert_id: str
    symbol: str
    alert_type: str
    message: str
    triggered_at: str
    severity: str = "info"


@dataclass
class DailyRiskBreachedEvent:
    user_id: str
    date: str
    daily_loss: float
    limit: float
    reason: str
    timestamp: str


@dataclass
class SuggestionCreatedEvent:
    suggestion_id: str
    trade_id: str
    symbol: str
    setup_score: float
    confidence: float
    timestamp: str


class EventBus:
    """Redis-backed event bus for publishing and subscribing to events."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.redis_url
        self._redis: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None

    def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    def publish(self, channel: str, event: Any) -> bool:
        """Publish an event to a Redis channel."""
        try:
            r = self._get_redis()
            payload = json.dumps({
                "type": event.__class__.__name__,
                "data": asdict(event),
                "published_at": datetime.utcnow().isoformat() + "Z",
            }, default=str)
            r.publish(channel, payload)
            logger.info(f"Published {event.__class__.__name__} to {channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            return False

    def publish_trade_opened(self, event: TradeOpenedEvent) -> bool:
        return self.publish("events:trades", event)

    def publish_trade_closed(self, event: TradeClosedEvent) -> bool:
        return self.publish("events:trades", event)

    def publish_alert_triggered(self, event: AlertTriggeredEvent) -> bool:
        return self.publish("events:alerts", event)

    def publish_daily_risk_breached(self, event: DailyRiskBreachedEvent) -> bool:
        return self.publish("events:risk", event)

    def publish_suggestion_created(self, event: SuggestionCreatedEvent) -> bool:
        return self.publish("events:suggestions", event)

    def get_connection_status(self) -> Dict[str, Any]:
        """Return Redis connection health status."""
        try:
            r = self._get_redis()
            info = r.ping()
            return {"connected": info, "redis_url": self.redis_url}
        except Exception as e:
            return {"connected": False, "error": str(e)}


# Global singleton
event_bus = EventBus()
