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
    assert body["returned"] == len(body["items"])
    assert 0 < len(body["items"]) <= 5

    scores = [item["rrf_score"] for item in body["items"]]
    assert scores == sorted(scores, reverse=True)

    first = body["items"][0]
    assert "tender" in first
    assert first["lexical_rank"] is not None or first["vector_rank"] is not None


@pytest.mark.real_corpus
def test_get_matches_reports_the_funnel_total_not_the_page_size(client: TestClient) -> None:
    """Protects the meaning of `total`: how many tenders survive the funnel, not how many
    fit in the response.

    Until 5.2 it was `len(items)`, so it always equalled whatever `limit` the caller had
    just asked for -- and the dashboard printed it as "N resultados del embudo". Asking
    twice with different limits is what makes that indistinguishable-looking bug visible:
    the corpus doesn't change between the two calls, so `total` must not either.
    """
    small = client.get("/matches", params={"limit": 3}).json()
    large = client.get("/matches", params={"limit": 20}).json()

    assert small["total"] == large["total"]
    assert small["returned"] == 3
    assert small["total"] > small["returned"]


@pytest.mark.real_corpus
def test_get_matches_reports_the_funnel_stages_in_non_increasing_order(client: TestClient) -> None:
    """Protects the stage counts the dashboard states the reduction with: each stage adds a
    filter on top of the previous one, so the sequence can only shrink, and the last stage
    is by definition the same number as `total`.
    """
    body = client.get("/matches", params={"limit": 5}).json()
    funnel = body["funnel"]

    stages = [
        funnel["total"],
        funnel["after_status"],
        funnel["after_cpv"],
        funnel["after_budget"],
        funnel["after_location"],
    ]
    assert stages == sorted(stages, reverse=True)
    assert funnel["after_location"] == body["total"]


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
