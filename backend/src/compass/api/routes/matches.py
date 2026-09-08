"""GET /matches — the fused ranking (RRF over lexical + vector) for the seeded provider profile."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from compass.core.db import get_db
from compass.matching.fusion import fused_matches
from compass.matching.schemas import MatchListResponse, MatchSchema
from compass.providers.repository import get_provider
from compass.tenders.schemas import TenderSchema

router = APIRouter(prefix="/matches", tags=["matches"])

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


@router.get("")
async def get_matches(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    session: AsyncSession = Depends(get_db),
) -> MatchListResponse:
    """The provider's best matches, fused from the lexical and vector rankings via RRF.

    There is a single provider profile (see `providers.models.Provider`) --
    no `provider_id` query param, this always ranks against it.

    Raises:
        HTTPException: 404 if the provider profile hasn't been seeded yet.

    Returns:
        The top `limit` matches, highest `rrf_score` first, each carrying
        the signal from whichever recoverer(s) surfaced it.
    """
    provider = await get_provider(session)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider profile not seeded yet")

    results = await fused_matches(session, provider, limit=limit)

    items = [
        MatchSchema(
            tender=TenderSchema.model_validate(result.tender),
            rrf_score=result.rrf_score,
            lexical_rank=result.lexical_rank,
            lexical_score=result.lexical_score,
            vector_rank=result.vector_rank,
            vector_distance=result.vector_distance,
        )
        for result in results
    ]
    return MatchListResponse(items=items, total=len(items), limit=limit)
