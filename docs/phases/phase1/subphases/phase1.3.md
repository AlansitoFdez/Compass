# Subfase 1.3 — Modelo de datos

## Plan acordado

Del desglose de la Fase 1 (`docs/phases/phase1/phase1.md`): modelo SQLAlchemy + schema Pydantic para los 12-15 campos CODICE del expediente, primera migración Alembic. Tests.

### Mapeo de campos (sección 3.3 del documento de diseño)

| Campo (diseño) | Columna | Tipo |
|---|---|---|
| Número de expediente | `expediente` | `str`, **primary key** |
| Órgano de contratación | `contracting_body` | `str` |
| Objeto del contrato | `title` | `str` |
| Códigos CPV | `cpv_codes` | `list[str]` (Postgres `ARRAY`) |
| Importe con IVA | `budget_with_vat` | `Numeric`, nullable |
| Importe sin IVA | `budget_without_vat` | `Numeric`, nullable |
| Valor estimado | `estimated_value` | `Numeric`, nullable |
| Tipo de contrato | `contract_type` | Enum (servicios/suministros/obras) |
| Procedimiento | `procedure_type` | Enum (abierto/simplificado/negociado...) |
| Estado | `status` | Enum (anuncio previo/en plazo/.../resuelta) |
| Fecha límite presentación | `submission_deadline` | `datetime`, nullable |
| Lugar de ejecución | `location` | `str`, nullable |
| URL del PCAP | `pcap_url` | `str`, nullable |
| URL del PPT | `ppt_url` | `str`, nullable |
| URL en PLACSP | `platform_url` | `str`, nullable |
| Fecha de publicación | `published_at` | `datetime` |
| Fecha última actualización (fuente) | `updated_at_source` | `datetime` |

Más `created_at`/`updated_at` técnicos (default del servidor), para depurar la ingesta — distintos de las fechas que vienen de PLACSP.

### Decisiones tomadas en la conversación de planificación

- **`expediente` como primary key directamente**, no un ID surrogate: el documento de diseño ya lo trata como la clave de negocio natural ("upsert por identificador de expediente"); a esta escala no hay ventaja real en un ID sustituto.
- **Enums para `contract_type`, `procedure_type`, `status`**: el documento de diseño ya enumera los valores posibles de cada uno.
- **`cpv_codes` como array de Postgres**, no una tabla relacionada: suficiente para lo que necesita el filtro; una tabla M:N sería sobre-ingeniería ahora.
- **La extensión `pgvector` no se activa todavía**: no hay columnas de embeddings en esta subfase (Fase 2). Activarla ahora sería el scope creep que el documento de diseño marca como riesgo.
- **SQLAlchemy en modo asíncrono** (`create_async_engine` + sesiones async). Razón: encaja con el modelo de FastAPI (no bloquea el event loop), y ya lo anticipamos en la 1.1 al decir que `pytest-asyncio` se añadiría "cuando aparezca el primer test async de verdad, probablemente con sesiones de BD" — es ahora. `psycopg` (ya instalado en 1.2) sirve tal cual para async, sin driver nuevo — verificado: [SQLAlchemy asyncio docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html).
- **Paquete de dominio `compass/tenders/`** (`models.py` + `schemas.py`), separado de `api/` (capa HTTP) y `core/` (infraestructura transversal) — mismo criterio que ya separó `api/` de `core/` en la 1.1. Cuando lleguen matching, agente de pliegos, etc., cada dominio tendrá su propio paquete.
- **Detalle técnico a tener en cuenta al implementar**: `DATABASE_URL` en `.env` es una URL "postgresql://" plana (la que ya entiende `psycopg.connect()` directamente, usada en el test de conectividad de la 1.2). SQLAlchemy necesita el dialecto explícito `postgresql+psycopg://` para usar psycopg3 (si no, asume psycopg2, que no tenemos instalado). Para no romper el test de la 1.2 ni ensuciar `.env`, esa transformación de prefijo se hace dentro de `core/db.py`, no en la variable de entorno.

## Progreso

### Paso 1 — Dependencias: `sqlalchemy`, `alembic` (completado)

- `uv add sqlalchemy alembic` → SQLAlchemy 2.0.51, Alembic 1.19.1. Dependencias de producción (las migraciones se aplican en cualquier entorno, no son solo una herramienta de dev).
- `greenlet` se instaló como transitiva de SQLAlchemy — es lo que usa por debajo su extensión asyncio.

### Paso 2 — `core/db.py`: engine async, sessionmaker, Base declarativa (completado)

