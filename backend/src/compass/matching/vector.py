"""Etapa 2 (vector half) of the matching funnel: ranks Etapa 1 survivors by cosine distance
between the provider's own free-text description and each tender's title, using pgvector.

Mirrors `matching.lexical`: never filters on its own, everything scored here
already survived `matching.repository.build_filters`'s hard filters.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.matching.embeddings import embed_query
from compass.matching.repository import build_filters
from compass.providers.models import Provider
from compass.tenders.models import Tender


async def vector_matches(
    session: AsyncSession, provider: Provider, *, limit: int
) -> list[tuple[Tender, float]]:
    """Ranks Etapa 1 survivors by semantic closeness to `provider.description`.

    Args:
        session: The active database session.
        provider: Whose hard filters (via `build_filters`) scope the
            candidates, and whose description is embedded as the query.
        limit: Maximum number of ranked tenders to return.

    Returns:
        Tenders with a stored embedding (rows still awaiting
        `matching.tasks.generate_embeddings_task` are excluded, not ranked
        last), closest cosine distance first, each paired with that distance
        -- 0.0 is identical, 2.0 is opposite, unlike `lexical_matches`'s
        `ts_rank` where higher is better.
    """
    # `embed_query`, not `embed_texts`: this runs inside a request handler, so the encode
    # has to stay off the event loop and out of the per-request path -- see its docstring.
    query_embedding = await embed_query(provider.description)
    distance = Tender.title_embedding.cosine_distance(query_embedding).label("distance")

    stmt = (
        select(Tender, distance)
        .where(*build_filters(provider))
        .where(Tender.title_embedding.is_not(None))
        .order_by(distance.asc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [(tender, distance_value) for tender, distance_value in rows]
