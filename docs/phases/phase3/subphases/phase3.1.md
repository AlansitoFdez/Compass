# Subfase 3.1 — Dominio `analysis/` y tabla de caché por hash de documento

## Plan acordado

Del desglose de la Fase 3 (`docs/phases/phase3/phase3.md`): dominio nuevo `analysis/`, con modelo SQLAlchemy, schema, repositorio y migración para la tabla de caché por hash de documento. Sin PDF ni LLM todavía -- solo la forma de la tabla.

### Decisiones tomadas en la conversación de planificación

- **`AnalysisStatus` completo desde ya** (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `NOT_ANALYZABLE`), aunque las subfases 3.2-3.8 sean las que de verdad muevan una fila entre estados -- para no necesitar otra migración por esto más adelante. `NOT_ANALYZABLE` es terminal (pliego escaneado sin capa de texto), no un fallo a reintentar.
- **`pdf_hash` como clave primaria, `expediente` como FK indexada -- no al revés.** La extracción se cachea por el contenido del documento (barato de repetir la búsqueda, caro de recalcular), no por licitación: dos expedientes con el mismo PDF byte a byte comparten análisis. Primera FK real del esquema -- hasta ahora `tenders`/`providers` son tablas independientes.
- **Sin columna de veredicto**, ajuste sobre el boceto de `phase3.md` (que mencionaba "columnas vacías para... veredicto"): la decisión de arquitectura de la fase dice que el veredicto se calcula "en el momento de lectura", contra el `Provider` que esté vigente entonces -- guardarlo obligaría a invalidarlo en cada edición del perfil, para una comparación barata (Python puro, sin LLM) que no tiene nada que cachear todavía.
- **`repository.py` solo con las primitivas de creación/lectura**, sin lógica de "¿ya existe, o hay que crearlo?" -- ese comportamiento de caché real necesita un hash de verdad que consultar, y eso llega con la 3.2.

### Criterios de aceptación

1. `uv run alembic upgrade head` crea `tender_analyses` con su FK a `tenders.expediente`.
2. Una fila se puede crear, leer, y falla claramente al duplicar `pdf_hash`.
3. `uv run pytest`, `ruff check --fix`, `ruff format`, `mypy` limpios.

## Progreso

`analysis/enums.py` (`AnalysisStatus`), `analysis/models.py` (`TenderAnalysis`: `pdf_hash` PK, `expediente` FK+índice, `status`, `extraction` JSONB nullable, `error_message` nullable, timestamps), `analysis/schemas.py` (`TenderAnalysisSchema`), `analysis/repository.py` (`create_analysis`, `get_analysis`) -- mismo patrón por dominio que `providers/` y `tenders/`.

Migración `1545737ea415` generada con `alembic revision --autogenerate` (detectó la tabla y el índice solos, sin ajustes de forma -- solo los docstrings genéricos sustituidos por los que explican el porqué, mismo criterio que las migraciones anteriores) y aplicada contra Postgres real.

Tests: round-trip de persistencia (`test_analysis_model.py`, incluida la conversión de vuelta a `TenderAnalysisSchema`) y del repositorio (`test_analysis_repository.py`: arranca en `PENDING`, `get_analysis` devuelve `None` en un cache-miss real, devuelve la fila en un cache-hit, y un `pdf_hash` duplicado falla con `IntegrityError` en vez de sobrescribir en silencio -- el test que protege la garantía central de la tabla).

Suite completa: **125 passed** (120 previos + 5 nuevos). `ruff check`/`format --check`/`mypy` sin avisos. `alembic check` sin drift.

Subfase 3.1 completada. Los tres criterios de aceptación se cumplen.