- `Base(DeclarativeBase)` — clase base para los modelos ORM; su `metadata` es lo que Alembic leerá para `autogenerate` (paso 5).
- `_async_database_url()` — transforma `postgresql://` (formato plano de `.env`, el que ya usa `psycopg.connect()` en el test de la 1.2) a `postgresql+psycopg://` (dialecto explícito que SQLAlchemy necesita para usar psycopg3 en vez de asumir psycopg2, que no está instalado). La transformación vive aquí, no en la variable de entorno, para no romper el test de conectividad de la 1.2.
- `engine` — `create_async_engine`, construido a partir de `get_settings()` (fail-fast si `.env` no tiene `DATABASE_URL`, mismo patrón que `main.py`).
- `async_session_factory` — `async_sessionmaker` con `expire_on_commit=False` (recomendación oficial de SQLAlchemy para uso async: evita que acceder a atributos tras un `commit` dispare una recarga perezosa, que no funciona bien en async sin manejo especial).
- Sin dependencia de FastAPI (`get_db()`) todavía — no hay endpoint que la consuma hasta la 1.10.
- Verificado: `uv run python -c "from compass.core.db import engine..."` construye el engine correctamente, con el dialecto `postgresql+psycopg` y el puerto `5433` de `.env`. La URL impresa enmascara la contraseña automáticamente.

### Paso 3 — `tenders/models.py` y `tenders/schemas.py` (completado)

- `tenders/enums.py`: `ContractType` y `TenderStatus` (`StrEnum`, conjuntos cerrados según el documento de diseño). **`procedure_type` se deja como `str` plano, no Enum**: el documento lo lista con "..." (conjunto abierto — la ley de contratos públicos define más procedimientos de los nombrados); forzar un Enum rompería la ingesta real (1.6) en cuanto el feed traiga un procedimiento legítimo no anticipado.
- `tenders/models.py`: modelo `Tender(Base)` con las 19 columnas (17 de negocio + `created_at`/`updated_at` técnicos). Decisiones: importes como `Decimal` (nunca `float` para dinero — precisión en coma flotante), `cpv_codes` como `ARRAY(String)`, enums con `native_enum=False` (implementados como `VARCHAR`, más fáciles de evolucionar que un `ENUM` nativo de Postgres), `created_at`/`updated_at` con `server_default=func.now()`/`onupdate=func.now()`.
  - **Corrección (2026-08-17, subfase 1.6):** aquí dijimos "VARCHAR+CHECK" — es incorrecto. `native_enum=False` en SQLAlchemy 2.0 no crea ningún `CHECK` constraint (`create_constraint=False` por defecto, verificado directamente); solo crea un `VARCHAR` dimensionado al valor más largo del enum. Confirmado contra la base de datos real: la tabla no tenía ningún `CHECK`. Ver `phase1.6.md` para el detalle completo.
- `tenders/schemas.py`: `TenderSchema` (Pydantic), refleja los 17 campos de negocio — deliberadamente **sin** `created_at`/`updated_at` (son de la capa de persistencia, no del CODICE). `ConfigDict(from_attributes=True)` permite construirlo desde un objeto ORM `Tender`, no solo desde un dict.
- Verificado: `Base.metadata.tables` registra `tenders` con las 19 columnas esperadas; los tres módulos importan sin errores.

### Paso 4 — Alembic init (plantilla async) + `env.py` conectado a `Settings`/`Base` (completado)

- `uv run alembic init -t async alembic` (desde `backend/`) → `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/`. Commiteado en bruto antes de tocarlo, igual que con `uv init` en la 1.1.
- `env.py`: `target_metadata` apuntado a `Base.metadata` (antes `None`), importando `compass.tenders.models` para que `Tender` se registre. La construcción del engine (`async_engine_from_config` leyendo `alembic.ini`) se sustituyó por reutilizar directamente `compass.core.db.engine` — una sola fuente de verdad para la conexión, en vez de mantener la URL sincronizada en dos sitios.
- `alembic.ini`: comentada la línea `sqlalchemy.url = driver://user:pass@localhost/dbname` (placeholder sin usar ya, para no confundir a quien lea el archivo pensando que falta configurar algo real ahí).
- Verificado con `ruff check`/`format --check` (sin avisos). La verificación de extremo a extremo (que de verdad conecte y funcione) se deja para el paso 5, cuando haga falta Docker arriba.

### Paso 5 — Primera migración autogenerada (crear tabla `tenders`) + aplicarla (completado)

