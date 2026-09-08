"""Tests for the golden set's internal consistency against the real Etapa 1 survivor population."""

from sqlalchemy.ext.asyncio import AsyncSession

from compass.matching.golden_set import (
    EXCLUDED_EXPEDIENTES,
    NOT_RELEVANT_EXPEDIENTES,
    RELEVANT_EXPEDIENTES,
)
from compass.matching.repository import list_matches
from compass.providers.repository import get_provider


def test_golden_set_categories_are_pairwise_disjoint() -> None:
    """Protects against a tender accidentally landing in more than one category."""
    assert not (RELEVANT_EXPEDIENTES & NOT_RELEVANT_EXPEDIENTES)
    assert not (RELEVANT_EXPEDIENTES & EXCLUDED_EXPEDIENTES)
    assert not (NOT_RELEVANT_EXPEDIENTES & EXCLUDED_EXPEDIENTES)


async def test_golden_set_covers_exactly_the_real_etapa1_survivors(
    db_session: AsyncSession,
) -> None:
    """Protects the golden set from silently going stale.

    If the real corpus or the seeded provider profile ever changes enough to
    shift who survives Etapa 1, this fails loudly instead of quietly
    measuring recall@k against a population that no longer matches reality.
    """
    provider = await get_provider(db_session)
    assert provider is not None
    items, _total = await list_matches(db_session, provider, limit=1000, offset=0)

    real_survivors = {tender.expediente for tender in items}
    golden_set_population = RELEVANT_EXPEDIENTES | NOT_RELEVANT_EXPEDIENTES | EXCLUDED_EXPEDIENTES

    assert golden_set_population == real_survivors
