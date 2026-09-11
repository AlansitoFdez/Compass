"""Tests for the matching funnel's vector ranking stage (vector_matches) -- real Postgres and
the real embedding model, no mocking: pgvector's `<=>` cosine distance only means anything
against real vectors, not stand-ins.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from compass.matching.embeddings import embed_texts
from compass.matching.vector import vector_matches
from compass.providers.models import Provider
from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.models import Tender

# A CPV outside division 72: isolates these tests' synthetic rows from the
# real corpus already persisted in the same Postgres, same reasoning as
# tests/matching/test_lexical.py's LEXICAL_CPV.
VECTOR_CPV = "99555555"

PROVIDER = Provider(
    id="test",
    description="Mantenimiento y soporte de portales web institucionales con Drupal",
    cpv_codes=[VECTOR_CPV],
    min_budget=None,
    max_budget=None,
    locations=None,
)


def _tender(expediente: str, title: str, *, embedded: bool = True, **overrides: object) -> Tender:
    """A minimal valid `Tender`, passing Etapa 1 for `PROVIDER`, embedded from its own `title`
    unless `embedded=False`.

    Built as an ORM object directly, not via `upsert_tender` -- `TenderSchema`
    never carries `title_embedding` (populated later, by
    `matching.tasks.generate_embeddings_task`), so the repository upsert path
    can't set it either.
    """
    defaults: dict[str, object] = {
        "expediente": expediente,
        "contracting_body": "Ayuntamiento de Prueba",
        "title": title,
        "cpv_codes": [VECTOR_CPV],
        "contract_type": ContractType.SERVICES,
        "procedure_type": "Abierto",
        "status": TenderStatus.OPEN_FOR_SUBMISSION,
        # A deadline in the future, not just an open status: since 5.4 Etapa 1 requires
        # both, because PLACSP leaves the status code stale on 84% of the tenders it
        # still calls open (see `matching.repository._status_filter`).
        "submission_deadline": datetime.now(UTC) + timedelta(days=30),
        "budget_with_vat": Decimal("50000.00"),
        "published_at": datetime.now(UTC),
        "updated_at_source": datetime.now(UTC),
    }
    defaults.update(overrides)
    if embedded:
        (defaults["title_embedding"],) = embed_texts([title])
    return Tender(**defaults)


async def test_vector_matches_ranks_relevant_tenders_above_unrelated_ones(
    db_session: AsyncSession,
) -> None:
    """Protects the core behavior: a semantically relevant title outranks an unrelated one.

    Both tenders pass Etapa 1 identically -- only the title text (and its
    embedding) differs.
    """
    db_session.add(
        _tender(
            "TEST-VEC-RELEVANT", "Mantenimiento y soporte de portal web institucional con Drupal"
        )
    )
    db_session.add(_tender("TEST-VEC-UNRELATED", "Suministro de mobiliario de oficina"))
    await db_session.flush()

    results = await vector_matches(db_session, PROVIDER, limit=10)

    expedientes = [tender.expediente for tender, _distance in results]
    assert expedientes == ["TEST-VEC-RELEVANT", "TEST-VEC-UNRELATED"]


async def test_vector_matches_excludes_tenders_that_fail_the_hard_filters(
    db_session: AsyncSession,
) -> None:
    """Protects the sequential funnel: a semantically perfect title still needs to survive Etapa 1.

    Same title as a relevant tender, but `status=awarded` -- not "en plazo" --
    so `build_filters` excludes it before ranking ever runs.
    """
    db_session.add(
        _tender(
            "TEST-VEC-WRONG-STATUS",
            "Mantenimiento y soporte de portal web institucional con Drupal",
            status=TenderStatus.AWARDED,
        )
    )
    await db_session.flush()

    results = await vector_matches(db_session, PROVIDER, limit=10)

    assert results == []


async def test_vector_matches_respects_the_limit(db_session: AsyncSession) -> None:
    """Protects `limit` actually bounding the ranked results, not just the query's own shape."""
    for i in range(3):
        db_session.add(_tender(f"TEST-VEC-LIMIT-{i}", "Mantenimiento de portal web institucional"))
    await db_session.flush()

    results = await vector_matches(db_session, PROVIDER, limit=2)

    assert len(results) == 2


async def test_vector_matches_excludes_tenders_without_an_embedding_yet(
    db_session: AsyncSession,
) -> None:
    """Protects against a NULL `title_embedding` (not yet processed by the backfill task) either
    crashing the cosine-distance query or, worse, sorting last instead of being excluded outright.
    """
    db_session.add(
        _tender(
            "TEST-VEC-NOT-EMBEDDED",
            "Mantenimiento y soporte de portal web institucional con Drupal",
            embedded=False,
        )
    )
    await db_session.flush()

    results = await vector_matches(db_session, PROVIDER, limit=10)

    assert results == []
