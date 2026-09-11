"""Tests for GET /tenders over the real ASGI app — wiring, envelope shape, and
validation. Exhaustive filter logic is already covered at the repository level
in test_tender_repository.py; here we only need one filter exercised end to
end to prove the query params actually reach list_tenders().

Real commits, not the usual flush()+rollback db_session pattern: GET /tenders
runs through the real get_db() dependency, on whatever event loop TestClient
happens to run requests on -- confirmed empirically to be a *different* loop
than pytest-asyncio's own. The 1.10 version of this file worked around that
by overriding get_db() to hand the endpoint the test's own db_session, so an
uncommitted transaction ended up shared across two event loops -- exactly
the psycopg-async danger create_task_engine()/NullPool exist to avoid (1.9).
Committing the fixture data for real sidesteps the whole problem: a commit
is visible to any connection on any loop, so there's nothing left to share.
"""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.models import Tender
from compass.tenders.repository import upsert_tender
from compass.tenders.schemas import TenderSchema

ENDPOINT_TEST_CPV = "99999998"


def _tender(expediente: str, **overrides: object) -> TenderSchema:
    """A minimal valid `TenderSchema` for the endpoint tests, with `overrides` applied."""
    defaults: dict[str, object] = {
        "expediente": expediente,
        "contracting_body": "Ayuntamiento de Prueba",
        "title": "Servicio de prueba",
        "cpv_codes": [ENDPOINT_TEST_CPV],
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


async def _seed(db_session: AsyncSession, *tenders: TenderSchema) -> None:
    """Upserts and commits `tenders` for real -- see the module docstring for why a real commit."""
    for tender in tenders:
        await upsert_tender(db_session, tender)
    await db_session.commit()


async def _cleanup(db_session: AsyncSession) -> None:
    """Deletes every row this test module seeded, committed for real like `_seed`."""
    await db_session.execute(delete(Tender).where(Tender.cpv_codes.contains([ENDPOINT_TEST_CPV])))
    await db_session.commit()


async def test_get_tenders_returns_envelope_shape(
    db_session: AsyncSession, client: TestClient
) -> None:
    """Protects the wiring end to end.

    Query params must reach `list_tenders`, and the response must match `TenderListResponse`.
    """
    try:
        await _seed(db_session, _tender("TEST-EP-SHAPE"))

        response = client.get("/tenders", params={"cpv": ENDPOINT_TEST_CPV})

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["limit"] == 20
        assert body["offset"] == 0
        assert body["items"][0]["expediente"] == "TEST-EP-SHAPE"
    finally:
        await _cleanup(db_session)


async def test_get_tenders_applies_status_filter(
    db_session: AsyncSession, client: TestClient
) -> None:
    """Protects that a query param actually reaches `list_tenders`.

    One filter, exercised end to end -- exhaustive filter logic is already
    covered at the repository level, in test_tender_repository.py.
    """
    try:
        await _seed(
            db_session,
            _tender("TEST-EP-OPEN", status=TenderStatus.OPEN_FOR_SUBMISSION),
            _tender("TEST-EP-AWARDED", status=TenderStatus.AWARDED),
        )

        response = client.get("/tenders", params={"cpv": ENDPOINT_TEST_CPV, "status": "awarded"})

        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["expediente"] == "TEST-EP-AWARDED"
    finally:
        await _cleanup(db_session)


def test_get_tenders_rejects_limit_over_max(client: TestClient) -> None:
    """Protects `MAX_LIMIT`: a client can't request more than 100 rows in one call."""
    response = client.get("/tenders", params={"limit": 101})

    assert response.status_code == 422


def test_get_tenders_rejects_negative_offset(client: TestClient) -> None:
    """Protects against a negative offset being silently accepted instead of rejected."""
    response = client.get("/tenders", params={"offset": -1})

    assert response.status_code == 422


async def test_get_tender_returns_one_tender_by_expediente(
    db_session: AsyncSession, client: TestClient
) -> None:
    """Protects the dashboard's tender page (5.1): a tender is readable on its own,
    not only as part of a list response.
    """
    expediente = "TEST-EP-DETAIL"
    try:
        await _seed(db_session, _tender(expediente, title="Portal web municipal"))

        response = client.get(f"/tenders/{expediente}")

        assert response.status_code == 200
        body = response.json()
        assert body["expediente"] == expediente
        assert body["title"] == "Portal web municipal"
    finally:
        await _cleanup(db_session)


async def test_get_tender_finds_an_expediente_containing_slashes(
    db_session: AsyncSession, client: TestClient
) -> None:
    """Protects the `:path` converter against the shape of real PLACSP expedientes.

    `SER/2026/0000006435` and `300/2026/01246` are real entries in the golden set --
    with the default converter, which stops at the first slash, their own detail page
    would 404.
    """
    expediente = "TEST/EP/2026/0001"
    try:
        await _seed(db_session, _tender(expediente))

        response = client.get(f"/tenders/{expediente}")

        assert response.status_code == 200
        assert response.json()["expediente"] == expediente
    finally:
        await _cleanup(db_session)


def test_get_tender_returns_404_for_an_unknown_expediente(client: TestClient) -> None:
    """Protects the missing case: a 404, not a 500 or an empty object."""
    assert client.get("/tenders/TEST-EP-DOES-NOT-EXIST").status_code == 404


def test_the_tender_detail_route_does_not_swallow_the_analysis_route(client: TestClient) -> None:
    """Protects the router order (5.1): `/tenders/{expediente:path}` matches slashes, so
    registered before the analysis router it would answer `/tenders/X/analysis` itself.

    A 404 is expected here either way -- that tender doesn't exist -- so the tell is
    *which* endpoint produced it: the analysis route says "has not been analyzed yet",
    the detail route says "Tender not found".

    Checked with a slash-carrying expediente too, and that half is the one that matters:
    the slash-free case passed even while the analysis routes were declared as a single
    path segment (5.2), which is exactly why the bug survived a test that only covered it.
    """
    for expediente in ("TEST-EP-DOES-NOT-EXIST", "TEST/EP/DOES/NOT/EXIST - con barras"):
        response = client.get(f"/tenders/{expediente}/analysis")

        assert response.status_code == 404
        assert response.json()["detail"] == "This tender has not been analyzed yet"