- **Bug real #1 — Windows/asyncio**: `uv run alembic revision --autogenerate` falló con `psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop' to run in async mode`. Es un problema conocido de psycopg en modo async sobre Windows (necesita un event loop basado en selector; `ProactorEventLoop` es el por defecto de asyncio en Windows). **No afecta a producción** (Linux no tiene este problema). Arreglado acotado a `alembic/env.py::run_migrations_online()`: en Windows, `asyncio.run(..., loop_factory=asyncio.SelectorEventLoop)`; en cualquier otro sistema, sin cambios. No se tocó `main.py` — la app todavía no abre ninguna conexión async real (ningún endpoint toca la BD), así que no está roto ahí todavía; habrá que aplicar el mismo tipo de fix cuando sí lo esté (probablemente 1.10).
- **Bug real #2 — enum names vs. values**: revisando la migración autogenerada antes de aplicarla (nunca hay que fiarse a ciegas de `autogenerate`), `sa.Enum('SERVICES', 'SUPPLIES', 'WORKS', ...)` usaba los **nombres** de los miembros de los enums de Python, no los **valores** (`'services'`, `'supplies'`, `'works'`) — comportamiento por defecto de SQLAlchemy al mapear un `Enum` de Python. Funcionaría igual a través del ORM, pero cualquiera mirando la tabla con `psql` directamente vería mayúsculas inconsistentes con el resto del proyecto. Arreglado con `values_callable=lambda enum_cls: [e.value for e in enum_cls]` en ambas columnas Enum de `models.py`, antes de aplicar nada (sin coste, no había datos todavía).
- **Mejora de tooling**: activados los `post_write_hooks` de `alembic.ini` (comentados por defecto) para que `ruff check --fix` + `ruff format` corran automáticamente sobre cada migración generada — el autogenerate de Alembic no sigue nuestro estilo (comillas simples, `Union` en vez de `X | Y`, líneas largas) y así no hay que arreglarlo a mano cada vez.
- `uv run alembic revision --autogenerate -m "create tenders table"` (con Docker arriba) → detecta correctamente la tabla nueva, genera la migración ya limpia gracias a los hooks.
- `uv run alembic upgrade head` → aplicada sin errores.
- Verificado contra la base de datos real (`docker exec compass-db-1 psql -U compass -d compass -c "\d tenders"`): las 19 columnas presentes, tipos correctos, `PRIMARY KEY` en `expediente`.

### Paso 6 — Tests: persistencia real (insert/query async) + validación del schema Pydantic (completado)

- `uv add --dev pytest-asyncio` + `asyncio_mode = "auto"` en `pyproject.toml` (evita el decorador `@pytest.mark.asyncio` en cada test).
- `tests/conftest.py`: fixture `db_session` — sesión real, transaccional: el test hace `flush()` (no `commit()`) y la fixture hace `rollback()` al terminar, así ningún test deja datos permanentes ni colisiona con expedientes repetidos entre ejecuciones.
- **Bug real #3 — mismo problema de Windows, sitio distinto**: al ejecutar el primer test async de verdad, aparece otra vez `Psycopg cannot use the 'ProactorEventLoop'` — esta vez no en Alembic, sino en el propio event loop que crea `pytest-asyncio` para correr los tests. Arreglado en `conftest.py` con `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())` a nivel de todo el proceso de test (acotado a Windows). Confirma que este fix habrá que aplicarlo en un tercer sitio más adelante: cuando la app real (`uvicorn`) toque la BD de forma async por primera vez (probablemente 1.10).
- `tests/test_tender_model.py`: `test_tender_persists_and_round_trips` — inserta un `Tender`, lo relee con `select()`, comprueba que los enums vuelven como el tipo Python correcto (no como string), y que `TenderSchema.model_validate(fetched)` (el puente `from_attributes`) funciona contra un objeto real.
- `tests/test_tender_schema.py`: `test_tender_schema_accepts_valid_data` y `test_tender_schema_rejects_invalid_status` (Pydantic, sin base de datos).
- Verificado manualmente que el rollback funciona: `docker exec compass-db-1 psql ... "SELECT count(*) FROM tenders;"` → `0` filas tras correr los tests.
- 6 tests en verde: health check, conectividad (1.2), persistencia y schema (1.3).

### Paso 7 — Verificación final: Docker arriba, migración aplicada, tests en verde, Docker abajo (completado)

Verificación desde cero, no solo con lo que ya había: `docker compose down -v` (borra también el volumen — solo tenía datos de prueba vacíos, nada real) → `docker compose up -d --wait` (contenedores y volumen nuevos) → confirmado `\dt` sin tablas → `uv run alembic upgrade head` aplica la migración sobre la base de datos vacía → `ruff check`/`format --check` sin avisos → `uv run pytest -v` → **6 passed**. `docker compose down` para cerrar.

Esto prueba que alguien que clone el repo hoy puede reproducir todo el pipeline (infra + esquema + tests) desde cero, no solo que "funcionaba en mi entorno ya levantado".

Subfase 1.3 completada. Tres bugs reales encontrados y documentados por el camino: incompatibilidad de psycopg async con `ProactorEventLoop` en Windows (Alembic y pytest-asyncio, dos sitios distintos — pendiente un tercero cuando la app toque la BD en un endpoint real), y enums de SQLAlchemy guardando `.name` en vez de `.value` por defecto.
