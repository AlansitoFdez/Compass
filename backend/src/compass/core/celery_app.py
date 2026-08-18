"""Celery app: Redis broker only, no result backend (nothing retrieves task results)."""

from celery import Celery

from compass.core.config import get_settings

celery_app = Celery("compass", broker=get_settings().redis_url)
