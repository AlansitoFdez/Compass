"""Etapa 2 (lexical half) of the matching funnel: ranks Etapa 1 survivors by relevance to
the provider's own free-text description, using Postgres full-text search.

This never filters on its own -- everything scored here already survived
`matching.repository.build_filters`'s hard filters. `provider.description`
is a whole paragraph, not a short search phrase, which matters for how the
query is built: see `_or_tsquery`.
"""

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.matching.repository import build_filters
from compass.providers.models import Provider
from compass.tenders.models import Tender


def _or_tsquery(text: str) -> ColumnElement[str]:
    """A `tsquery` matching ANY significant lexeme in `text` (OR), not every one of them (AND).

    `plainto_tsquery` -- the obvious first choice -- ANDs every lexeme
    together, which works for a short search phrase but not for a whole
    paragraph: verified empirically while planning this subphase
    (`docs/phases/phase2/subphases/phase2.3.md`) that ANDing the real
    seeded provider description's ~23 lexemes matched zero real tender
    titles. This builds the OR version instead: `to_tsvector` already
    strips stopwords, stems, and normalizes `text`, so the lexemes it
    produces are safe to join with `|` -- no tsquery operator characters
    survive that normalization.
    """
    lexemes = func.tsvector_to_array(func.to_tsvector("spanish", text))
    joined = func.array_to_string(lexemes, " | ")
    # to_tsquery()'s return isn't precisely typed upstream (Any); same
    # explicit-annotation fix as build_filters._cpv_filter's `.overlap()`.
    query: ColumnElement[str] = func.to_tsquery("spanish", joined)
    return query


async def lexical_matches(
    session: AsyncSession, provider: Provider, *, limit: int
) -> list[tuple[Tender, float]]:
    """Ranks Etapa 1 survivors by lexical relevance to `provider.description`.

    Args:
        session: The active database session.
        provider: Whose hard filters (via `build_filters`) scope the
            candidates, and whose description is the query text.
        limit: Maximum number of ranked tenders to return.

    Returns:
        Tenders sharing at least one significant lexeme with the
        description, highest `ts_rank` first, each paired with its score.
    """
    query = _or_tsquery(provider.description)
    rank = func.ts_rank(Tender.title_tsv, query).label("rank")

    stmt = (
        select(Tender, rank)
        .where(*build_filters(provider))
        .where(Tender.title_tsv.op("@@")(query))
        .order_by(rank.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [(tender, rank_value) for tender, rank_value in rows]
