"""Shared synchronous Redis client, used by the ingestion pipeline (Celery, 1.9+)."""

from functools import lru_cache

import redis

from compass.core.config import get_settings


@lru_cache
def get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
