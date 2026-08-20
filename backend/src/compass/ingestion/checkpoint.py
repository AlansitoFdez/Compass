"""Tracks ingestion progress across the ATOM feed: resuming after a mid-run
failure, and skipping content a previous complete run already ingested.
"""

from typing import cast

from compass.core.redis_client import get_redis_client

RESUME_URL_KEY = "ingestion:atom:resume_url"
PENDING_HIGH_WATER_MARK_KEY = "ingestion:atom:pending_high_water_mark"
HIGH_WATER_MARK_KEY = "ingestion:atom:high_water_mark"


def _get_str(key: str) -> str | None:
    # redis-py types .get() as bytes | str | None, since it depends on the
    # client's decode_responses setting -- get_redis_client() always sets it
    # True, so this is always really a str, never bytes.
    return cast("str | None", get_redis_client().get(key))


def get_resume_url() -> str | None:
    return _get_str(RESUME_URL_KEY)


def set_resume_url(url: str) -> None:
    get_redis_client().set(RESUME_URL_KEY, url)


def clear_resume_url() -> None:
    get_redis_client().delete(RESUME_URL_KEY)


def get_high_water_mark() -> str | None:
    """The newest atom:updated value the last fully completed run ingested —
    entries at or before this point were already processed and don't need
    to be walked again.
    """
    return _get_str(HIGH_WATER_MARK_KEY)


def clear_high_water_mark() -> None:
    get_redis_client().delete(HIGH_WATER_MARK_KEY)


def get_pending_high_water_mark() -> str | None:
    return _get_str(PENDING_HIGH_WATER_MARK_KEY)


def clear_pending_high_water_mark() -> None:
    get_redis_client().delete(PENDING_HIGH_WATER_MARK_KEY)


def set_pending_high_water_mark(updated_at: str) -> None:
    """Set once, right after fetching the first page of a fresh run: the
    newest entry's atom:updated for the run now in progress.

    Kept separate from HIGH_WATER_MARK_KEY (the real threshold future runs
    stop at) until complete_run() promotes it. Advancing the real one early —
    before this run's tenders are confirmed committed — would mean losing
    them forever: the whole point of the high-water mark is that future runs
    never re-fetch what it covers, so it must never get ahead of what's
    actually durable.
    """
    get_redis_client().set(PENDING_HIGH_WATER_MARK_KEY, updated_at)


def complete_run() -> None:
    """Called by the caller of ingest_atom_feed(), once, after its own writes
    are durably committed: promotes this run's pending high-water mark to
    the real one, and clears the per-run resume checkpoint — the run is
    done, there's nothing left to resume.
    """
    client = get_redis_client()
    pending = client.get(PENDING_HIGH_WATER_MARK_KEY)
    if pending is not None:
        client.set(HIGH_WATER_MARK_KEY, pending)
    client.delete(RESUME_URL_KEY, PENDING_HIGH_WATER_MARK_KEY)
