"""Tests for GET /health — the liveness check — and the CORS policy around it, over the
real ASGI app. `/health` stands in for every route here: the middleware is applied to the
whole app, so what it does on the cheapest endpoint is what it does on all of them.
"""

from fastapi.testclient import TestClient

from compass.core.config import get_settings


def test_health_check_returns_ok(client: TestClient) -> None:
    """Protects the fixed payload the liveness check promises."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_the_api_allows_the_dashboard_origin_to_call_it(client: TestClient) -> None:
    """Protects the dashboard's ability to reach the API at all (5.1).

    The analysis panel triggers `POST /analyze` and polls `GET /analysis` straight from
    the browser, so without this header every one of those calls is blocked before it
    leaves the page -- with nothing failing server-side to explain why.
    """
    origin = get_settings().cors_origins[0]

    response = client.get("/health", headers={"Origin": origin})

    assert response.headers["access-control-allow-origin"] == origin


def test_the_api_does_not_allow_an_unknown_origin(client: TestClient) -> None:
    """Protects the decision not to use `allow_origins=["*"]`: an origin that isn't
    configured gets no CORS header, so the browser refuses the response.
    """
    response = client.get("/health", headers={"Origin": "https://not-the-dashboard.example"})

    assert "access-control-allow-origin" not in response.headers
