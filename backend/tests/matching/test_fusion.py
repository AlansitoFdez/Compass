"""Tests for fused_matches -- real Postgres and the real embedding model, no mocking: RRF only
means anything over real rankings from lexical_matches/vector_matches, not stand-ins.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from compass.matching.embeddings import embed_texts
from compass.matching.fusion import fused_matches
from compass.providers.models import Provider
from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.models import Tender

# A CPV outside division 72: isolates these tests' synthetic rows from the
# real corpus already persisted in the same Postgres, same reasoning as
# tests/matching/test_lexical.py's LEXICAL_CPV.
FUSION_CPV = "99444444"

PROVIDER = Provider(
    id="test",
    description="Mantenimiento y soporte de portales web institucionales con Drupal",
    cpv_codes=[FUSION_CPV],
    min_budget=None,
    max_budget=None,
    locations=None,
)

RELEVANT_TITLE = "Mantenimiento y soporte de portal web institucional con Drupal"


def _tender(expediente: str, title: str, *, embedded: bool = True, **overrides: object) -> Tender:
    """A minimal valid `Tender`, passing Etapa 1 for `PROVIDER`, embedded from its own `title`
    unless `embedded=False` -- same shape as tests/matching/test_vector.py's helper.
    """
    defaults: dict[str, object] = {
        "expediente": expediente,
        "contracting_body": "Ayuntamiento de Prueba",
        "title": title,
        "cpv_codes": [FUSION_CPV],
        "contract_type": ContractType.SERVICES,
        "procedure_type": "Abierto",
        "status": TenderStatus.OPEN_FOR_SUBMISSION,
        "budget_with_vat": Decimal("50000.00"),
        "published_at": datetime.now(UTC),
        "updated_at_source": datetime.now(UTC),
    }
    defaults.update(overrides)
    if embedded:
        (defaults["title_embedding"],) = embed_texts([title])
    return Tender(**defaults)


async def test_fused_matches_ranks_a_tender_from_both_recoverers_above_one_from_only_one(
    db_session: AsyncSession,
) -> None:
    """Protects RRF's core promise: agreement between the two rankings beats a single strong
    ranking. "TEST-FUS-LEXICAL-ONLY" is never embedded, so vector_matches (2.5) can never
    surface it (see its own NULL-exclusion test) -- it's lexical-only by construction, not
    by luck.
    """
    db_session.add(_tender("TEST-FUS-BOTH", RELEVANT_TITLE))
    db_session.add(_tender("TEST-FUS-LEXICAL-ONLY", RELEVANT_TITLE, embedded=False))
    await db_session.flush()

    results = await fused_matches(db_session, PROVIDER, limit=10)

    by_expediente = {result.tender.expediente: result for result in results}
    both = by_expediente["TEST-FUS-BOTH"]
    lexical_only = by_expediente["TEST-FUS-LEXICAL-ONLY"]

    assert both.rrf_score > lexical_only.rrf_score
    assert both.lexical_rank is not None
    assert both.vector_rank is not None
    assert lexical_only.lexical_rank is not None
    assert lexical_only.vector_rank is None
    assert lexical_only.vector_distance is None


async def test_fused_matches_excludes_tenders_that_fail_the_hard_filters(
    db_session: AsyncSession,
) -> None:
    """Protects the sequential funnel: a fused score never surfaces a tender that never survived
    Etapa 1 in the first place.
    """
    db_session.add(_tender("TEST-FUS-WRONG-STATUS", RELEVANT_TITLE, status=TenderStatus.AWARDED))
    await db_session.flush()

    results = await fused_matches(db_session, PROVIDER, limit=10)

    assert results == []


async def test_fused_matches_respects_the_limit(db_session: AsyncSession) -> None:
    """Protects `limit` bounding the fused results, not just each underlying ranking's own limit."""
    for i in range(3):
        db_session.add(_tender(f"TEST-FUS-LIMIT-{i}", RELEVANT_TITLE))
    await db_session.flush()

    results = await fused_matches(db_session, PROVIDER, limit=2)

    assert len(results) == 2
