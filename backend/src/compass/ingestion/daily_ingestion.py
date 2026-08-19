"""Orchestrates the daily live-feed ingestion: parse -> filter by vertical -> upsert."""

import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from compass.ingestion.codice_parser import try_parse_codice_entry
from compass.ingestion.feed_reader import ingest_atom_feed
from compass.tenders.repository import upsert_tender
from compass.tenders.vertical import matches_it_vertical

DEFAULT_COMMIT_EVERY = 50


async def run_daily_ingestion(
    client: httpx2.Client, session: AsyncSession, commit_every: int = DEFAULT_COMMIT_EVERY
) -> int:
    """Drains the live feed from the last checkpoint (or from scratch), committing
    periodically.

    The checkpoint (Redis) advances once per ATOM page, independently of this
    session's transaction — a live-feed cold start can walk hundreds of pages
    in one call. Without periodic commits, a crash mid-run would leave the
    checkpoint pointing past pages whose tenders were never actually saved,
    making them unreachable (the checkpoint never moves backwards). Committing
    every `commit_every` persisted tenders bounds that gap to a small, known
    size instead of the whole run.

    Returns how many tenders matched the IT vertical and were persisted.
    """
    persisted = 0
    since_last_commit = 0

    for entry in ingest_atom_feed(client):
        tender = try_parse_codice_entry(entry)
        if tender is None:
            continue
        if not matches_it_vertical(tender.cpv_codes):
            continue
        await upsert_tender(session, tender)
        persisted += 1
        since_last_commit += 1

        if since_last_commit >= commit_every:
            await session.commit()
            since_last_commit = 0

    if since_last_commit > 0:
        await session.commit()

    return persisted
