"""Single entry point that aggregates every route module into one router for `main.py`."""

from fastapi import APIRouter

from compass.api.routes import analysis, health, ingestion, matches, providers, tenders

api_router = APIRouter()
api_router.include_router(health.router)
# Before `tenders`, and that order is load-bearing: FastAPI matches routes in
# declaration order, and `GET /tenders/{expediente:path}` (5.1) matches slashes --
# including the one in `/tenders/{expediente}/analysis`. Registered the other way
# round, every analysis read would be answered by the tender detail route instead.
api_router.include_router(analysis.router)
api_router.include_router(tenders.router)
api_router.include_router(matches.router)
api_router.include_router(providers.router)
api_router.include_router(ingestion.router)
