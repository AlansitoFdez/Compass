"""Tests for upsert_tender (idempotency) and list_tenders (filters, pagination) — real
Postgres, no mocking.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.models import Tender
from compass.tenders.repository import list_tenders, upsert_tender
from compass.tenders.schemas import TenderSchema

BASE_TENDER = TenderSchema(
    expediente="TEST-REPO-0001",
    contracting_body="Ayuntamiento de Prueba",
    title="Servicio de prueba",
    cpv_codes=["72000000"],
    contract_type=ContractType.SERVICES,
    procedure_type="Abierto",
    status=TenderStatus.OPEN_FOR_SUBMISSION,
    submission_deadline=datetime.now(UTC),
    published_at=datetime.now(UTC),
    updated_at_source=datetime.now(UTC),
)


async def _fetch_all(session: AsyncSession, expediente: str) -> list[Tender]:
    """Re-reads every row for `expediente` straight from Postgres, bypassing the session cache.

    `expire_all()` is required here, not decorative: without it, a query
    right after `upsert_tender` can return the session's stale in-memory
    copy instead of what Postgres actually has (see the finding in
    phase1.7.md).
    """
    session.expire_all()
    result = await session.execute(select(Tender).where(Tender.expediente == expediente))
    return list(result.scalars().all())


async def test_upsert_tender_creates_a_new_row(db_session: AsyncSession) -> None:
    """Protects the base case: upserting a brand-new expediente inserts exactly one row."""
    await upsert_tender(db_session, BASE_TENDER)
    await db_session.flush()

    assert len(await _fetch_all(db_session, BASE_TENDER.expediente)) == 1


async def test_upsert_tender_processed_twice_with_same_data_is_one_row(
    db_session: AsyncSession,
) -> None:
    """Protects the "no plain INSERT" rule from CLAUDE.md.

    Same expediente processed twice must still be one row.
    """
    await upsert_tender(db_session, BASE_TENDER)
    await upsert_tender(db_session, BASE_TENDER)
    await db_session.flush()

    assert len(await _fetch_all(db_session, BASE_TENDER.expediente)) == 1


async def test_upsert_tender_updates_fields_and_preserves_created_at(
    db_session: AsyncSession,
) -> None:
    """Protects the update half of upsert: changed fields land, created_at doesn't, updated_at does.

    A republished tender must overwrite `title`/`submission_deadline` in
    place, keep its original `created_at` (it's still the same row, not a
    new one), and bump `updated_at` past its previous value.
    """
    await upsert_tender(db_session, BASE_TENDER)
    await db_session.flush()
    first = (await _fetch_all(db_session, BASE_TENDER.expediente))[0]
    # Captured as plain values, not as attributes on `first`: the session's
    # identity map mutates `first` in place on the next query (same row =
    # same Python object), so comparing against `first.x` later would
    # compare an already-updated object against itself.
    first_created_at = first.created_at
    first_updated_at = first.updated_at

    modified = BASE_TENDER.model_copy(
        update={"title": "Servicio de prueba (modificado)", "submission_deadline": None}
    )
    await upsert_tender(db_session, modified)
    await db_session.flush()
    second = (await _fetch_all(db_session, BASE_TENDER.expediente))[0]

    assert second.title == "Servicio de prueba (modificado)"
    assert second.submission_deadline is None
    assert second.created_at == first_created_at
    assert second.updated_at > first_updated_at


# A CPV outside division 72 (IT services): no real ingested data uses it, so
# it isolates these tests' synthetic rows from the rest of the table --
# Docker persists ~1,200+ real tenders in the same Postgres the tests use.
LIST_TEST_CPV = "99999999"


def _list_tender(expediente: str, **overrides: object) -> TenderSchema:
    """A minimal valid `TenderSchema` for the `list_tenders` tests, with `overrides` applied."""
    defaults: dict[str, object] = {
        "expediente": expediente,
        "contracting_body": "Ayuntamiento de Prueba",
        "title": "Servicio de prueba",
        "cpv_codes": [LIST_TEST_CPV],
        "contract_type": ContractType.SERVICES,
        "procedure_type": "Abierto",
        "status": TenderStatus.OPEN_FOR_SUBMISSION,
        "budget_with_vat": Decimal("10000.00"),
        "location": "Asturias",
        "published_at": datetime.now(UTC),
        "updated_at_source": datetime.now(UTC),
    }
    defaults.update(overrides)
    return TenderSchema(**defaults)


async def test_list_tenders_filters_by_cpv_full_code_acts_as_exact_match(
    db_session: AsyncSession,
) -> None:
    """Protects the full-8-digit-code path: an exact match, never a prefix match on another code."""
    await upsert_tender(
        db_session, _list_tender("TEST-LIST-CPV-MATCH", cpv_codes=[LIST_TEST_CPV, "72200000"])
    )
    await upsert_tender(db_session, _list_tender("TEST-LIST-CPV-NOMATCH", cpv_codes=["72200000"]))
    await db_session.flush()

    items, total = await list_tenders(db_session, cpv=LIST_TEST_CPV, limit=10, offset=0)

    assert total == 1
    assert items[0].expediente == "TEST-LIST-CPV-MATCH"


async def test_list_tenders_filters_by_cpv_division_prefix(db_session: AsyncSession) -> None:
    """Protects the real use case that used to be broken: filtering by division (bug 7 of 1.11).

    `LIST_TEST_CPV = "99999999"` falls under the synthetic division "999".
    """
    await upsert_tender(
        db_session, _list_tender("TEST-LIST-CPV-DIV-MATCH", cpv_codes=[LIST_TEST_CPV])
    )
    await upsert_tender(
        db_session, _list_tender("TEST-LIST-CPV-DIV-NOMATCH", cpv_codes=["88888888"])
    )
    await db_session.flush()

    items, total = await list_tenders(db_session, cpv="999", limit=10, offset=0)

    assert total == 1
    assert items[0].expediente == "TEST-LIST-CPV-DIV-MATCH"


async def test_list_tenders_filters_by_cpv_normalizes_the_check_digit(
    db_session: AsyncSession,
) -> None:
    """Protects a caller passing a CPV filter with its check digit still attached.

    E.g. a value typed into a UI field, not yet normalized by the caller.
    """
    await upsert_tender(
        db_session, _list_tender("TEST-LIST-CPV-CHECKDIGIT", cpv_codes=[LIST_TEST_CPV])
    )
    await db_session.flush()

    items, total = await list_tenders(db_session, cpv=f"{LIST_TEST_CPV}-0", limit=10, offset=0)

    assert total == 1
    assert items[0].expediente == "TEST-LIST-CPV-CHECKDIGIT"


async def test_list_tenders_filters_by_status(db_session: AsyncSession) -> None:
    """Protects the `status` filter: only tenders in the requested status come back."""
    await upsert_tender(
        db_session, _list_tender("TEST-LIST-STATUS-OPEN", status=TenderStatus.OPEN_FOR_SUBMISSION)
    )
    await upsert_tender(
        db_session, _list_tender("TEST-LIST-STATUS-AWARDED", status=TenderStatus.AWARDED)
    )
    await db_session.flush()

    items, total = await list_tenders(
        db_session, cpv=LIST_TEST_CPV, status=TenderStatus.AWARDED, limit=10, offset=0
    )

    assert total == 1
    assert items[0].expediente == "TEST-LIST-STATUS-AWARDED"


async def test_list_tenders_filters_by_budget_range(db_session: AsyncSession) -> None:
    """Protects `min_budget`/`max_budget` as independent, inclusive bounds."""
    await upsert_tender(
        db_session, _list_tender("TEST-LIST-BUDGET-LOW", budget_with_vat=Decimal("5000.00"))
    )
    await upsert_tender(
        db_session, _list_tender("TEST-LIST-BUDGET-HIGH", budget_with_vat=Decimal("50000.00"))
    )
    await db_session.flush()

    above_10k, _ = await list_tenders(
        db_session, cpv=LIST_TEST_CPV, min_budget=Decimal("10000.00"), limit=10, offset=0
    )
    below_10k, _ = await list_tenders(
        db_session, cpv=LIST_TEST_CPV, max_budget=Decimal("10000.00"), limit=10, offset=0
    )

    assert [t.expediente for t in above_10k] == ["TEST-LIST-BUDGET-HIGH"]
    assert [t.expediente for t in below_10k] == ["TEST-LIST-BUDGET-LOW"]


async def test_list_tenders_filters_by_location(db_session: AsyncSession) -> None:
    """Protects the `location` filter: an exact match on `location`."""
    await upsert_tender(db_session, _list_tender("TEST-LIST-LOC-AST", location="Asturias"))
    await upsert_tender(db_session, _list_tender("TEST-LIST-LOC-MAD", location="Madrid"))
    await db_session.flush()

    items, total = await list_tenders(
        db_session, cpv=LIST_TEST_CPV, location="Madrid", limit=10, offset=0
    )

    assert total == 1
    assert items[0].expediente == "TEST-LIST-LOC-MAD"


async def test_list_tenders_combines_filters_with_and(db_session: AsyncSession) -> None:
    """Protects AND semantics: a row matching only one of two given filters must not come back."""
    await upsert_tender(
        db_session,
        _list_tender("TEST-LIST-AND-MATCH", status=TenderStatus.AWARDED, location="Madrid"),
    )
    await upsert_tender(
        db_session,
        # Matches on status but not on location: would pass under an OR by mistake.
        _list_tender("TEST-LIST-AND-PARTIAL", status=TenderStatus.AWARDED, location="Asturias"),
    )
    await db_session.flush()

    items, total = await list_tenders(
        db_session,
        cpv=LIST_TEST_CPV,
        status=TenderStatus.AWARDED,
        location="Madrid",
        limit=10,
        offset=0,
    )

    assert total == 1
    assert items[0].expediente == "TEST-LIST-AND-MATCH"


async def test_list_tenders_orders_by_published_at_desc_and_paginates(
    db_session: AsyncSession,
) -> None:
    """Protects newest-first ordering.

    Also that limit/offset return consistent, non-overlapping pages.
    """
    now = datetime.now(UTC)
    await upsert_tender(
        db_session, _list_tender("TEST-LIST-PAGE-OLD", published_at=now - timedelta(days=2))
    )
    await upsert_tender(
        db_session, _list_tender("TEST-LIST-PAGE-MID", published_at=now - timedelta(days=1))
    )
    await upsert_tender(db_session, _list_tender("TEST-LIST-PAGE-NEW", published_at=now))
    await db_session.flush()

    first_page, total = await list_tenders(db_session, cpv=LIST_TEST_CPV, limit=2, offset=0)
    second_page, _ = await list_tenders(db_session, cpv=LIST_TEST_CPV, limit=2, offset=2)

    assert total == 3
    assert [t.expediente for t in first_page] == ["TEST-LIST-PAGE-NEW", "TEST-LIST-PAGE-MID"]
    assert [t.expediente for t in second_page] == ["TEST-LIST-PAGE-OLD"]
