"""Persistence round-trip test for the Provider ORM model, against the real database."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.providers.models import Provider
from compass.providers.schemas import ProviderSchema


async def test_provider_persists_and_round_trips(db_session: AsyncSession) -> None:
    """Protects the ORM mapping end to end: insert, fetch back, and re-validate as a schema.

    In particular, that `created_at`'s `server_default=func.now()` actually
    fires, and that a fetched row can build a `ProviderSchema` via
    `from_attributes=True` despite the schema not declaring `id` at all --
    extra ORM attributes are simply ignored by Pydantic here.
    """
    provider = Provider(
        id="test-round-trip",
        description="Desarrollamos aplicaciones web a medida.",
        cpv_codes=["72000000"],
    )
    db_session.add(provider)
    await db_session.flush()

    result = await db_session.execute(select(Provider).where(Provider.id == "test-round-trip"))
    fetched = result.scalar_one()

    assert fetched.created_at is not None

    schema = ProviderSchema.model_validate(fetched)
    assert schema.description == "Desarrollamos aplicaciones web a medida."
