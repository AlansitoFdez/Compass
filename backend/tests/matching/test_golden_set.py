"""Tests for the golden set's internal consistency against the real Etapa 1 survivor population."""

import pytest
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


# Needs the real PLACSP corpus persisted locally, which a CI runner doesn't have --
# see docs/phases/phase4/subphases/phase4.6.md.
@pytest.mark.real_corpus
async def test_golden_set_covers_exactly_the_real_etapa1_survivors(
    db_session: AsyncSession,
) -> None:
    """Protects the golden set from silently going stale: every tender the funnel ranks
    today must be one a human actually annotated.

    Checked as containment, not equality, and the reason is worth writing down. The golden
    set was annotated by hand against the Etapa 1 survivors as they stood in 2.3. Equality
    held only while that population was frozen, and it never could have held for long: a
    tender leaves Etapa 1 on its own the moment its deadline passes or PLACSP marks it
    awarded. 5.4 made that explicit by adding the deadline condition to the filter -- the
    live population dropped from 61 to a handful, all of them annotated.

    What actually matters for a recall@k measurement is this direction: no tender may be
    ranked that the golden set has no label for, because such a tender would count as a
    miss no matter how good the ranking is. The opposite direction -- annotated tenders
    that have since closed -- is just time passing, and silently re-annotating to chase it
    would destroy the hand-made labels this whole file exists to protect.
    """
    provider = await get_provider(db_session)
    assert provider is not None
    items, _total = await list_matches(db_session, provider, limit=1000, offset=0)

    real_survivors = {tender.expediente for tender in items}
    golden_set_population = RELEVANT_EXPEDIENTES | NOT_RELEVANT_EXPEDIENTES | EXCLUDED_EXPEDIENTES

    assert real_survivors <= golden_set_population, (
        "estas licitaciones sobreviven a Etapa 1 pero nadie las ha anotado: "
        f"{sorted(real_survivors - golden_set_population)}"
    )
