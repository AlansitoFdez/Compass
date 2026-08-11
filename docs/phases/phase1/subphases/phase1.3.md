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

### Paso 2 — `core/db.py`: engine async, sessionmaker, Base declarativa (pendiente)

### Paso 3 — `tenders/models.py` y `tenders/schemas.py` (pendiente)

### Paso 4 — Alembic init (plantilla async) + `env.py` conectado a `Settings`/`Base` (pendiente)

### Paso 5 — Primera migración autogenerada (crear tabla `tenders`) + aplicarla (pendiente)

### Paso 6 — Tests: persistencia real (insert/query async) + validación del schema Pydantic (pendiente)

### Paso 7 — Verificación final: Docker arriba, migración aplicada, tests en verde, Docker abajo (pendiente)
