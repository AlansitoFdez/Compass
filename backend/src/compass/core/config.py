"""Application settings, loaded and validated from environment variables / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed configuration for the whole application.

    Values are read from the environment first and from `.env` as a fallback.
    Fields without a default are required, so a missing one stops the process
    at startup with a validation error naming the field, instead of surfacing
    much later as an obscure connection failure.

    Attributes:
        app_env: Name of the deployment environment.
        log_level: Root log level used by the entry points.
        database_url: PostgreSQL DSN, in its plain `postgresql://` form; the
            async driver is spliced in by `compass.core.db`.
        redis_url: Redis DSN, shared by the Celery broker and the ingestion
            checkpoint store.
        openrouter_api_key: OpenRouter API key used by the pliego analyst
            agent (Fase 3) to call its extraction models.
        langfuse_public_key: Langfuse Cloud public key (Fase 4), or `None`.
            Optional on purpose: tracing is how *this* project watches what
            its model calls cost, not something the tool needs to work, and
            requiring a second account from someone who just wants to try
            Compass would be a tax on curiosity. Without both keys the
            client is built disabled and every observation becomes a no-op
            (see `analysis.tracing`).
        langfuse_secret_key: Langfuse Cloud secret key (Fase 4), or `None`.
        langfuse_base_url: Langfuse API host. Defaults to the EU Cloud
            region; override in `.env` if the account lives in another
            region (e.g. `https://us.cloud.langfuse.com`).
        cors_origins: Origins the browser is allowed to call this API from
            (Fase 5) -- the dashboard's dev server by default. A list, not
            a wildcard: see `compass.main.create_app`.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str
    redis_url: str
    # Required: without it the analyst agent has nothing to call, which is
    # the one thing Compass cannot do without.
    openrouter_api_key: str
    # Optional: see the class docstring.
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """The settings instance shared by the whole process.

    Cached so `.env` is parsed once and every caller sees the same object,
    which is what makes it safe to call this at import time.

    Returns:
        The validated settings for this process.
    """
    return Settings()
