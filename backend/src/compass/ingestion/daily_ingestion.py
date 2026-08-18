"""Orchestrates the daily live-feed ingestion: parse -> filter by vertical -> upsert."""

import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from compass.ingestion.codice_parser import parse_codice_entry
from compass.ingestion.feed_reader import ingest_atom_feed
from compass.tenders.repository import upsert_tender
from compass.tenders.vertical import matches_it_vertical


async def run_daily_ingestion(client: httpx2.Client, session: AsyncSession) -> int:
    """Drains the live feed from the last checkpoint (or from scratch). Does not commit.

    Returns how many tenders matched the IT vertical and were persisted.
    """
    persisted = 0

    for entry in ingest_atom_feed(client):
        tender = parse_codice_entry(entry)
        if not matches_it_vertical(tender.cpv_codes):
            continue
        await upsert_tender(session, tender)
        persisted += 1

    return persisted
