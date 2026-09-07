# Subfase 2.1 — Perfil de proveedor

## Plan acordado

Del desglose de la Fase 2 (`docs/phases/phase2/phase2.md`): nuevo dominio `providers/`, mismo patrón que `tenders/` (modelo SQLAlchemy, schema Pydantic, repositorio, migración), sin lógica de matching todavía y sin endpoints HTTP -- eso queda para subfases posteriores.

### Decisiones tomadas en la conversación de planificación

- **Un único proveedor, sin FK de "usuario".** Coherente con "multi-tenant fuera de v1" del documento de diseño. Si algún día hace falta más de uno, se añade la FK entonces.
- **Sin endpoints de escritura en esta subfase.** Solo modelo + repositorio + seed. El CRUD del perfil llega más adelante (posiblemente junto con el frontend, Fase 5).
- **Campos**: `description` (texto libre, es lo que la Etapa 2 del embudo cruzará contra el objeto del contrato), `cpv_codes`, `min_budget`/`max_budget`, `annual_revenue`, `certifications` (texto libre, no catálogo cerrado -- `Tender` no extrae certificaciones requeridas de CODICE todavía, así que no hay nada estructurado contra lo que cruzar).
- **Seed con un perfil de ejemplo realista, no con placeholders arbitrarios.** Compass v1 no está atado a una empresa real concreta -- a diferencia de las licitaciones (reales, de PLACSP), no hay una empresa detrás cuyo perfil cargar. La alternativa a "datos reales" no es "cualquier dato de relleno": es un perfil coherente y verificado contra el propio corpus (los CPV elegidos son los más frecuentes entre las tenders ya ingeridas, no CPV inventados que no aparecerían nunca en un match), para que el embudo de matching de las subfases siguientes tenga contra qué comparar de verdad.

### Criterios de aceptación

1. `uv run alembic upgrade head` aplica la migración de `providers` sin drift (`alembic check` limpio).
2. `uv run pytest` cubre `ProviderSchema`, el modelo (round-trip) y el repositorio (`get_provider`/`upsert_provider`, incluida la idempotencia del upsert), y sigue en verde junto con los tests existentes.
3. `uv run mypy` y `uv run ruff check`/`format --check` limpios.
4. Un perfil de proveedor completo queda cargado en la base de datos (verificable con una consulta directa), con CPV verificados contra el corpus real -- no un dato de prueba vacío ni placeholders sin sentido.

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

### Paso 4 — Seed con un perfil de ejemplo verificado contra el corpus real (completado)

- **CPV elegidos por evidencia, no por intuición**: consulta directa (`unnest(cpv_codes)` + `count(*)` sobre las 3.583 filas reales) para encontrar los códigos más frecuentes del corpus, en vez de adivinar cuáles "deberían" aparecer. De esos, se seleccionaron cinco coherentes con un perfil de desarrollo/mantenimiento web (`72200000` programación y consultoría -- 272 apariciones; `72262000` desarrollo de software -- 132; `72267000` mantenimiento de software -- 396; `72400000` servicios de Internet -- 118; `72600000` soporte y consultoría informática -- 154).
- **Rango de importe por percentiles reales**, no un número redondo sin más: `percentile_cont` sobre `budget_with_vat` (mediana 128.400 €, p25 42.349 €, p75 482.378 €) para fijar `min_budget=10.000`/`max_budget=200.000` -- un rango de pyme pequeña, por debajo de la mediana, que sí va a producir matches reales en el embudo de las subfases siguientes.
- **Descripción**: reutiliza literalmente el ejemplo que ya usa el propio documento de diseño (`docs/compass-radar-licitaciones.md`, sección "Etapa 2") para el caso de recuperación híbrida, manteniendo la narrativa del proyecto coherente entre el diseño y los datos de desarrollo.
- **`annual_revenue=450.000 €`**: orden de magnitud coherente con poder optar a contratos de hasta 200.000 € (los pliegos suelen exigir solvencia económica en torno a 1-2x el importe del contrato). **`certifications=["ENS", "ISO 27001"]`**.
- Nuevo `providers/seed.py` -- mismo patrón que `historical_loader.py`: `_main()` bajo `if __name__ == "__main__":`, invocable con `uv run python -m compass.providers.seed`, con el mismo fix de `logging.basicConfig` y `SelectorEventLoop` en Windows. El perfil vive como constante de módulo (`PROFILE`), no en un archivo de configuración aparte -- es un script de un solo uso, no una pieza reutilizable.
- Ejecutado contra Postgres real y verificado con una consulta directa: la fila `id="default"` existe con los cinco CPV, el rango de importe, la facturación y las dos certificaciones, tal como se sembraron.
- `ruff check`/`format --check` y `mypy` limpios (52 archivos).

Subfase 2.1 completada. Los cuatro criterios de aceptación se cumplen: migración sin drift, suite en 81 passed, herramientas de calidad limpias, y perfil de proveedor cargado y verificado contra el corpus real.
