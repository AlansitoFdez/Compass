"""ASGI entry point: the FastAPI application Uvicorn serves."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from compass.api.router import api_router
from compass.core.config import get_settings


def create_app() -> FastAPI:
    """Builds the FastAPI app, with every route from `api_router` mounted."""
    settings = get_settings()  # fail fast if the environment is misconfigured

    app = FastAPI(title="Compass API")
    # The dashboard (5.1) triggers an analysis and polls for it straight from the
    # browser, so its origin has to be allowed explicitly. A configured list, never
    # `["*"]`: the wildcard is the kind of default that survives all the way into a
    # deployment, and this API has write-ish endpoints (POST /analyze enqueues work).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    return app


app = create_app()
