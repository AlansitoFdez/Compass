"""Tracks the last successfully-processed ATOM feed URL, so ingestion can resume after a failure."""

from compass.core.redis_client import get_redis_client

CHECKPOINT_KEY = "ingestion:atom:last_processed_url"


def get_last_processed_atom_url() -> str | None:
    return get_redis_client().get(CHECKPOINT_KEY)


def set_last_processed_atom_url(url: str) -> None:
    get_redis_client().set(CHECKPOINT_KEY, url)


def clear_last_processed_atom_url() -> None:
    """Called once the feed is fully drained — the next run starts fresh, it doesn't resume."""
    get_redis_client().delete(CHECKPOINT_KEY)
