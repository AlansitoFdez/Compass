"""Single entry point that aggregates every route module into one router for `main.py`."""

from fastapi import APIRouter

from compass.api.routes import health, matches, tenders

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(tenders.router)
api_router.include_router(matches.router)
