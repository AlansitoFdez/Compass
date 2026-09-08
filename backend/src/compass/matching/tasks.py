"""The embedding-generation Celery task: bridges the sync Celery model into our async pipeline.

Same shape as `compass.ingestion.tasks.daily_ingestion_task` -- see that
module's docstring for why a Celery task needs its own event loop and engine.
"""

import asyncio
import logging
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from compass.core.celery_app import celery_app
from compass.core.db import create_task_engine
from compass.matching.embeddings import embed_texts
from compass.tenders.models import Tender

logger = logging.getLogger(__name__)

# Bounds each transaction/batch call to the model, not the whole backlog --
# a cold backfill of the ~3,583-row corpus runs as multiple batches inside
# one task call (see generate_embeddings), so a crash mid-run only loses
# the batch in flight, not everything embedded so far.
BATCH_SIZE = 200


async def generate_embeddings(session: AsyncSession) -> int:
    """Embeds every tender still missing `title_embedding`, in batches, until none are left.

    Loops rather than handling one batch per task invocation: with beat
    scheduling this task every 15 minutes (see celery_app.py), a normal run
    finds nothing to do and exits immediately, but the first run after the
    2.5 migration (or any bulk load, like `historical_loader`) needs to
    drain the whole backlog, not trickle it out one batch per 15 minutes.

    Returns:
        How many tenders were embedded and persisted.
    """
    total = 0
    while True:
        stmt = select(Tender).where(Tender.title_embedding.is_(None)).limit(BATCH_SIZE)
        tenders = (await session.scalars(stmt)).all()
        if not tenders:
            break

        embeddings = embed_texts([tender.title for tender in tenders])
        for tender, embedding in zip(tenders, embeddings, strict=True):
            tender.title_embedding = embedding
        await session.commit()

        total += len(tenders)
        logger.info("generate_embeddings: %d tenders embedded so far", total)

    return total


async def _run() -> int:
    engine = create_task_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            return await generate_embeddings(session)
    finally:
        await engine.dispose()


@celery_app.task(name="generate_embeddings")
def generate_embeddings_task() -> int:
    """Celery entry point: embeds every tender still missing `title_embedding`.

    No lock, unlike `daily_ingestion_task` -- two concurrent runs would at
    worst embed the same handful of straggler rows twice, both writing the
    same deterministic result, not corrupt any shared state like a checkpoint.

    Returns:
        How many tenders were embedded and persisted in this run.
    """
    logger.info("generate_embeddings: starting")

    try:
        if sys.platform == "win32":
            count = asyncio.run(_run(), loop_factory=asyncio.SelectorEventLoop)
        else:
            count = asyncio.run(_run())
    except Exception:
        logger.exception("generate_embeddings: failed")
        raise

    logger.info("generate_embeddings: finished, %d tenders embedded", count)
    return count
