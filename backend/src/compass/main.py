from fastapi import FastAPI

from compass.api.router import api_router
from compass.core.config import get_settings


def create_app() -> FastAPI:
    get_settings()  # fail fast if the environment is misconfigured

    app = FastAPI(title="Compass API")
    app.include_router(api_router)

    return app


app = create_app()
