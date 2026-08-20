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
    get_redis_client().delete(LOCK_KEY)
    yield
    get_redis_client().delete(LOCK_KEY)


def test_create_task_engine_uses_null_pool() -> None:
    engine = create_task_engine()
    assert isinstance(engine.pool, NullPool)


def test_create_task_engine_returns_a_fresh_engine_each_call() -> None:
    first = create_task_engine()
    second = create_task_engine()
    assert first is not second


def test_daily_ingestion_task_runs_end_to_end_with_mocked_orchestration() -> None:
    async def fake_run_daily_ingestion(client: httpx2.Client, session: AsyncSession) -> int:
        return 3

    with patch("compass.ingestion.tasks.run_daily_ingestion", side_effect=fake_run_daily_ingestion):
        result = daily_ingestion_task()

    assert result == 3


def test_daily_ingestion_task_skips_when_a_previous_run_holds_the_lock() -> None:
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
    async def fake_run_daily_ingestion(client: httpx2.Client, session: AsyncSession) -> int:
        return 1

    with patch("compass.ingestion.tasks.run_daily_ingestion", side_effect=fake_run_daily_ingestion):
        daily_ingestion_task()

    lock = get_redis_client().lock(LOCK_KEY, timeout=60)
    assert lock.acquire(blocking=False)
    lock.release()


def test_daily_ingestion_task_releases_the_lock_even_if_the_run_fails() -> None:
    async def failing_run_daily_ingestion(client: httpx2.Client, session: AsyncSession) -> int:
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
