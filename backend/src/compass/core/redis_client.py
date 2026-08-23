"""Shared synchronous Redis client: Celery's broker and the ingestion checkpoints."""

from functools import lru_cache

import redis

from compass.core.config import get_settings


@lru_cache
def get_redis_client() -> redis.Redis:
    """The Redis client shared by the whole process.

    `decode_responses=True` makes every read come back as `str` instead of the
    default `bytes`, which is what lets the checkpoint helpers store and
    compare plain strings.

    Returns:
        A cached client. Connections underneath are pooled and opened lazily,
        so building it never touches the network.
    """
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
