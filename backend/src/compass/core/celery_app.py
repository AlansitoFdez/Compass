"""Celery app: Redis broker only, no result backend (nothing retrieves task results)."""

from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

from compass.core.config import get_settings

celery_app = Celery(
    "compass",
    broker=get_settings().redis_url,
    include=["compass.ingestion.tasks", "compass.matching.tasks"],
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
    # A fixed interval, not a crontab: this only needs to run "often enough",
    # not at a specific wall-clock time. Runs after daily_ingestion (03:00)
    # will normally find a backlog of that day's new tenders and drain it
    # within one run (see matching.tasks._generate_embeddings) well before
    # the next tick -- 15 minutes is slack, not the expected latency.
    "generate-embeddings": {
        "task": "generate_embeddings",
        "schedule": timedelta(minutes=15),
    },
}
