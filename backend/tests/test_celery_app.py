"""Tests for the Celery app configuration."""

from celery.schedules import crontab

import compass.ingestion.tasks  # noqa: F401 — importing registers the task
from compass.core.celery_app import celery_app


def test_celery_app_uses_madrid_timezone() -> None:
    # Mismo desajuste de celery-types que en celery_app.py: en runtime esto
    # es un str, no el tzinfo que el stub anuncia.
    assert celery_app.conf.timezone == "Europe/Madrid"  # type: ignore[comparison-overlap]


def test_daily_ingestion_task_is_registered() -> None:
    assert "daily_ingestion" in celery_app.tasks


def test_beat_schedule_runs_daily_at_3am_madrid() -> None:
    entry = celery_app.conf.beat_schedule["daily-ingestion"]
    assert entry["task"] == "daily_ingestion"
    assert entry["schedule"] == crontab(hour=3, minute=0)
