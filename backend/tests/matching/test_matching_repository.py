"""Tests for the matching funnel's hard-filter stage (list_matches, funnel_stage_counts) --
real Postgres, no mocking.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from compass.matching.repository import funnel_stage_counts, list_matches
from compass.providers.models import Provider
from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.repository import upsert_tender
from compass.tenders.schemas import TenderSchema

# A CPV outside division 72: no real ingested data uses it, so it isolates
# these tests' synthetic rows from the ~3,500+ real tenders already
# persisted in the same Postgres the tests use (same reasoning as
# tests/tenders/test_tender_repository.py's LIST_TEST_CPV).
MATCH_CPV = "99777777"


def _tender(expediente: str, **overrides: object) -> TenderSchema:
    """A minimal valid `TenderSchema`, matching a default provider, with `overrides` applied."""
    defaults: dict[str, object] = {
        "expediente": expediente,
        "contracting_body": "Ayuntamiento de Prueba",
        "title": "Servicio de prueba",
        "cpv_codes": [MATCH_CPV],
        "contract_type": ContractType.SERVICES,
        "procedure_type": "Abierto",
        "status": TenderStatus.OPEN_FOR_SUBMISSION,
        "budget_with_vat": Decimal("50000.00"),
        "location": "Asturias",
        "published_at": datetime.now(UTC),
        "updated_at_source": datetime.now(UTC),
    }
    defaults.update(overrides)
    return TenderSchema(**defaults)


def _provider(**overrides: object) -> Provider:
    """A minimal unpersisted `Provider` -- these functions only read its attributes in Python,
    no join against the `providers` table, so it never needs to be added to a session.
    """
    defaults: dict[str, object] = {
        "id": "test",
        "description": "Proveedor de prueba",
        "cpv_codes": [MATCH_CPV],
        "min_budget": None,
        "max_budget": None,
        "locations": None,
    }
    defaults.update(overrides)
    return Provider(**defaults)


async def test_list_matches_excludes_tenders_not_open_for_submission(
    db_session: AsyncSession,
) -> None:
    """Protects "en plazo": a tender in any other status never reaches a provider."""
    await upsert_tender(
        db_session, _tender("TEST-MATCH-STATUS-OPEN", status=TenderStatus.OPEN_FOR_SUBMISSION)
    )
    await upsert_tender(
        db_session, _tender("TEST-MATCH-STATUS-AWARDED", status=TenderStatus.AWARDED)
    )
    await db_session.flush()

    items, total = await list_matches(db_session, _provider(), limit=10, offset=0)

    assert total == 1
    assert items[0].expediente == "TEST-MATCH-STATUS-OPEN"


async def test_list_matches_filters_by_cpv_overlap(db_session: AsyncSession) -> None:
    """Protects the CPV filter: any shared code is enough, not an exact list match."""
    await upsert_tender(
        db_session,
        _tender("TEST-MATCH-CPV-SHARED", cpv_codes=[MATCH_CPV, "72999999"]),
    )
    await upsert_tender(db_session, _tender("TEST-MATCH-CPV-NONE", cpv_codes=["72999999"]))
    await db_session.flush()

    items, total = await list_matches(db_session, _provider(), limit=10, offset=0)

    assert total == 1
    assert items[0].expediente == "TEST-MATCH-CPV-SHARED"


async def test_list_matches_filters_by_provider_budget_range(db_session: AsyncSession) -> None:
    """Protects the budget filter as two independent, inclusive bounds from the profile."""
    await upsert_tender(
        db_session, _tender("TEST-MATCH-BUDGET-IN", budget_with_vat=Decimal("50000.00"))
    )
    await upsert_tender(
        db_session, _tender("TEST-MATCH-BUDGET-OUT", budget_with_vat=Decimal("500000.00"))
    )
    await db_session.flush()

    provider = _provider(min_budget=Decimal("10000.00"), max_budget=Decimal("200000.00"))
    items, total = await list_matches(db_session, provider, limit=10, offset=0)

    assert total == 1
    assert items[0].expediente == "TEST-MATCH-BUDGET-IN"


async def test_list_matches_excludes_missing_budget_when_provider_has_a_range(
    db_session: AsyncSession,
) -> None:
    """Protects the conservative default: a tender with no declared budget can't be verified
    as "within range", so it's excluded rather than let in for free.
    """
    await upsert_tender(db_session, _tender("TEST-MATCH-BUDGET-MISSING", budget_with_vat=None))
    await db_session.flush()

    provider = _provider(min_budget=Decimal("10000.00"))
    items, total = await list_matches(db_session, provider, limit=10, offset=0)

    assert total == 0
    assert items == []


async def test_list_matches_filters_by_provider_locations(db_session: AsyncSession) -> None:
    """Protects the location filter: applies only when the provider restricts to provinces."""
    await upsert_tender(db_session, _tender("TEST-MATCH-LOC-MAD", location="Madrid"))
    await upsert_tender(db_session, _tender("TEST-MATCH-LOC-AST", location="Asturias"))
    await db_session.flush()

    provider = _provider(locations=["Madrid"])
    items, total = await list_matches(db_session, provider, limit=10, offset=0)

    assert total == 1
    assert items[0].expediente == "TEST-MATCH-LOC-MAD"


async def test_list_matches_does_not_restrict_location_when_provider_has_none(
    db_session: AsyncSession,
) -> None:
    """Protects `locations=None` meaning "no restriction", not "matches nothing"."""
    await upsert_tender(db_session, _tender("TEST-MATCH-LOC-ANY", location="Cantabria"))
    await db_session.flush()

    items, total = await list_matches(db_session, _provider(locations=None), limit=10, offset=0)

    assert total == 1
    assert items[0].expediente == "TEST-MATCH-LOC-ANY"


async def test_funnel_stage_counts_are_cumulative_and_non_increasing(
    db_session: AsyncSession,
) -> None:
    """Protects the funnel's core property: each stage only narrows, never widens the one before.

    `total`/`after_status` count across the *entire* real table by design
    (that's the point of instrumenting the funnel: the real corpus-wide
    survival rate) -- Docker persists ~3,500+ real tenders in the same
    Postgres these tests use, most already `open_for_submission`, so an
    absolute count here would assert against data this test doesn't own.
    Comparing the delta this test's own three rows cause is what isolates
    it, the same way `LIST_TEST_CPV`/`MATCH_CPV` isolate the CPV-scoped
    filters elsewhere.
    """
    provider = _provider(min_budget=Decimal("10000.00"), max_budget=Decimal("200000.00"))
    before = await funnel_stage_counts(db_session, provider)

    await upsert_tender(
        db_session,
        _tender("TEST-FUNNEL-SURVIVES-ALL", status=TenderStatus.OPEN_FOR_SUBMISSION),
    )
    await upsert_tender(
        # Wrong status: counted in `total`, filtered out from `after_status` onward.
        db_session,
        _tender("TEST-FUNNEL-WRONG-STATUS", status=TenderStatus.AWARDED),
    )
    await upsert_tender(
        # Right status, wrong CPV: survives `after_status`, filtered out from `after_cpv` onward.
        db_session,
        _tender(
            "TEST-FUNNEL-WRONG-CPV",
            status=TenderStatus.OPEN_FOR_SUBMISSION,
            cpv_codes=["72999999"],
        ),
    )
    await db_session.flush()

    after = await funnel_stage_counts(db_session, provider)

    assert after.total == before.total + 3
    assert after.after_status == before.after_status + 2
    assert after.after_cpv == before.after_cpv + 1
    assert after.after_budget == before.after_budget + 1
    assert after.after_location == before.after_location + 1
    assert after.total >= after.after_status >= after.after_cpv
    assert after.after_cpv >= after.after_budget >= after.after_location
