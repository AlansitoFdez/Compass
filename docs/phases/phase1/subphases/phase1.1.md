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



### Paso 4 — Configuración de ruff y pytest (pendiente)



### Paso 5 — Tests reales (pendiente)



### Paso 6 — `.env.example` (pendiente)



### Paso 7 — `.gitignore` raíz (pendiente)



### Paso 8 — `CLAUDE.md` (pendiente)



### Paso 9 — Verificación final (pendiente)

