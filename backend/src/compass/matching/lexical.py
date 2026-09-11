"""Etapa 2 (lexical half) of the matching funnel: ranks Etapa 1 survivors by relevance to
the provider's own free-text description, using Postgres full-text search.

This never filters on its own -- everything scored here already survived
`matching.repository.build_filters`'s hard filters. `provider.description`
is a whole paragraph, not a short search phrase, which matters for how the
query is built: see `lexical_matches`.
"""

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.matching.repository import build_filters
from compass.providers.models import Provider
from compass.tenders.models import Tender


async def _significant_lexemes(session: AsyncSession, text: str) -> str:
    """The significant lexemes of `text`, already joined with `|` for `to_tsquery`.

    Resolved in its own round trip instead of nested inside the ranking query, for two
    reasons that pull the same way:

    - **Correctness.** A text with no significant lexemes -- empty, or nothing but
      stopwords -- produces an empty string, and `to_tsquery('')` is a syntax error that
      takes the whole of `GET /matches` down with it. Having the string in Python lets the
      caller skip the lexical half entirely, which is the honest answer anyway.
    - **Cost.** Folding `nullif` into the nested expression instead was measured turning a
      millisecond ranking query into 130 seconds against the real corpus: the planner
      stopped treating the tsquery as a constant and re-derived it per row. Passing the
      finished string as a bound parameter keeps it a constant, as it always was.

    Args:
        session: The active database session.
        text: The provider description to analyze.

    Returns:
        Lexemes joined with `" | "`, or `""` when the text has none.
    """
    lexemes = func.tsvector_to_array(func.to_tsvector("spanish", text))
    joined = await session.scalar(select(func.array_to_string(lexemes, " | ")))
    return joined or ""


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
    joined = await _significant_lexemes(session, provider.description)
    if not joined:
        return []

    # ANY of the lexemes (`|`), not all of them (`&`): `plainto_tsquery` -- the obvious
    # first choice -- ANDs every lexeme together, which works for a short search phrase but
    # not for a whole paragraph. Verified empirically while planning 2.3
    # (`docs/phases/phase2/subphases/phase2.3.md`) that ANDing the real seeded provider
    # description's ~23 lexemes matched zero real tender titles. Safe to join with `|`
    # because `to_tsvector` already stripped, stemmed and normalized them -- no tsquery
    # operator character survives that.
    # to_tsquery()'s return isn't precisely typed upstream (Any); same explicit-annotation
    # fix as build_filters._cpv_filter's `.overlap()`.
    query: ColumnElement[str] = func.to_tsquery("spanish", joined)
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
