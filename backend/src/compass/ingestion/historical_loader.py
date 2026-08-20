"""Downloads and processes PLACSP's historical monthly archives (last 3 months)."""

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

BASE_URL = "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643"


def monthly_archive_url(year: int, month: int) -> str:
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
    """Streams the ZIP to a temp file (never holds the whole ~200MB in memory)."""
    with client.stream("GET", url) as response:
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            for chunk in response.iter_bytes():
                tmp.write(chunk)
            return Path(tmp.name)


def iter_entries_from_zip(zip_path: Path) -> Iterator[Element]:
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.endswith(".atom"):
                continue
            with zf.open(name) as f:
                page = parse_atom_page(f.read())
            yield from page.entries


def iter_entries_from_url(url: str, client: httpx2.Client) -> Iterator[Element]:
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


async def _main() -> None:
    from compass.core.db import async_session_factory

    # httpx2.Client es deliberadamente síncrono (ver ingestion/tasks.py) --
    # no admite "async with", solo el "with" normal.
    with httpx2.Client(timeout=60) as client:
        async with async_session_factory() as session:
            for year, month in recent_months(3):
                count = await load_month(year, month, client, session)
                await session.commit()
                print(f"{year:04d}-{month:02d}: {count} licitaciones del vertical guardadas")


if __name__ == "__main__":
    import asyncio
    import sys

    if sys.platform == "win32":
        asyncio.run(_main(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(_main())
