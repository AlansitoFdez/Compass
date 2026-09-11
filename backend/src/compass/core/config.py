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
            agent (Fase 3), or `None`. Optional since 5.5, and the reasoning
            is the same as Langfuse's: everything that is not the agent --
            ingestion, the funnel, the hybrid ranking, the whole dashboard --
            works without it, and demanding an account from someone who just
            wants to see Compass run is a tax paid before they have seen
            anything. Without it the API still starts and
            `GET /capabilities` reports analysis as unavailable, so the
            dashboard can say what is missing instead of failing on a click.
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
    # Optional, like the Langfuse keys below: see the class docstring.
    openrouter_api_key: str | None = None
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


class MissingOpenRouterKeyError(RuntimeError):
    """Raised where an OpenRouter key is genuinely required and isn't configured.

    Separate from a plain `RuntimeError` so the few places that can do something about it
    -- the analysis task, which records it as a readable failure, and the eval scripts,
    which stop with a message -- can tell it apart from a real bug.
    """

    def __init__(self) -> None:
        super().__init__(
            "Falta OPENROUTER_API_KEY en el .env. Es gratuita en openrouter.ai y sólo hace "
            "falta para analizar pliegos: el resto de Compass funciona sin ella."
        )


def require_openrouter_key() -> str:
    """The OpenRouter key, for code that cannot proceed without one.

    The key is optional in `Settings` (5.5) so the API starts and the whole funnel works
    unconfigured. This is the boundary where that optionality ends.

    Raises:
        MissingOpenRouterKeyError: No key is configured.

    Returns:
        The configured key.
    """
    key = get_settings().openrouter_api_key
    if key is None:
        raise MissingOpenRouterKeyError
    return key
