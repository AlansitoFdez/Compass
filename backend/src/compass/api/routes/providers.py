"""GET/PUT /provider — read and write the single supplier profile the funnel ranks against.

Fase 2 deliberately built no CRUD here ("a CRUD endpoint nobody else needs yet") and
seeded the profile by editing `providers/seed.py`. That held while Compass ran on one
machine with one company's data in it. It stops holding the moment someone else downloads
the tool: their CPV codes, budget range, revenue and certifications are what decide both
the funnel and the verdict, and asking them to edit a Python file for that is asking them
to give up.

No `provider_id` anywhere: there is exactly one profile (see `providers.models.Provider`),
so the resource is `/provider`, singular, and `PUT` is an upsert rather than a create.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from compass.core.db import get_db
from compass.providers.repository import get_provider, upsert_provider
from compass.providers.schemas import ProviderSchema

router = APIRouter(prefix="/provider", tags=["provider"])


@router.get("")
async def read_provider(session: AsyncSession = Depends(get_db)) -> ProviderSchema:
    """The current provider profile.

    Raises:
        HTTPException: 404 if no profile has been saved yet -- the state a fresh install
            starts in, and what the dashboard turns into its onboarding screen rather
            than an error.

    Returns:
        The profile.
    """
    provider = await get_provider(session)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider profile not seeded yet")
    return ProviderSchema.model_validate(provider)


@router.put("")
async def write_provider(
    profile: ProviderSchema, session: AsyncSession = Depends(get_db)
) -> ProviderSchema:
    """Saves the provider profile, replacing whatever was there.

    `PUT`, not `PATCH`: the form sends the whole profile every time, and a partial update
    would make "I cleared my certifications" indistinguishable from "I didn't mention
    them" -- a difference that decides verdicts (`analysis.verdict`).

    Nothing needs invalidating afterwards, which is worth knowing before someone adds a
    cache here: the verdict is never stored (it's recomputed on every read against
    whichever profile is current) and the query embedding is cached by the description's
    own text, so editing the description misses that cache by construction.

    Args:
        profile: The complete profile to store.
        session: The active database session.

    Returns:
        The profile as stored, so the caller can render what the server actually kept.
    """
    await upsert_provider(session, profile)
    await session.commit()
    return profile
