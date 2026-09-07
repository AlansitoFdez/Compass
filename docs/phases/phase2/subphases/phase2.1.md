# Subfase 2.1 — Perfil de proveedor

## Plan acordado

Del desglose de la Fase 2 (`docs/phases/phase2/phase2.md`): nuevo dominio `providers/`, mismo patrón que `tenders/` (modelo SQLAlchemy, schema Pydantic, repositorio, migración), sin lógica de matching todavía y sin endpoints HTTP -- eso queda para subfases posteriores.

### Decisiones tomadas en la conversación de planificación

- **Un único proveedor, sin FK de "usuario".** Coherente con "multi-tenant fuera de v1" del documento de diseño. Si algún día hace falta más de uno, se añade la FK entonces.
- **Sin endpoints de escritura en esta subfase.** Solo modelo + repositorio + seed. El CRUD del perfil llega más adelante (posiblemente junto con el frontend, Fase 5).
- **Campos**: `description` (texto libre, es lo que la Etapa 2 del embudo cruzará contra el objeto del contrato), `cpv_codes`, `min_budget`/`max_budget`, `annual_revenue`, `certifications` (texto libre, no catálogo cerrado -- `Tender` no extrae certificaciones requeridas de CODICE todavía, así que no hay nada estructurado contra lo que cruzar).
- **Seed con datos reales**, no ficticios -- mismo criterio que la carga histórica de la 1.8 ("no seeds, no usuario de prueba").

### Criterios de aceptación

1. `uv run alembic upgrade head` aplica la migración de `providers` sin drift (`alembic check` limpio).
2. `uv run pytest` cubre `ProviderSchema`, el modelo (round-trip) y el repositorio (`get_provider`/`upsert_provider`, incluida la idempotencia del upsert), y sigue en verde junto con los tests existentes.
3. `uv run mypy` y `uv run ruff check`/`format --check` limpios.
4. El perfil real de Alan queda cargado en la base de datos (verificable con una consulta directa), no un dato de prueba.

## Progreso

### Paso 1 — Dominio: modelo, schema, repositorio (completado)

- `providers/models.py` -- `Provider`, clave primaria `id: str` fija en `PROVIDER_ID = "default"` (no un id autoincremental): la fila única del proveedor, sin tabla de usuarios todavía. `repository.py` es lo único que hace cumplir el "una sola fila" -- expone `get_provider()`/`upsert_provider()`, nunca un `create()`.
- `providers/schemas.py` -- `ProviderSchema`, deliberadamente sin `id`: es un detalle de persistencia de `Provider`, no un hecho del dominio. `from_attributes=True` (mismo patrón que `TenderSchema`) permite construirlo directo desde una fila ORM.
- `providers/repository.py` -- `get_provider()` (lee la fila fija, `None` si no está sembrada) y `upsert_provider()` (mismo patrón `pg_insert().on_conflict_do_update()` que `upsert_tender`, con `clock_timestamp()` para `updated_at` por el mismo motivo: `now()` queda congelado al inicio de la transacción).

### Paso 2 — Migración (completado)

- `alembic/env.py` importa `compass.providers.models` (aliasado `providers_models` para no chocar con el `models` ya importado de `tenders`), registrándolo en `Base.metadata` para que `--autogenerate` lo vea.
- Migración `408a569ec4ff_create_providers_table.py` generada contra Postgres real, aplicada con `alembic upgrade head`. Docstrings de `upgrade()`/`downgrade()` reescritos (no la plantilla genérica), mismo criterio que la 1.12.
- `alembic check` -- sin drift.

### Paso 3 — Tests (completado)

- `tests/providers/test_provider_schema.py` -- 2 tests: datos mínimos válidos (defaults correctos) y perfil completo (los campos opcionales sí viajan cuando se dan).
- `tests/providers/test_provider_model.py` -- 1 test de round-trip ORM↔Postgres↔Pydantic, mismo patrón que `test_tender_model.py`.
- `tests/providers/test_provider_repository.py` -- 5 tests: `get_provider` sin sembrar devuelve `None`; `upsert_provider` crea la fila; procesado dos veces sigue siendo una fila (la regla "nunca INSERT a secas" de `CLAUDE.md`, aplicada a la fila única); actualiza campos preservando `created_at` y avanzando `updated_at`; los campos opcionales persisten con un valor real.
- Suite completa: **81 passed** (73 previos + 8 nuevos). `uv run mypy` limpio en 51 archivos. `ruff check`/`format --check` limpios.

### Paso 4 — Seed con el perfil real (pendiente)

Bloqueado en datos que solo Alan tiene: descripción del servicio, CPV de interés, rango de importe objetivo, facturación anual aproximada, certificaciones. No se fabrica un perfil de relleno -- va contra la filosofía de "datos reales, no seeds" que ya rigió la carga histórica de la 1.8.
