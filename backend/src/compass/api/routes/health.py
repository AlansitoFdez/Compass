"""Liveness check — confirms the process is up, independent of any external dependency."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Fixed payload -- reaching this handler at all is the actual check."""
    return {"status": "ok"}
