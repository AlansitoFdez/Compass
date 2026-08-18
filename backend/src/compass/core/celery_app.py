"""Celery app: Redis broker only, no result backend (nothing retrieves task results)."""

from celery import Celery
from celery.schedules import crontab

from compass.core.config import get_settings

celery_app = Celery(
    "compass",
    broker=get_settings().redis_url,
    include=["compass.ingestion.tasks"],
)

celery_app.conf.timezone = "Europe/Madrid"
celery_app.conf.beat_schedule = {
    "daily-ingestion": {
        "task": "daily_ingestion",
        "schedule": crontab(hour=3, minute=0),
    },
}
