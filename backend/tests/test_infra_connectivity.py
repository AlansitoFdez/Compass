"""Confirms the local Docker services are reachable. Requires `docker compose up`."""

import psycopg
import redis

from compass.core.config import get_settings


def test_postgres_is_reachable() -> None:
    settings = get_settings()

    with psycopg.connect(settings.database_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone() == (1,)


def test_redis_is_reachable() -> None:
    settings = get_settings()

    client = redis.from_url(settings.redis_url)
    assert client.ping() is True
