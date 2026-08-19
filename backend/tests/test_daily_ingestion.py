"""Tests for the daily ingestion orchestration — commit behavior in particular."""

from pathlib import Path

import httpx2
import pytest
from sqlalchemy import delete, event, select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.ingestion.checkpoint import clear_last_processed_atom_url
from compass.ingestion.daily_ingestion import run_daily_ingestion
from compass.tenders.models import Tender

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "codice_entry_sample.xml"
XML_HEADER = b'<?xml version="1.0" encoding="UTF-8"?>\n'


def _matching_entry(suffix: str) -> bytes:
    """The real fixture, CPV swapped into our vertical, with a unique expediente."""
    content = FIXTURE_PATH.read_bytes().replace(XML_HEADER, b"")
    content = content.replace(b">CS2026/94<", f">CS2026/94-{suffix}<".encode(), 1)
    return content.replace(b"30231320", b"72000000")


def _atom_feed(entries: list[bytes]) -> bytes:
    body = b"".join(entries)
    return XML_HEADER + b'<feed xmlns="http://www.w3.org/2005/Atom">' + body + b"</feed>"


def _malformed_entry(suffix: str) -> bytes:
    """A matching entry whose status code is one PLACSP has never used —
    parse_codice_entry() raises for it; try_parse_codice_entry() must not.
    """
    return _matching_entry(suffix).replace(
        b">PUB</ns3:ContractFolderStatusCode>", b">ZZZZ</ns3:ContractFolderStatusCode>", 1
    )


@pytest.fixture(autouse=True)
def _clean_checkpoint():
    clear_last_processed_atom_url()
    yield
    clear_last_processed_atom_url()


async def test_run_daily_ingestion_commits_periodically(db_session: AsyncSession) -> None:
    """With commit_every=1, each of the 3 matches should trigger its own commit —
    proving the checkpoint (per-page) never gets ahead of what's durably saved
    by more than `commit_every` tenders, per the bug found in the real 1.9 run.
    """
    entries = [_matching_entry(str(i)) for i in range(3)]
    feed = _atom_feed(entries)

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=feed)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))

    commit_count = 0

    def _on_commit(session: object) -> None:
        nonlocal commit_count
        commit_count += 1

    event.listen(db_session.sync_session, "after_commit", _on_commit)

    try:
        count = await run_daily_ingestion(client, db_session, commit_every=1)

        assert count == 3
        assert commit_count == 3

        result = await db_session.execute(
            select(Tender).where(Tender.expediente.like("CS2026/94-%"))
        )
        assert len(result.scalars().all()) == 3
    finally:
        event.remove(db_session.sync_session, "after_commit", _on_commit)
        # Ya son commits reales — el rollback de la fixture db_session no los
        # deshace, hay que limpiarlos explícitamente.
        await db_session.execute(delete(Tender).where(Tender.expediente.like("CS2026/94-%")))
        await db_session.commit()


async def test_run_daily_ingestion_skips_a_malformed_entry_without_losing_the_rest(
    db_session: AsyncSession,
) -> None:
    """A malformed entry ahead of a valid one in the feed must not sink the
    valid one — the real bug found in the 1.11 review (one bad entry crashed
    the whole run).
    """
    feed = _atom_feed([_malformed_entry("BAD"), _matching_entry("GOOD")])

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=feed)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))

    try:
        count = await run_daily_ingestion(client, db_session, commit_every=1)

        assert count == 1

        result = await db_session.execute(
            select(Tender).where(Tender.expediente == "CS2026/94-GOOD")
        )
        assert result.scalar_one_or_none() is not None
        result = await db_session.execute(
            select(Tender).where(Tender.expediente == "CS2026/94-BAD")
        )
        assert result.scalar_one_or_none() is None
    finally:
        # commit_every=1 -> commits reales, igual que en el test anterior.
        await db_session.execute(delete(Tender).where(Tender.expediente.like("CS2026/94-%")))
        await db_session.commit()
