"""Confirms the local Docker services are reachable. Requires `docker compose up`."""

import psycopg
import redis

from compass.core.config import get_settings


def test_postgres_is_reachable() -> None:
    """Protects against a misconfigured DATABASE_URL or a Postgres that isn't listening.

    Without this, that failure would only surface later, as a confusing
    error deep inside some unrelated test that happens to touch the DB first.
    """
    settings = get_settings()

    with psycopg.connect(settings.database_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone() == (1,)


def test_redis_is_reachable() -> None:
    """Protects against a misconfigured REDIS_URL or a Redis that isn't listening.

    Both the Celery broker and the ingestion checkpoints depend on this --
    a silent failure here would surface as an unrelated Celery or checkpoint
    test failing for the wrong reason.
    """
    settings = get_settings()

    client = redis.from_url(settings.redis_url)
    assert client.ping() is True
