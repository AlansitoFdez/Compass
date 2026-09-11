"""Tests for GET/PUT /provider and POST /ingestion/backfill over the real ASGI app.

Real commits, not the usual flush()+rollback `db_session` pattern -- same reasoning as
`test_tenders_endpoint.py`'s own module docstring: the real app's `get_db()` dependency
runs on a different event loop than pytest-asyncio's, so only a real commit is guaranteed
visible to it.

These tests restore the seeded profile afterwards. It is shared, real state that the
funnel tests and the development environment both read, and a test that left its own
fixture behind would quietly change what every later assertion is ranking against.
"""

from collections.abc import AsyncIterator
from decimal import Decimal
from unittest.mock import patch

import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from compass.providers.repository import get_provider, upsert_provider
from compass.providers.schemas import ProviderSchema
from compass.providers.seed import PROFILE

_TEST_PROFILE = {
    "description": "Instalación y mantenimiento de sistemas de climatización industrial.",
    "cpv_codes": ["45331000"],
    "min_budget": "25000.00",
    "max_budget": "300000.00",
    "annual_revenue": "1200000.00",
    "certifications": ["ISO 9001"],
    "locations": ["Madrid"],
}


@pytest_asyncio.fixture
async def restore_seeded_profile(db_session: AsyncSession) -> AsyncIterator[None]:
    """Puts the real seeded profile back after a test has overwritten it."""
    yield
    await upsert_provider(db_session, PROFILE)
    await db_session.commit()


def test_get_provider_returns_the_seeded_profile(client: TestClient) -> None:
    """Protects the read the dashboard makes on every visit to the profile screen."""
    response = client.get("/provider")

    assert response.status_code == 200
    body = response.json()
    assert body["description"] == PROFILE.description
    assert body["cpv_codes"] == PROFILE.cpv_codes


def test_get_provider_returns_404_when_nothing_is_saved(client: TestClient) -> None:
    """Protects the state a fresh install starts in.

    A 404 here is not an error condition: it is what the dashboard turns into its
    onboarding screen, so it has to stay distinguishable from a real failure. Mocked
    rather than deleting the row, which the funnel tests and the dev environment share.
    """
    with patch("compass.api.routes.providers.get_provider", return_value=None):
        response = client.get("/provider")

    assert response.status_code == 404


async def test_put_provider_replaces_the_profile(
    client: TestClient, db_session: AsyncSession, restore_seeded_profile: None
) -> None:
    """Protects the write the onboarding form makes: what comes back is what was stored,
    and the next read sees it.
    """
    response = client.put("/provider", json=_TEST_PROFILE)

    assert response.status_code == 200
    assert response.json()["description"] == _TEST_PROFILE["description"]

    stored = await get_provider(db_session)
    assert stored is not None
    assert stored.description == _TEST_PROFILE["description"]
    assert stored.annual_revenue == Decimal("1200000.00")


async def test_put_provider_clears_a_field_that_is_sent_empty(
    client: TestClient, db_session: AsyncSession, restore_seeded_profile: None
) -> None:
    """Protects the reason this is a PUT and not a PATCH.

    "I hold no certifications" and "I didn't mention certifications" are different facts,
    and the difference decides verdicts: a pliego requiring ISO 27001 blocks a provider
    who declares none. A partial update would collapse the two.
    """
    client.put("/provider", json=_TEST_PROFILE)
    client.put("/provider", json={**_TEST_PROFILE, "certifications": []})

    stored = await get_provider(db_session)
    assert stored is not None
    assert stored.certifications == []


def test_put_provider_rejects_a_profile_with_no_description(client: TestClient) -> None:
    """Protects the funnel's own input: the description is the text both recoverers rank
    against, so a profile without one would survive validation and then rank nothing.
    """
    incomplete = {key: value for key, value in _TEST_PROFILE.items() if key != "description"}

    assert client.put("/provider", json=incomplete).status_code == 422


def test_put_provider_rejects_a_non_numeric_budget(client: TestClient) -> None:
    """Protects against a typo in the form reaching a Numeric column as a string."""
    response = client.put("/provider", json={**_TEST_PROFILE, "min_budget": "mucho"})

    assert response.status_code == 422


def test_post_backfill_enqueues_the_task(client: TestClient) -> None:
    """Protects the wiring of the cold-start trigger: the endpoint enqueues and answers
    immediately, because the work is minutes long and there is no result backend.
    """
    with patch("compass.api.routes.ingestion.backfill_historical_task") as mocked_task:
        response = client.post("/ingestion/backfill")

    assert response.status_code == 202
    mocked_task.delay.assert_called_once_with()


def test_the_seeded_profile_is_a_valid_profile() -> None:
    """`seed.py` is an example now, not the source of truth -- but it is the example a
    reader copies, so it has to keep validating against the same schema the form posts.
    """
    assert ProviderSchema.model_validate(PROFILE.model_dump())
