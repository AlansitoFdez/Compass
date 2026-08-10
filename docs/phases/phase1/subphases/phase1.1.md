# Subfase 1.1 — Scaffolding del backend

## Plan acordado

Del desglose de la Fase 1 (`docs/phases/phase1/phase1.md`): estructura de carpetas, `uv init`, esqueleto FastAPI (health check), ruff (lint + format), pytest, `.env.example` inicial.

Decisiones tomadas en la conversación de planificación:

- El proyecto Python vive en `backend/` (monorepo), separado del futuro frontend Next.js (Fase 5). Razón: la raíz del repo ya se trata como nivel de orquestación (README, CLAUDE.md, docs/), no de aplicación; meter el proyecto Python ahí rompería esa separación en cuanto llegue `frontend/` y forzaría una migración disruptiva más tarde (imports, tests, Docker, CI).
- Layout `src/` dentro de `backend/`, no plano. Razón: con `uv init --package`, `compass` se instala en modo editable en el `.venv`, así que tests y servidor siempre importan el paquete instalado, nunca por accidente vía el directorio de trabajo actual.
- Nombre del paquete: `compass` (no `compass_backend`) — `backend/` ya aporta ese contexto.
- Python **3.13** fijado. Razón: ciclo completo de madurez del ecosistema (release oct 2024) frente a 3.14 (release oct 2025, ~10 meses de vida), menor riesgo de que dependencias más pesadas de subfases posteriores (psycopg/asyncpg, pgvector, celery, langfuse) fuercen builds desde fuente por falta de wheels.
- Se incluye ya `pydantic-settings` con un `core/config.py` mínimo (`APP_ENV`, `LOG_LEVEL`), aunque `phase1.md` solo pedía el health check literalmente — así `.env.example` tiene un uso real desde ya en vez de quedar como placeholder inerte. El health check en sí sigue siendo estático.
- Ruff con `line-length = 100` (frente al default 88 de ruff/black).
- `uv.lock` se commitea (práctica estándar de uv para aplicaciones, no para librerías).

Plan completo de implementación en `C:\Users\Alan\.claude\plans\perfecto-pues-tocar-a-subfase-reflective-stream.md`.

## Progreso

### Paso 1 — Inicializar el proyecto (completado)

- `uv init --package --name compass --python 3.13 backend`.
- Limpieza del boilerplate generado: quitado `[project.scripts]` de `pyproject.toml`, quitado `main()` de `src/compass/__init__.py` (queda solo un docstring), descripción del proyecto actualizada en `pyproject.toml`, nombre de autor corregido (el generado por uv tomó el nombre de usuario de Windows en vez del real).
- Commit: `chore(backend): initialize Python project with uv`.

### Paso 2 — Dependencias de producción y dev (completado)

- Producción: `uv add fastapi "uvicorn[standard]" pydantic-settings` → fastapi 0.141.1, uvicorn 0.52.1, pydantic-settings 2.15.0 (y transitivas: pydantic 2.13.4, starlette, anyio, etc.).
- Dev: `uv add --dev ruff pytest httpx` → ruff 0.16.2, pytest 9.1.1, httpx 0.28.1. `httpx` es necesario porque `TestClient` de FastAPI/Starlette lo requiere y no viene arrastrado por `fastapi` solo.
- `uv` creó el entorno virtual en `backend/.venv` y generó `backend/uv.lock` (se commitea, ver plan).

### Paso 3 — Módulos de la app (completado)

- `api/routes/health.py` — `APIRouter` con `GET /health` → `{"status": "ok"}`.
- `api/router.py` — agregador único (`api_router`) que incluye `health.router`. Los endpoints futuros (1.10 → `tenders.py`) se registran aquí sin tocar `main.py`.
- `core/config.py` — `Settings(BaseSettings)` con `app_env`/`log_level`, más `get_settings()` cacheado con `@lru_cache`.
- `main.py` — patrón application factory (`create_app()`), llama a `get_settings()` para fallar rápido si `.env` está mal formado, incluye `api_router`. Expone `app` a nivel de módulo como punto de entrada ASGI para Uvicorn.
- Todavía sin probar en caliente — se verifica en el paso de verificación final (tests + servidor).

### Paso 4 — Configuración de ruff y pytest (completado)

- `[tool.ruff]`: `line-length = 100`, `target-version = "py313"`.
- `[tool.ruff.lint]`: `select = [E, W, F, I, UP, B, C4, SIM]` — errores/estilo básico, imports ordenados, sintaxis moderna, bugs comunes, comprensiones y simplificaciones.
- `[tool.ruff.lint.isort]`: `known-first-party = ["compass"]` para separar imports propios de terceros.
- `[tool.ruff.format]`: `quote-style = "double"`.
- `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `addopts = "-ra"`.
- Verificado: `uv run ruff check .` y `uv run ruff format --check .` pasan sin avisos sobre el código existente (paso 3).

### Paso 5 — Tests reales (completado)

- `tests/conftest.py` — fixture `client` (`TestClient(app)`), disponible automáticamente en todos los tests del directorio sin import explícito.
- `tests/test_health.py` — `test_health_check_returns_ok`, verifica `status_code == 200` y el cuerpo exacto `{"status": "ok"}`.
- **Desviación del plan**: al ejecutar `uv run pytest -v` apareció `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead`. Investigado (no era territorio conocido — Starlette 1.6.0 y este aviso son posteriores al conocimiento del asistente): `httpx` lleva sin release desde 2024 y está de facto sin mantenimiento; Pydantic ha creado `httpx2` como sucesor mantenido, y Starlette ya lo prefiere en `TestClient`. Cambiado `httpx` → `httpx2` en las dependencias de dev (`uv remove --dev httpx && uv add --dev httpx2`) antes de seguir, para no arrastrar una dependencia ya abandonada desde el primer commit del proyecto. Verificado: test sigue en verde, sin avisos.
- Fuentes: [Starlette issue #2524](https://github.com/Kludex/starlette/issues/2524), [Starlette PR #3291](https://github.com/Kludex/starlette/pull/3291), [Starlette TestClient docs](https://starlette.dev/testclient/).

### Paso 6 — `.env.example` (completado)

- `backend/.env.example` con `APP_ENV=development` y `LOG_LEVEL=INFO`, mapeando 1:1 con los campos de `core/config.py`. Nada de `DATABASE_URL`/`REDIS_URL` todavía (1.2/1.9).
- Verificado que la excepción `!.env.example` del `.gitignore` raíz funciona: el archivo aparece como untracked, no como ignorado.

### Paso 7 — `.gitignore` raíz (completado, adelantado)

Adelantado respecto al orden del plan: al ejecutar los tests se generó `backend/tests/__pycache__/*.pyc`, y como el `.gitignore` raíz todavía no tenía reglas de Python, un commit anterior (`test(backend): ...`) los trackeó por error. Corregido: añadido el bloque `# Python / uv (backend/)` al final de `.gitignore` (`__pycache__/`, `*.py[cod]`, `.venv/`, `.ruff_cache/`, `.pytest_cache/`, `.mypy_cache/`, `*.egg-info/`, `.coverage`, `htmlcov/`) y destrackeados los `.pyc` con `git rm -r --cached`. El bloque dotenv existente (líneas 68-71) ya cubría `backend/.env`/`backend/.env.example` sin cambios — los patrones sin `/` inicial aplican a cualquier profundidad.

### Paso 8 — `CLAUDE.md` (pendiente)

### Paso 9 — Verificación final (pendiente)
