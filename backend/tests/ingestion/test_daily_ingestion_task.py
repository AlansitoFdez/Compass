"""Tests for the daily ingestion Celery task — real engine/session, mocked orchestration."""

from collections.abc import Iterator
from unittest.mock import patch

import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool

from compass.core.db import create_task_engine
from compass.core.redis_client import get_redis_client
from compass.ingestion.tasks import LOCK_KEY, daily_ingestion_task


@pytest.fixture(autouse=True)
def _clean_lock() -> Iterator[None]:
    """Deletes the ingestion lock key before and after each test.

    So tests can't see each other's leftover lock.
    """
    get_redis_client().delete(LOCK_KEY)
    yield
    get_redis_client().delete(LOCK_KEY)


def test_create_task_engine_uses_null_pool() -> None:
    """Protects the choice behind `create_task_engine()`.

    No connection pooling across event loops.
    """
    engine = create_task_engine()
    assert isinstance(engine.pool, NullPool)


def test_create_task_engine_returns_a_fresh_engine_each_call() -> None:
    """Protects against a shared module-level engine sneaking back in.

    Each call must return a new instance.
    """
    first = create_task_engine()
    second = create_task_engine()
    assert first is not second


def test_daily_ingestion_task_runs_end_to_end_with_mocked_orchestration() -> None:
    """Protects the end-to-end wiring: the real lock and event-loop plumbing, mocked orchestration.

    The task must return whatever `run_daily_ingestion` reports.
    """

    async def fake_run_daily_ingestion(client: httpx2.Client, session: AsyncSession) -> int:
        """Stands in for the real orchestration: reports 3 tenders persisted."""
        return 3

    with patch("compass.ingestion.tasks.run_daily_ingestion", side_effect=fake_run_daily_ingestion):
        result = daily_ingestion_task()

    assert result == 3


def test_daily_ingestion_task_skips_when_a_previous_run_holds_the_lock() -> None:
    """Protects against two overlapping runs -- see the comment in tasks.py on why that's unsafe."""
    held_by_another_run = get_redis_client().lock(LOCK_KEY, timeout=60)
    assert held_by_another_run.acquire(blocking=False)

    try:
        with patch("compass.ingestion.tasks.run_daily_ingestion") as mocked:
            result = daily_ingestion_task()

        assert result == 0
        mocked.assert_not_called()
    finally:
        held_by_another_run.release()


def test_daily_ingestion_task_releases_the_lock_after_a_successful_run() -> None:
    """Protects against a successful run leaving the lock held.

    That would block every future run forever.
    """

    async def fake_run_daily_ingestion(client: httpx2.Client, session: AsyncSession) -> int:
        """Stands in for the real orchestration: reports 1 tender persisted."""
        return 1

    with patch("compass.ingestion.tasks.run_daily_ingestion", side_effect=fake_run_daily_ingestion):
        daily_ingestion_task()

    lock = get_redis_client().lock(LOCK_KEY, timeout=60)
    assert lock.acquire(blocking=False)
    lock.release()


def test_daily_ingestion_task_releases_the_lock_even_if_the_run_fails() -> None:
    """Protects the `finally: lock.release()` path: a crash must not leave the lock stuck held."""

    async def failing_run_daily_ingestion(client: httpx2.Client, session: AsyncSession) -> int:
        """Stands in for the real orchestration: simulates a run that crashes."""
        raise RuntimeError("boom")

    with (
        patch(
            "compass.ingestion.tasks.run_daily_ingestion", side_effect=failing_run_daily_ingestion
        ),
        pytest.raises(RuntimeError),
    ):
        daily_ingestion_task()

    lock = get_redis_client().lock(LOCK_KEY, timeout=60)
    assert lock.acquire(blocking=False)
    lock.release()
