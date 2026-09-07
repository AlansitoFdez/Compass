"""Persistence for the provider profile: read the singleton row, upsert it -- never a plain insert.

See `models.Provider` for why there is always exactly one row.
"""

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from compass.providers.models import PROVIDER_ID, Provider
from compass.providers.schemas import ProviderSchema


async def get_provider(session: AsyncSession) -> Provider | None:
    """The provider profile, or `None` if it hasn't been seeded yet.

    Args:
        session: The active database session.

    Returns:
        The single `Provider` row, or `None`.
    """
    return await session.get(Provider, PROVIDER_ID)


async def upsert_provider(session: AsyncSession, provider: ProviderSchema) -> None:
    """Insert the provider profile, or replace it in place if it already exists.

    Same upsert-by-fixed-key shape as `tenders.repository.upsert_tender`,
    except the conflict target is always `PROVIDER_ID` -- there is only ever
    one row (see `models.Provider`).

    Args:
        session: The active database session; the caller commits.
        provider: The provider profile to persist.
    """
    values: dict[str, object] = {"id": PROVIDER_ID, **provider.model_dump()}

    stmt = pg_insert(Provider).values(**values)
    update_values = {key: getattr(stmt.excluded, key) for key in values if key != "id"}
    # clock_timestamp(), not now(): see upsert_tender's identical comment --
    # now() is frozen at transaction start and wouldn't advance here either.
    update_values["updated_at"] = func.clock_timestamp()

    stmt = stmt.on_conflict_do_update(index_elements=[Provider.id], set_=update_values)
    await session.execute(stmt)
