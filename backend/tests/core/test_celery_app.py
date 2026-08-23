"""Tests for the Celery app configuration."""

from celery.schedules import crontab

import compass.ingestion.tasks  # noqa: F401 — importing registers the task
from compass.core.celery_app import celery_app


def test_celery_app_uses_madrid_timezone() -> None:
    """Protects against the beat crontab firing at the wrong local hour.

    `hour=3` in `celery_app.py` is only "3am in Madrid" as long as
    `conf.timezone` actually holds that value -- this catches it silently
    reverting to Celery's UTC default.
    """
    # Same celery-types mismatch as in celery_app.py: at runtime this is a
    # str, not the tzinfo the stub advertises.
    assert celery_app.conf.timezone == "Europe/Madrid"  # type: ignore[comparison-overlap]


def test_daily_ingestion_task_is_registered() -> None:
    """Protects against `tasks.py` never being imported, or the task being renamed.

    Either would leave `"daily_ingestion"` unroutable: beat would enqueue a
    task name no worker recognizes, and it would fail silently at runtime.
    """
    assert "daily_ingestion" in celery_app.tasks


def test_beat_schedule_runs_daily_at_3am_madrid() -> None:
    """Protects against the beat schedule drifting from the documented 03:00 Europe/Madrid."""
    entry = celery_app.conf.beat_schedule["daily-ingestion"]
    assert entry["task"] == "daily_ingestion"
    assert entry["schedule"] == crontab(hour=3, minute=0)
