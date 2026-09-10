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
        langfuse_public_key: Langfuse Cloud public key (Fase 4) -- identifies
            the project, safe to appear in client-side code, but still kept
            here so a missing one fails at startup rather than silently.
        langfuse_secret_key: Langfuse Cloud secret key (Fase 4).
        langfuse_base_url: Langfuse API host. Defaults to the EU Cloud
            region; override in `.env` if the account lives in another
            region (e.g. `https://us.cloud.langfuse.com`).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str
    redis_url: str
    openrouter_api_key: str
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_base_url: str = "https://cloud.langfuse.com"


@lru_cache
def get_settings() -> Settings:
    """The settings instance shared by the whole process.

    Cached so `.env` is parsed once and every caller sees the same object,
    which is what makes it safe to call this at import time.

    Returns:
        The validated settings for this process.
    """
    return Settings()
