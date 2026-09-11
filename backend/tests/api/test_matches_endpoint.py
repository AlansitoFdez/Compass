"""Tests for GET /matches over the real ASGI app — wiring, envelope shape, and the 404 when no
provider is seeded. Fusion logic itself is already covered at the repository level in
test_fusion.py; here we only need the real seeded provider and corpus to prove the wiring works
end to end, same split as test_tenders_endpoint.py.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# Needs the real PLACSP corpus persisted locally, which a CI runner doesn't have --
# see docs/phases/phase4/subphases/phase4.6.md.
@pytest.mark.real_corpus
def test_get_matches_returns_envelope_shape_ranked_by_rrf_score(client: TestClient) -> None:
    """Protects the wiring end to end: the real seeded provider and real embedded corpus produce
    a non-empty, correctly ordered response matching `MatchListResponse`.
    """
    response = client.get("/matches", params={"limit": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 5
    assert body["total"] == len(body["items"])
    assert 0 < len(body["items"]) <= 5

    scores = [item["rrf_score"] for item in body["items"]]
    assert scores == sorted(scores, reverse=True)

    first = body["items"][0]
    assert "tender" in first
    assert first["lexical_rank"] is not None or first["vector_rank"] is not None


def test_get_matches_returns_404_when_no_provider_is_seeded(client: TestClient) -> None:
    """Protects the one place in the project that turns a missing singleton row into a proper
    404 instead of an unhandled exception -- mocked, not a real delete: the seeded provider is
    shared, real state other tests (and the dev environment) depend on.
    """
    with patch("compass.api.routes.matches.get_provider", return_value=None):
        response = client.get("/matches")

    assert response.status_code == 404


def test_get_matches_rejects_limit_over_max(client: TestClient) -> None:
    """Protects `MAX_LIMIT`: a client can't request more than 100 fused matches in one call."""
    response = client.get("/matches", params={"limit": 101})

    assert response.status_code == 422


def test_get_matches_rejects_negative_limit(client: TestClient) -> None:
    """Protects against a non-positive `limit` being silently accepted instead of rejected."""
    response = client.get("/matches", params={"limit": 0})

    assert response.status_code == 422
