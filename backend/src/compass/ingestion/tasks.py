"""The daily ingestion Celery task: bridges the sync Celery model into our async pipeline."""

import asyncio
import logging
import sys
import time

import httpx2
from sqlalchemy.ext.asyncio import async_sessionmaker

from compass.core.celery_app import celery_app
from compass.core.db import create_task_engine
from compass.ingestion.daily_ingestion import run_daily_ingestion

logger = logging.getLogger(__name__)


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
