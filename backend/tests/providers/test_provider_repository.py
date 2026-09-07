"""Tests for get_provider/upsert_provider -- real Postgres, no mocking."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.providers.models import PROVIDER_ID, Provider
from compass.providers.repository import get_provider, upsert_provider
from compass.providers.schemas import ProviderSchema

BASE_PROVIDER = ProviderSchema(
    description="Desarrollamos aplicaciones web a medida.",
    cpv_codes=["72000000"],
)


async def _fetch(session: AsyncSession) -> Provider:
    """Re-reads the singleton row straight from Postgres, bypassing the session cache.

    `expire_all()` matters here for the same reason it does in
    `tests/tenders/test_tender_repository.py`: without it, a query right
    after `upsert_provider` can return the session's stale in-memory copy
    instead of what Postgres actually has.
    """
    session.expire_all()
    result = await session.execute(select(Provider).where(Provider.id == PROVIDER_ID))
    return result.scalar_one()


async def test_get_provider_returns_none_when_unseeded(db_session: AsyncSession) -> None:
    """Protects the "not seeded yet" case: no row means `None`, not an exception."""
    assert await get_provider(db_session) is None


async def test_upsert_provider_creates_the_row(db_session: AsyncSession) -> None:
    """Protects the base case: seeding an empty table inserts exactly the one row."""
    await upsert_provider(db_session, BASE_PROVIDER)
    await db_session.flush()

    fetched = await _fetch(db_session)
    assert fetched.description == BASE_PROVIDER.description


async def test_upsert_provider_processed_twice_with_same_data_is_one_row(
    db_session: AsyncSession,
) -> None:
    """Protects the "no plain INSERT" rule from CLAUDE.md, applied to the singleton row.

    Re-running the seed must never fail on a duplicate key or produce a
    second row -- it replaces the one row in place.
    """
    await upsert_provider(db_session, BASE_PROVIDER)
    await upsert_provider(db_session, BASE_PROVIDER)
    await db_session.flush()

    result = await db_session.execute(select(Provider))
    assert len(result.scalars().all()) == 1


async def test_upsert_provider_updates_fields_and_preserves_created_at(
    db_session: AsyncSession,
) -> None:
    """Protects the update half of upsert: changed fields land, created_at doesn't, updated_at does.

    A profile edit must overwrite `description`/`min_budget` in place, keep
    the original `created_at` (still the same row), and bump `updated_at`
    past its previous value.
    """
    await upsert_provider(db_session, BASE_PROVIDER)
    await db_session.flush()
    first = await _fetch(db_session)
    # Captured as plain values, not as attributes on `first`: the session's
    # identity map mutates `first` in place on the next query (same row =
    # same Python object), so comparing against `first.x` later would
    # compare an already-updated object against itself.
    first_created_at = first.created_at
    first_updated_at = first.updated_at

    modified = BASE_PROVIDER.model_copy(
        update={"description": "Ahora también mantenemos portales institucionales."}
    )
    await upsert_provider(db_session, modified)
    await db_session.flush()
    second = await _fetch(db_session)

    assert second.description == "Ahora también mantenemos portales institucionales."
    assert second.created_at == first_created_at
    assert second.updated_at > first_updated_at


async def test_upsert_provider_persists_optional_fields(db_session: AsyncSession) -> None:
    """Protects the nullable columns actually round-tripping when given a real value."""
    full_profile = BASE_PROVIDER.model_copy(
        update={
            "min_budget": Decimal("10000.00"),
            "max_budget": Decimal("500000.00"),
            "annual_revenue": Decimal("1200000.00"),
            "certifications": ["ISO 27001", "ENS"],
        }
    )
    await upsert_provider(db_session, full_profile)
    await db_session.flush()

    fetched = await get_provider(db_session)

    assert fetched is not None
    assert fetched.min_budget == Decimal("10000.00")
    assert fetched.certifications == ["ISO 27001", "ENS"]
