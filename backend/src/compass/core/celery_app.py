"""Celery app: Redis broker only, no result backend (nothing retrieves task results)."""

from celery import Celery
from celery.schedules import crontab

from compass.core.config import get_settings

celery_app = Celery(
    "compass",
    broker=get_settings().redis_url,
    include=["compass.ingestion.tasks"],
)

# celery-types declares conf.timezone as a read-only property returning tzinfo
# -- but at runtime Config.__setattr__ is dynamic (dict-like) and does accept a
# string, which is exactly what crontab() below needs.
celery_app.conf.timezone = "Europe/Madrid"  # type: ignore[misc, assignment]
celery_app.conf.beat_schedule = {
    "daily-ingestion": {
        "task": "daily_ingestion",
        "schedule": crontab(hour=3, minute=0),
    },
}
