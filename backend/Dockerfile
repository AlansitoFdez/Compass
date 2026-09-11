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

# The model, fetched once at build time into the image's own Hugging Face cache.
#
# Before the source, and copying only the one file it needs, so that ~570 MB of weights
# are not re-downloaded every time a line of application code changes. With `COPY src`
# above this step -- where it sat until 5.5 -- a one-line edit meant a five-minute rebuild.
#
# `runpy.run_path` runs that file on its own instead of importing the package, which isn't
# installed at this point. It works because `embedding_model.py` imports nothing,
# deliberately: reading the name from `matching/embeddings.py` instead failed this build
# with a pydantic validation error, since that module reaches the ORM, which reaches
# `core.db`, which builds an engine from `Settings` at import time.
ENV HF_HOME=/opt/huggingface
COPY src/compass/matching/embedding_model.py /tmp/embedding_model.py
RUN /app/.venv/bin/python -c "\
import runpy; \
from sentence_transformers import SentenceTransformer; \
SentenceTransformer(runpy.run_path('/tmp/embedding_model.py')['EMBEDDING_MODEL_NAME'])"

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


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
