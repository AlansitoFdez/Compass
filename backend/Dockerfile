# Compass backend: one image, three roles (api, worker, beat) chosen by the command.
#
# Two stages, and the split is not about image size for its own sake -- it is about the
# embedding model. `sentence-transformers` downloads ~570 MB from Hugging Face the first
# time it is asked to encode anything. Left to runtime that download happens inside the
# first `GET /matches` a user makes, on a machine that may be offline, and repeats every
# time the container is recreated. Baking it into the image (decided in Fase 2) makes the
# first request fast and the container work without network access to Hugging Face at all.

FROM python:3.13-slim AS builder

# uv, pinned to the version that produced uv.lock -- the same guarantee CI gets from
# `--locked`, so an upstream uv release can never change what ends up installed here.
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies before source: this layer is the expensive one (torch alone is ~200 MB on
# the CPU index pyproject.toml points Linux at), and it only rebuilds when the lock does.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# The model, fetched once at build time into the image's own Hugging Face cache. The name
# comes from `matching/embedding_model.py` rather than being repeated here, so changing the
# model changes what gets baked with nothing to keep in sync -- and that module imports
# nothing on purpose, which is what lets this run before any configuration exists. Reading
# it from `matching/embeddings.py` instead failed this build with a pydantic validation
# error: that module reaches the ORM, which reaches `core.db`, which builds an engine from
# `Settings` at import time.
ENV HF_HOME=/opt/huggingface
RUN /app/.venv/bin/python -c "\
from sentence_transformers import SentenceTransformer; \
from compass.matching.embedding_model import EMBEDDING_MODEL_NAME; \
SentenceTransformer(EMBEDDING_MODEL_NAME)"


FROM python:3.13-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/huggingface \
    # Offline: the model is already in the image, and without this the library still
    # reaches out to check for updates on every load -- which is a startup that fails on a
    # machine with no internet, for a file it already has.
    HF_HUB_OFFLINE=1

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /opt/huggingface /opt/huggingface
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

# Not root. Nothing here needs it, and the writable state (beat's schedule file) lives on
# a mounted volume whose ownership is set below.
RUN useradd --create-home --uid 1000 compass \
    && mkdir -p /app/state \
    && chown -R compass:compass /app
USER compass

# The API is the default role; worker and beat override this in docker-compose.yml.
CMD ["python", "-m", "compass", "--host", "0.0.0.0"]
