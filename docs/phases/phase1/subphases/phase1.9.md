# Subfase 1.9 — Celery + Redis

## Plan acordado

Del desglose de la Fase 1 (`docs/phases/phase1/phase1.md`): app de Celery, tarea de ingesta diaria programada vía Celery beat, logging básico de cada corrida. Tests.

### Investigación (verificada, no asumida)

- **Celery 5.6.x** es la rama actual (marzo 2026), sin cambios grandes de API frente a lo ya conocido (`Celery()`, `@app.task`, `beat_schedule` con `crontab`).
- **Problema real de pooling entre event loops**: el `async_session_factory` compartido (1.3) usa el pool de conexiones por defecto de SQLAlchemy, pensado para un único event loop de larga duración (FastAPI). Cada tarea de Celery, al hacer `asyncio.run(...)`, crea un event loop **nuevo** cada vez — una conexión pooleada bajo un event loop es inválida en otro. La práctica recomendada (verificada, no inventada) es un engine aparte con `NullPool` para tareas Celery, aceptable porque el coste de no poolear (un handshake TCP extra) es irrelevante para una tarea que corre una vez al día.
- Fuentes: [Using Async SQLAlchemy Inside Sync Celery Tasks](https://dev.to/kevinnadar22/using-async-sqlalchemy-inside-sync-celery-tasks-3eg4), [SQLAlchemy discussion #9388](https://github.com/sqlalchemy/sqlalchemy/discussions/9388)

### Decisiones tomadas en la conversación de planificación

- **`create_task_engine()` nuevo en `core/db.py`**: engine con `NullPool`, construido bajo demanda dentro de cada ejecución de la tarea — no el `engine`/`async_session_factory` compartido (pensado para FastAPI).
- **Sin *result backend* de Celery, solo *broker*** (Redis para ambos sería redundante aquí): nada recupera el resultado vía Celery `AsyncResult`; el conteo de licitaciones procesadas se registra con `logging` normal.
- **`ingestion/daily_ingestion.py`**: función de orquestación paralela a `load_month()` (1.8), pero iterando `ingest_atom_feed()` (1.5, con checkpoint de reanudación) en vez de un ZIP histórico — misma estructura parsear (1.6) → filtrar vertical (1.4) → upsert (1.7).
- **La tarea de Celery en sí es una función síncrona** (modelo de ejecución de Celery) que hace de puente a nuestro código async vía `asyncio.run(...)` — mismo patrón ya usado en `historical_loader.py::_main()`, incluido el fix de `SelectorEventLoop` en Windows (un cuarto sitio donde hace falta, tras Alembic, pytest-asyncio y el script de carga histórica).

## Progreso

### Paso 1 — `core/celery_app.py`: app de Celery + `create_task_engine()` en `core/db.py` (completado)

- `uv add celery` → 5.6.3, coincide con la versión investigada. No hizo falta el extra `celery[redis]`: `kombu` (mensajería de Celery) usa el paquete `redis` que ya teníamos instalado desde la 1.2.
- `core/db.py`: `create_task_engine()` — engine nuevo con `NullPool` en cada llamada, para usar dentro de un único `asyncio.run()` de una tarea Celery, distinto del `engine`/`async_session_factory` compartido (pensado para el event loop único y de larga duración de FastAPI). Verificado: `isinstance(engine.pool, NullPool)` → `True`.
- `core/celery_app.py`: `Celery("compass", broker=...)`, solo el broker de Redis, sin *result backend*. Alcance mínimo a propósito — la tarea en sí, `include` y `beat_schedule` van en el paso 3, cuando el módulo de la tarea exista de verdad.
- Verificado: `celery_app.main == "compass"`, `celery_app.conf.broker_url` apunta correctamente a `REDIS_URL` de `.env`.

### Paso 2 — `ingestion/daily_ingestion.py`: orquestación de la ingesta diaria (pendiente)

### Paso 3 — La tarea de Celery: puente sync→async, logging, `beat_schedule` (pendiente)

### Paso 4 — Tests (pendiente)

### Paso 5 — Verificación final (pendiente, incluye decidir si se corre una ingesta real contra el feed en vivo)
