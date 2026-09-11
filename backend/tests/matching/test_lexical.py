"""Tests for the matching funnel's lexical ranking stage (lexical_matches) -- real
Postgres, no mocking: `ts_rank`/`to_tsquery` only mean anything against the real
full-text search engine, not a mock.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from compass.matching.lexical import lexical_matches
from compass.providers.models import Provider
from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.repository import upsert_tender
from compass.tenders.schemas import TenderSchema

# A CPV outside division 72: isolates these tests' synthetic rows from the
# real corpus already persisted in the same Postgres, same reasoning as
# tests/matching/test_matching_repository.py's MATCH_CPV.
LEXICAL_CPV = "99666666"

PROVIDER = Provider(
    id="test",
    description="Mantenimiento y soporte de portales web institucionales con Drupal",
    cpv_codes=[LEXICAL_CPV],
    min_budget=None,
    max_budget=None,
    locations=None,
)


def _tender(expediente: str, **overrides: object) -> TenderSchema:
    """A minimal valid `TenderSchema`, passing Etapa 1 for `PROVIDER`, with `overrides` applied."""
    defaults: dict[str, object] = {
        "expediente": expediente,
        "contracting_body": "Ayuntamiento de Prueba",
        "title": "Servicio de prueba",
        "cpv_codes": [LEXICAL_CPV],
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
    return TenderSchema(**defaults)


async def test_lexical_matches_ranks_relevant_tenders_above_unrelated_ones(
    db_session: AsyncSession,
) -> None:
    """Protects the core behavior: a relevant title outranks an unrelated one.

    Both tenders pass Etapa 1 identically -- only the title text differs.
    """
    await upsert_tender(
        db_session,
        _tender(
            "TEST-LEX-RELEVANT",
            title="Mantenimiento y soporte de portal web institucional con Drupal",
        ),
    )
    await upsert_tender(
        db_session, _tender("TEST-LEX-UNRELATED", title="Suministro de mobiliario de oficina")
    )
    await db_session.flush()

    results = await lexical_matches(db_session, PROVIDER, limit=10)

    expedientes = [tender.expediente for tender, _rank in results]
    assert expedientes == ["TEST-LEX-RELEVANT"]


async def test_lexical_matches_excludes_tenders_that_fail_the_hard_filters(
    db_session: AsyncSession,
) -> None:
    """Protects the sequential funnel: a lexically perfect title still needs to survive Etapa 1.

    Same title as the relevant tender above, but `status=awarded` -- not
    "en plazo" -- so `build_filters` excludes it before ranking ever runs.
    """
    await upsert_tender(
        db_session,
        _tender(
            "TEST-LEX-WRONG-STATUS",
            title="Mantenimiento y soporte de portal web institucional con Drupal",
            status=TenderStatus.AWARDED,
        ),
    )
    await db_session.flush()

    results = await lexical_matches(db_session, PROVIDER, limit=10)

    assert results == []


async def test_lexical_matches_respects_the_limit(db_session: AsyncSession) -> None:
    """Protects `limit` actually bounding the ranked results, not just the query's own shape."""
    for i in range(3):
        await upsert_tender(
            db_session,
            _tender(f"TEST-LEX-LIMIT-{i}", title="Mantenimiento de portal web institucional"),
        )
    await db_session.flush()

    results = await lexical_matches(db_session, PROVIDER, limit=2)

    assert len(results) == 2


async def test_lexical_matches_survives_a_description_with_no_lexemes(
    db_session: AsyncSession,
) -> None:
    """Protects GET /matches against a 500 from its own query builder.

    The tsquery is assembled from the lexemes `to_tsvector` finds in the description. A
    description that yields none -- empty, or nothing but stopwords -- left an empty
    string, and `to_tsquery('')` is a syntax error, not an empty result: the endpoint
    answered 500 rather than "the lexical half found nothing".
    """
    provider = Provider(
        id="TEST-LEXICAL-EMPTY",
        description="de la y el en",
        cpv_codes=["72000000"],
    )

    assert await lexical_matches(db_session, provider, limit=5) == []


async def test_lexical_matches_survives_an_empty_description(db_session: AsyncSession) -> None:
    """The degenerate case of the same rule: an unseeded/blank description must return no
    lexical candidates, never raise.
    """
    provider = Provider(id="TEST-LEXICAL-BLANK", description="", cpv_codes=["72000000"])

    assert await lexical_matches(db_session, provider, limit=5) == []
