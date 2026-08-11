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
- `tenders/models.py`: modelo `Tender(Base)` con las 19 columnas (17 de negocio + `created_at`/`updated_at` técnicos). Decisiones: importes como `Decimal` (nunca `float` para dinero — precisión en coma flotante), `cpv_codes` como `ARRAY(String)`, enums con `native_enum=False` (implementados como `VARCHAR`+`CHECK`, más fáciles de evolucionar que un `ENUM` nativo de Postgres), `created_at`/`updated_at` con `server_default=func.now()`/`onupdate=func.now()`.
- `tenders/schemas.py`: `TenderSchema` (Pydantic), refleja los 17 campos de negocio — deliberadamente **sin** `created_at`/`updated_at` (son de la capa de persistencia, no del CODICE). `ConfigDict(from_attributes=True)` permite construirlo desde un objeto ORM `Tender`, no solo desde un dict.
- Verificado: `Base.metadata.tables` registra `tenders` con las 19 columnas esperadas; los tres módulos importan sin errores.

### Paso 4 — Alembic init (plantilla async) + `env.py` conectado a `Settings`/`Base` (pendiente)

### Paso 5 — Primera migración autogenerada (crear tabla `tenders`) + aplicarla (pendiente)

### Paso 6 — Tests: persistencia real (insert/query async) + validación del schema Pydantic (pendiente)

### Paso 7 — Verificación final: Docker arriba, migración aplicada, tests en verde, Docker abajo (pendiente)
