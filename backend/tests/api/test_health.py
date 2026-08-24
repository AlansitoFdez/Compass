"""Tests for GET /health — the liveness check, over the real ASGI app."""

from fastapi.testclient import TestClient


def test_health_check_returns_ok(client: TestClient) -> None:
    """Protects the fixed payload the liveness check promises."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
