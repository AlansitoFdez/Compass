"""One-off script that seeds the provider profile with its real data.

Invoked by hand (`uv run python -m compass.providers.seed`), not part of any
scheduled pipeline -- there is exactly one profile (see `models.Provider`),
and it changes rarely enough that re-running this script by hand whenever it
does is simpler than building a CRUD endpoint nobody else needs yet.
"""

import asyncio
import logging
import sys
from decimal import Decimal

from compass.providers.repository import upsert_provider
from compass.providers.schemas import ProviderSchema

logger = logging.getLogger(__name__)

PROFILE = ProviderSchema(
    description=(
        "Desarrollamos aplicaciones web a medida y mantenemos portales "
        "institucionales para el sector público. Trabajamos con Drupal, "
        "WordPress y desarrollos a medida, con atención a accesibilidad, "
        "sede electrónica y cumplimiento del Esquema Nacional de Seguridad (ENS)."
    ),
    cpv_codes=["72200000", "72262000", "72267000", "72400000", "72600000"],
    min_budget=Decimal("10000.00"),
    max_budget=Decimal("200000.00"),
    annual_revenue=Decimal("450000.00"),
    certifications=["ENS", "ISO 27001"],
)


async def _main() -> None:
    """CLI entry point: upserts `PROFILE` and commits."""
    from compass.core.db import async_session_factory

    async with async_session_factory() as session:
        await upsert_provider(session, PROFILE)
        await session.commit()
        logger.info("Provider profile seeded.")


if __name__ == "__main__":
    # Without this, logger.info() prints nothing when run as a standalone
    # script -- same fix as historical_loader.py's __main__ block.
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if sys.platform == "win32":
        asyncio.run(_main(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(_main())
