"""Tests for GET /capabilities and the 503 that replaces a doomed analysis run.

Both exist for the same reason and are tested together: since 5.5 Compass starts with no
keys configured, so the dashboard has to be able to say what is missing rather than let
someone click a button that fails a minute later.
"""

from datetime import UTC, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from compass.core.config import Settings
from compass.tenders.enums import ContractType, TenderStatus
from compass.tenders.models import Tender

_NO_KEYS = Settings(
    _env_file=None,
    database_url="postgresql://u:p@localhost:5432/db",
    redis_url="redis://localhost:6379/0",
)
_WITH_KEYS = Settings(
    _env_file=None,
    database_url="postgresql://u:p@localhost:5432/db",
    redis_url="redis://localhost:6379/0",
    openrouter_api_key="sk-test",
    langfuse_public_key="pk-test",
    langfuse_secret_key="sk-test",
)


def test_capabilities_reports_everything_off_when_nothing_is_configured(
    client: TestClient,
) -> None:
    """Protects what a fresh install answers: not an error, a truthful inventory."""
    with patch("compass.api.routes.capabilities.get_settings", return_value=_NO_KEYS):
        response = client.get("/capabilities")

    assert response.status_code == 200
    assert response.json() == {"analysis": False, "tracing": False}


def test_capabilities_reports_everything_on_when_fully_configured(client: TestClient) -> None:
    """The other direction, so "off" can't quietly become the only answer it ever gives."""
    with patch("compass.api.routes.capabilities.get_settings", return_value=_WITH_KEYS):
        response = client.get("/capabilities")

    assert response.json() == {"analysis": True, "tracing": True}


def test_capabilities_never_returns_key_material(client: TestClient) -> None:
    """Protects the one rule this endpoint has. It answers a browser, and whether a key is
    set is all a browser needs -- the key itself must never be part of the answer.
    """
    with patch("compass.api.routes.capabilities.get_settings", return_value=_WITH_KEYS):
        body = client.get("/capabilities").text

    assert "sk-test" not in body
    assert "pk-test" not in body


async def test_analyze_refuses_with_503_when_there_is_no_openrouter_key(
    client: TestClient, db_session: AsyncSession
) -> None:
    """Protects the fast refusal, on a tender that really exists.

    Without a key the run would be enqueued, reach OpenRouter, come back 401 and land as a
    failed analysis minutes later. Refusing up front turns that into a sentence the reader
    can act on -- and 503 rather than 500, because nothing is broken: the installation
    simply isn't configured for this.
    """
    expediente = "TEST-EP-NO-KEY"
    try:
        db_session.add(
            Tender(
                expediente=expediente,
                contracting_body="Ayuntamiento de Prueba",
                title="Servicio de prueba",
                cpv_codes=["72000000"],
                contract_type=ContractType.SERVICES,
                procedure_type="Abierto",
                status=TenderStatus.OPEN_FOR_SUBMISSION,
                published_at=datetime.now(UTC),
                updated_at_source=datetime.now(UTC),
                pcap_url="https://fake/pliego.pdf",
            )
        )
        await db_session.commit()

        with (
            patch("compass.api.routes.analysis.get_settings", return_value=_NO_KEYS),
            patch("compass.api.routes.analysis.analyze_tender_task") as mocked_task,
        ):
            response = client.post(f"/tenders/{expediente}/analyze")

        assert response.status_code == 503
        assert "OPENROUTER_API_KEY" in response.json()["detail"]
        # Nothing was queued: the point is that no doomed run reaches the worker.
        mocked_task.delay.assert_not_called()
    finally:
        await db_session.execute(delete(Tender).where(Tender.expediente == expediente))
        await db_session.commit()


async def test_analyze_still_checks_the_tender_before_the_key(
    client: TestClient,
) -> None:
    """Protects the order of the checks: a missing tender is still a 404, not a 503.

    The key check runs last on purpose -- reporting "you have no API key" for a tender
    that doesn't exist would send the reader to fix the wrong thing.
    """
    with patch("compass.api.routes.analysis.get_settings", return_value=_NO_KEYS):
        response = client.post("/tenders/TEST-EP-DOES-NOT-EXIST/analyze")

    assert response.status_code == 404
