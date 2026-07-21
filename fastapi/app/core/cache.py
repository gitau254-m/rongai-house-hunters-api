import redis.asyncio as redis
import json
from typing import Optional
from app.core.config import settings

# Create one Redis connection pool for the whole app.
# A pool manages multiple connections efficiently —
# instead of opening/closing a connection per request,
# FastAPI reuses connections from the pool.
redis_pool = redis.ConnectionPool.from_url(
    settings.redis_url,
    decode_responses=True,  # automatically decode bytes to strings
    max_connections=20,  # maximum simultaneous connections
)


def get_redis_client() -> redis.Redis:
    """
    Returns a Redis client using the shared connection pool.
    Used as a FastAPI dependency — same pattern as get_db().
    """
    return redis.Redis(connection_pool=redis_pool)


# ── Cache key constants ──────────────────────────────────────────────
# We define cache keys as constants so we never mistype them.
# A typo in a cache key is a hard-to-find bug:
# "houses:all" vs "house:all" — one letter difference, two separate caches.

HOUSES_ALL_KEY = "rhh:houses:all"  # all live houses, no filters
HOUSES_FILTER_KEY = "rhh:houses:filter:{filter_hash}"  # filtered results (varies per filter combo)
CARETAKER_KEY = "rhh:caretaker:{id}"  # individual caretaker profile

CACHE_TTL = 300  # 5 minutes — how long before cache expires and DB is queried again


async def get_cached(client: redis.Redis, key: str) -> Optional[dict]:
    """
    Reads from cache. Returns parsed data or None if not found/expired.
    """
    try:
        data = await client.get(key)
        if data:
            return json.loads(data)  # convert stored JSON string back to Python dict
        return None
    except Exception:
        # If Redis is down, we return None → code falls back to database
        # Cache failures should NEVER break the application
        return None


async def set_cached(client: redis.Redis, key: str, data, ttl: int = CACHE_TTL) -> None:
    """
    Writes data to cache with an expiry time.
    data is converted to JSON string for storage — Redis stores strings.
    """
    try:
        await client.set(
            key,
            json.dumps(data, default=str),  # default=str handles UUID and datetime objects
            ex=ttl
        )
    except Exception:
        # If Redis is down, we skip caching but still return data from DB
        # Never crash because of a cache write failure
        pass


async def invalidate_cache(client: redis.Redis, pattern: str) -> None:
    """
    Deletes cached keys matching a pattern.
    Called when data changes — so stale data is never served.

    Example: when a new listing is created:
    invalidate_cache(client, "rhh:houses:*")
    → deletes all house cache entries so next request gets fresh data
    """
    try:
        keys = await client.keys(pattern)
        if keys:
            await client.delete(*keys)
    except Exception:
        pass