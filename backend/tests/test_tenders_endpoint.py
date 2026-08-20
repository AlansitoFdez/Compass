"""Tests for GET /tenders over the real ASGI app — wiring, envelope shape, and
validation. Exhaustive filter logic is already covered at the repository level
in test_tender_repository.py; here we only need one filter exercised end to
end to prove the query params actually reach list_tenders().
"""

from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from compass.core.db import get_db
from compass.main import app
from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.repository import upsert_tender
from compass.tenders.schemas import TenderSchema

# Distinto del usado en test_tender_repository.py, aunque hoy no compartan
# transacción: cada test aísla sus propias filas del resto de la tabla real.
ENDPOINT_TEST_CPV = "99999998"


def _tender(expediente: str, **overrides: object) -> TenderSchema:
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


@pytest.fixture
def db_client(db_session: AsyncSession) -> Iterator[TestClient]:
    """TestClient cuyo `get_db` está sobrescrito para devolver el `db_session` del
    propio test: lo que se inserta (solo flush, sin commit) en el test es visible
    para la petición HTTP, y el rollback de `db_session` deshace todo al terminar.
    """

    async def _override() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


async def test_get_tenders_returns_envelope_shape(
    db_session: AsyncSession, db_client: TestClient
) -> None:
    await upsert_tender(db_session, _tender("TEST-EP-SHAPE"))
    await db_session.flush()

    response = db_client.get("/tenders", params={"cpv": ENDPOINT_TEST_CPV})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert body["items"][0]["expediente"] == "TEST-EP-SHAPE"


async def test_get_tenders_applies_status_filter(
    db_session: AsyncSession, db_client: TestClient
) -> None:
    await upsert_tender(
        db_session, _tender("TEST-EP-OPEN", status=TenderStatus.OPEN_FOR_SUBMISSION)
    )
    await upsert_tender(db_session, _tender("TEST-EP-AWARDED", status=TenderStatus.AWARDED))
    await db_session.flush()

    response = db_client.get("/tenders", params={"cpv": ENDPOINT_TEST_CPV, "status": "awarded"})

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["expediente"] == "TEST-EP-AWARDED"


def test_get_tenders_rejects_limit_over_max(client: TestClient) -> None:
    response = client.get("/tenders", params={"limit": 101})

    assert response.status_code == 422


def test_get_tenders_rejects_negative_offset(client: TestClient) -> None:
    response = client.get("/tenders", params={"offset": -1})

    assert response.status_code == 422
