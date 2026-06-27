"""
Market data service — caching, aggregation, and real-time price feed management.

Will integrate with Redis for price caching and WebSocket broadcasting.
"""
import redis
from app.config import settings

redis_client = redis.from_url(settings.redis_url, decode_responses=True)


def get_cached_price(symbol: str) -> dict | None:
    """Get latest price from Redis cache (if available)."""
    data = redis_client.hgetall(f"price:{symbol.upper()}")
    return data if data else None


def set_cached_price(symbol: str, price_data: dict, ttl: int = 60) -> None:
    """Cache latest price in Redis."""
    redis_client.hset(f"price:{symbol.upper()}", mapping=price_data)
    redis_client.expire(f"price:{symbol.upper()}", ttl)
