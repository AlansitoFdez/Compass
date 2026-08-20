"""The daily ingestion Celery task: bridges the sync Celery model into our async pipeline."""

import asyncio
import logging
import sys
import time

import httpx2
from redis.exceptions import LockError
from sqlalchemy.ext.asyncio import async_sessionmaker

from compass.core.celery_app import celery_app
from compass.core.db import create_task_engine
from compass.core.redis_client import get_redis_client
from compass.ingestion.daily_ingestion import run_daily_ingestion

logger = logging.getLogger(__name__)

LOCK_KEY = "ingestion:daily_ingestion:lock"
# Generosamente por encima de cualquier duración real observada (corridas
# incrementales de segundos tras el fix de la 1.11; el peor caso documentado
# en la 1.9 -- un arranque en frío con meses de backlog -- tardó minutos, no
# horas). Si una corrida de verdad superase esto, el lock expira solo: se
# prefiere arriesgar un solape excepcional antes que bloquear la ingesta para
# siempre por un proceso que murió sin liberar el lock.
LOCK_TIMEOUT_SECONDS = 3600


async def _run() -> int:
    engine = create_task_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        with httpx2.Client(timeout=60) as client:
            async with session_factory() as session:
                # run_daily_ingestion commits periodically (and at the end)
                # by itself now — see its docstring for why.
                return await run_daily_ingestion(client, session)
    finally:
        await engine.dispose()


@celery_app.task(name="daily_ingestion")
def daily_ingestion_task() -> int:
    lock = get_redis_client().lock(LOCK_KEY, timeout=LOCK_TIMEOUT_SECONDS)
    if not lock.acquire(blocking=False):
        # Dos corridas a la vez escribirían el mismo checkpoint sin saber la
        # una de la otra -- páginas saltadas, o una marca de agua promovida
        # con el valor equivocado (ver phase1.11.md, paso 3). Se salta esta
        # corrida en vez de arriesgarse a corromper el checkpoint.
        logger.warning("daily_ingestion: previous run still in progress, skipping")
        return 0

    try:
        logger.info("daily_ingestion: starting")
        start = time.monotonic()

        try:
            if sys.platform == "win32":
                count = asyncio.run(_run(), loop_factory=asyncio.SelectorEventLoop)
            else:
                count = asyncio.run(_run())
        except Exception:
            logger.exception("daily_ingestion: failed")
            raise

        elapsed = time.monotonic() - start
        logger.info("daily_ingestion: finished, %d tenders persisted in %.1fs", count, elapsed)
        return count
    finally:
        try:
            lock.release()
        except LockError:
            # Ya expiró solo (corrida más larga que LOCK_TIMEOUT_SECONDS) o
            # ya lo liberó otra cosa -- no hay nada que deshacer aquí.
            logger.warning("daily_ingestion: lock already expired or released")
