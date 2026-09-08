"""Etapa 2 fusion: Reciprocal Rank Fusion over the lexical (2.3) and vector (2.5) rankings.

Neither underlying ranking filters on its own beyond Etapa 1 (see their own
modules); this only combines two already-scoped orderings into one.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from compass.matching.lexical import lexical_matches
from compass.matching.vector import vector_matches
from compass.providers.models import Provider
from compass.tenders.models import Tender

# The standard constant from the original RRF paper (Cormack et al., 2009) --
# dampens how much a single #1 rank can dominate the fused score, so a tender
# both rankings agree on (even at modest individual ranks) can outrank one
# only one of them ranked #1.
RRF_K = 60

# Candidates requested from each recoverer before fusing -- generous enough
# that RRF has something to work with even when one side comes back thin
# (e.g. the lexical query matching nothing), without asking for more than
# makes sense against a corpus of a few thousand rows.
CANDIDATE_POOL = 50


@dataclass
class MatchResult:
    """One tender's fused rank, plus enough of each recoverer's own signal to explain it.

    `lexical_rank`/`lexical_score` and `vector_rank`/`vector_distance` are
    `None` when that recoverer didn't surface this tender at all -- outside
    its own `CANDIDATE_POOL`, or (for vector) not embedded yet. Which of
    these are set *is* the "motivo de encaje" the design doc asks for.
    """

    tender: Tender
    rrf_score: float
    lexical_rank: int | None
    lexical_score: float | None
    vector_rank: int | None
    vector_distance: float | None


async def fused_matches(
    session: AsyncSession, provider: Provider, *, limit: int
) -> list[MatchResult]:
    """Reciprocal Rank Fusion over `lexical_matches` and `vector_matches`.

    Args:
        session: The active database session.
        provider: Whose hard filters and description drive both underlying rankings.
        limit: Maximum number of fused results to return.

    Returns:
        Tenders either recoverer surfaced, ordered by combined RRF score
        (highest first) -- a tender both rankings agree on outranks one only
        one of them found, even if that one ranked it #1.
    """
    lexical = await lexical_matches(session, provider, limit=CANDIDATE_POOL)
    vector = await vector_matches(session, provider, limit=CANDIDATE_POOL)

    results: dict[str, MatchResult] = {}

    for rank, (tender, score) in enumerate(lexical, start=1):
        results[tender.expediente] = MatchResult(
            tender=tender,
            rrf_score=1 / (RRF_K + rank),
            lexical_rank=rank,
            lexical_score=score,
            vector_rank=None,
            vector_distance=None,
        )

    for rank, (tender, distance) in enumerate(vector, start=1):
        contribution = 1 / (RRF_K + rank)
        existing = results.get(tender.expediente)
        if existing is None:
            results[tender.expediente] = MatchResult(
                tender=tender,
                rrf_score=contribution,
                lexical_rank=None,
                lexical_score=None,
                vector_rank=rank,
                vector_distance=distance,
            )
        else:
            existing.rrf_score += contribution
            existing.vector_rank = rank
            existing.vector_distance = distance

    ranked = sorted(results.values(), key=lambda result: result.rrf_score, reverse=True)
    return ranked[:limit]
