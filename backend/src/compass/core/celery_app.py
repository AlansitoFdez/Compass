"""Celery app: Redis broker only, no result backend (nothing retrieves task results)."""

from celery import Celery
from celery.schedules import crontab

from compass.core.config import get_settings

celery_app = Celery(
    "compass",
    broker=get_settings().redis_url,
    include=["compass.ingestion.tasks"],
)

# celery-types tipa conf.timezone como una propiedad de solo lectura que
# devuelve tzinfo -- pero en runtime, Config.__setattr__ es dinámico (como un
# dict) y sí acepta un string, que es justo lo que necesita crontab() más abajo.
celery_app.conf.timezone = "Europe/Madrid"  # type: ignore[misc, assignment]
celery_app.conf.beat_schedule = {
    "daily-ingestion": {
        "task": "daily_ingestion",
        "schedule": crontab(hour=3, minute=0),
    },
}
