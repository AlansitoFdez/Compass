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
from compass.ingestion.historical_loader import load_recent_months

logger = logging.getLogger(__name__)

LOCK_KEY = "ingestion:daily_ingestion:lock"
# Generously above any observed real duration (incremental runs take seconds
# after the 1.11 fix; the worst case documented in 1.9 -- a cold start with
# months of backlog -- took minutes, not hours). If a real run ever exceeded
# this, the lock expires on its own: an occasional overlap is preferred over
# blocking ingestion forever because a process died without releasing it.
LOCK_TIMEOUT_SECONDS = 3600


async def _run() -> int:
    """Runs one ingestion inside its own event loop and engine.

    Builds a throwaway `AsyncEngine` via `create_task_engine()` -- see its
    docstring for why a Celery task can't reuse the module-level `engine` --
    and disposes it in `finally`, so nothing outlives this call.
    """
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
    """Celery entry point for the daily ingestion, guarded by a Redis lock.

    Returns:
        How many tenders matched the IT vertical and were persisted; `0` if
        this run was skipped because a previous one was still in progress.
    """
    lock = get_redis_client().lock(LOCK_KEY, timeout=LOCK_TIMEOUT_SECONDS)
    if not lock.acquire(blocking=False):
        # Two concurrent runs would write the same checkpoint without knowing
        # about each other -- skipped pages, or a high-water mark promoted
        # with the wrong value (see phase1.11.md, step 3). This run is
        # skipped rather than risking a corrupted checkpoint.
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
            # Already expired on its own (a run longer than
            # LOCK_TIMEOUT_SECONDS) or already released by something else --
            # there is nothing to undo here.
            logger.warning("daily_ingestion: lock already expired or released")


BACKFILL_LOCK_KEY = "ingestion:backfill:lock"
# Three ~200 MB archives, downloaded and parsed entry by entry. Minutes in practice, but
# generous for the same reason as the daily lock: a worker that dies mid-run must not
# block every future attempt, and the lock expiring on its own is what prevents that.
BACKFILL_LOCK_TIMEOUT_SECONDS = 7200


async def _run_backfill(months: int) -> int:
    """Runs one historical backfill inside its own event loop and engine."""
    engine = create_task_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        with httpx2.Client(timeout=60) as client:
            async with session_factory() as session:
                return await load_recent_months(client, session, months)
    finally:
        await engine.dispose()


@celery_app.task(name="backfill_historical")
def backfill_historical_task(months: int = 3) -> int:
    """Celery entry point for the initial corpus load, guarded by a Redis lock.

    Not scheduled by beat: this fills an empty database once, when someone first sets up
    their profile. The daily ingestion keeps it current from then on.

    There is no progress reporting and none is needed -- the dashboard watches the corpus
    grow through `funnel.total` on `GET /matches`, which counts rows as they land.

    Args:
        months: How many monthly archives back to load, including the current one.

    Returns:
        How many tenders were persisted; `0` if a backfill was already running.
    """
    lock = get_redis_client().lock(BACKFILL_LOCK_KEY, timeout=BACKFILL_LOCK_TIMEOUT_SECONDS)
    if not lock.acquire(blocking=False):
        # Two concurrent backfills would download the same ~600 MB twice and upsert the
        # same rows over each other -- harmless but pointless, and slow enough to matter.
        logger.warning("backfill_historical: already running, skipping")
        return 0

    try:
        logger.info("backfill_historical: starting (%d months)", months)
        start = time.monotonic()

        try:
            if sys.platform == "win32":
                count = asyncio.run(_run_backfill(months), loop_factory=asyncio.SelectorEventLoop)
            else:
                count = asyncio.run(_run_backfill(months))
        except Exception:
            logger.exception("backfill_historical: failed")
            raise

        elapsed = time.monotonic() - start
        logger.info("backfill_historical: finished, %d tenders in %.1fs", count, elapsed)
        return count
    finally:
        try:
            lock.release()
        except LockError:
            logger.warning("backfill_historical: lock already expired or released")
