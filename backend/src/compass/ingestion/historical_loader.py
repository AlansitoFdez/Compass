"""Downloads and processes PLACSP's historical monthly archives (last 3 months)."""

from datetime import date

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
