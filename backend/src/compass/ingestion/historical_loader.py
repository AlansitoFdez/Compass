"""Downloads and processes PLACSP's historical monthly archives (last 3 months)."""

import logging
import tempfile
import zipfile
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from xml.etree.ElementTree import Element

import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from compass.ingestion.atom_client import parse_atom_page
from compass.ingestion.codice_parser import try_parse_codice_entry
from compass.tenders.repository import upsert_tender
from compass.tenders.vertical import matches_it_vertical

logger = logging.getLogger(__name__)

BASE_URL = "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643"


def monthly_archive_url(year: int, month: int) -> str:
    """URL of PLACSP's monthly archive ZIP for `year`-`month`."""
    return f"{BASE_URL}/licitacionesPerfilesContratanteCompleto3_{year:04d}{month:02d}.zip"


def recent_months(count: int, today: date | None = None) -> list[tuple[int, int]]:
    """(year, month) tuples for the last `count` months, oldest first, including the current one."""
    reference = today or date.today()
    months = []
    year, month = reference.year, reference.month

    for _ in range(count):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1

    return list(reversed(months))


def download_archive(url: str, client: httpx2.Client) -> Path:
    """Streams the ZIP to a temp file (never holds the whole ~200MB in memory).

    Cleans up after itself if the download dies partway: the file is created with
    `delete=False` so the caller can read it after the handle closes, and the only code
    that deletes it is `iter_entries_from_url`'s `finally` -- which never runs if this
    raises. Each failed attempt otherwise left ~200 MB behind in the temp directory.

    Raises:
        httpx2.HTTPStatusError: The archive isn't available (a month PLACSP hasn't
            published yet, typically).

    Returns:
        Path to the downloaded ZIP. The caller owns it, and must delete it.
    """
    with client.stream("GET", url) as response:
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            path = Path(tmp.name)
            try:
                for chunk in response.iter_bytes():
                    tmp.write(chunk)
            except BaseException:
                tmp.close()
                path.unlink(missing_ok=True)
                raise
            return path


def iter_entries_from_zip(zip_path: Path) -> Iterator[Element]:
    """Yields every <entry> across all `.atom` pages packed inside the archive."""
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.endswith(".atom"):
                continue
            with zf.open(name) as f:
                page = parse_atom_page(f.read())
            yield from page.entries


def iter_entries_from_url(url: str, client: httpx2.Client) -> Iterator[Element]:
    """Downloads the archive at `url`, yields its entries, then deletes the temp file."""
    zip_path = download_archive(url, client)
    try:
        yield from iter_entries_from_zip(zip_path)
    finally:
        zip_path.unlink()


async def load_month(year: int, month: int, client: httpx2.Client, session: AsyncSession) -> int:
    """Downloads and processes one month's archive. Does not commit — caller controls that.

    Returns how many tenders matched the IT vertical and were persisted.
    """
    url = monthly_archive_url(year, month)
    persisted = 0

    for entry in iter_entries_from_url(url, client):
        tender = try_parse_codice_entry(entry)
        if tender is None:
            continue
        if not matches_it_vertical(tender.cpv_codes):
            continue
        await upsert_tender(session, tender)
        persisted += 1

    return persisted


DEFAULT_MONTHS = 3


async def load_recent_months(
    client: httpx2.Client, session: AsyncSession, months: int = DEFAULT_MONTHS
) -> int:
    """Loads the last `months` monthly archives, committing once per month.

    Committing per month rather than once at the end bounds what a mid-run failure
    loses to the month in flight -- each archive is ~200 MB and takes minutes, so a
    single transaction around all three would throw away a lot of finished work.

    Args:
        client: The HTTP client to download the archives with.
        session: The active database session; this function commits.
        months: How many months back to go, including the current one.

    Returns:
        How many tenders matched the IT vertical and were persisted, across all months.
    """
    total = 0
    for year, month in recent_months(months):
        count = await load_month(year, month, client, session)
        await session.commit()
        total += count
        logger.info("%04d-%02d: %d IT-vertical tenders saved", year, month, count)
    return total


async def _main() -> None:
    """CLI entry point: loads the last three months, committing once per month."""
    from compass.core.db import async_session_factory

    # httpx2.Client is deliberately synchronous (see ingestion/tasks.py) --
    # it doesn't support "async with", only the plain "with".
    with httpx2.Client(timeout=60) as client:
        async with async_session_factory() as session:
            await load_recent_months(client, session)


if __name__ == "__main__":
    import asyncio
    import sys

    # Without this, logger.info() prints nothing when run as a standalone
    # script -- print() gave that for free, logging needs a configured handler.
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if sys.platform == "win32":
        asyncio.run(_main(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(_main())
