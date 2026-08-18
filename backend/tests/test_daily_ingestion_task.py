"""Tests for the daily ingestion Celery task — real engine/session, mocked orchestration."""

from unittest.mock import patch

import httpx2
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool

from compass.core.db import create_task_engine
from compass.ingestion.tasks import daily_ingestion_task


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
