# Subfase 1.10 — Endpoint FastAPI mínimo

## Plan acordado

Del desglose de la Fase 1 (`docs/phases/phase1/phase1.md`): `GET /tenders` con filtros básicos (CPV, estado, importe, provincia), paginado, probado vía Swagger UI. Tests.

### Decisiones tomadas en la conversación de planificación

- **Reutilizar `TenderSchema`** (1.3) como respuesta, no un schema nuevo — ya se dejó preparado a propósito para esto (`ConfigDict(from_attributes=True)`), anticipado explícitamente en el log de la 1.3.
- **`get_db()` nuevo**: la dependencia de FastAPI para inyectar la sesión en endpoints, pendiente desde la 1.3 ("la añadiremos cuando exista un consumidor real, eso es la 1.10").
- **Filtro de CPV: coincidencia exacta, no por prefijo** — revisado durante la planificación de implementación: un filtro por prefijo exigiría una subconsulta con `unnest()` sobre el array de Postgres (sin operador directo simple), demasiada complejidad para un endpoint "mínimo". Coincidencia exacta vía el operador nativo `@>` de Postgres para arrays (`cpv_codes.contains([...])` en SQLAlchemy, sin subconsultas) sigue siendo útil y mucho más simple.
- **`min_budget`/`max_budget`** (rango), no un importe exacto — el dinero no se filtra por igualdad.
- Todos los filtros opcionales, combinados con lógica **AND**.
- **Paginación clásica `limit`/`offset`**, con respuesta en un sobre (`TenderListResponse`: `items`, `total`, `limit`, `offset`) en vez de una lista suelta — así quien consuma el endpoint sabe cuántos resultados hay en total, no solo los de la página actual. `limit` por defecto 20, máximo 100.

## Progreso

### Paso 1 — `get_db()` en `core/db.py` + `TenderListResponse` (completado)

- `core/db.py`: `get_db() -> AsyncIterator[AsyncSession]` — dependencia de FastAPI vía `Depends(get_db)`, un `async_session_factory()` por request (`async with`, cierre automático al terminar el request).
- `api/routes/tenders.py` (nuevo): `TenderListResponse` (sobre de paginación: `items: list[TenderSchema]`, `total`, `limit`, `offset`) y las constantes `DEFAULT_LIMIT = 20` / `MAX_LIMIT = 100`. Router (`APIRouter(prefix="/tenders", ...)`) creado ya con el prefijo, el endpoint en sí llega en el paso 2.
- Verificado: `ruff check`/`format --check` sin avisos, import manual de ambas piezas correcto.

### Paso 2 — `GET /tenders`: filtros + paginación (completado)

- `tenders/repository.py`: nueva `list_tenders()` — construye la lista de filtros (`cpv` vía `cpv_codes.contains([cpv])`, el operador `@>` nativo de Postgres; `status` por igualdad; `min_budget`/`max_budget` como rango sobre `budget_with_vat` — decisión tomada aquí, no en la planificación: es el importe de licitación con IVA, el más habitual como "importe" en contratación pública; `location` por igualdad exacta, ya que el campo se rellena desde `cac:RealizedLocation/cbc:CountrySubentity`, un valor de lista de códigos, no texto libre). Todos combinados con `.where(*filters)` (AND implícito de SQLAlchemy). Dos consultas: un `COUNT(*)` para `total` y un `SELECT` paginado con `ORDER BY published_at DESC` — el orden explícito es imprescindible, sin él `limit`/`offset` no garantiza páginas estables entre llamadas.
- `api/routes/tenders.py`: `GET /tenders` (ruta `""` bajo el `prefix="/tenders"` del router, para que resuelva a `/tenders` y no `/tenders/`) — parámetros de query opcionales para cada filtro, `limit`/`offset` con `Query(..., ge=, le=)` para los límites acordados (1-100, por defecto 20). Inyecta la sesión vía `Depends(get_db)` (paso 1), delega en `list_tenders()`, envuelve el resultado en `TenderListResponse`.
- **Ajuste de configuración real, no anticipado**: `ruff` marcó `Depends(get_db)` con B008 ("no llamar funciones en valores por defecto") — a diferencia de `Query(...)`, que ruff sí exime por defecto, `Depends` no está en su lista de exenciones automáticas. Añadido `[tool.ruff.lint.flake8-bugbear] extend-immutable-calls = ["fastapi.Depends"]` en `pyproject.toml`: es justo el patrón que exige la inyección de dependencias de FastAPI, no un descuido.
- Verificado (sin servidor real todavía, eso es el paso 5): `ruff check`/`format --check` sin avisos, import manual de `router`/`list_tenders`, `[r.path for r in router.routes]` → `['/tenders']`, confirmando que el prefijo se resolvió como se esperaba.

### Paso 3 — Registrar el router en `api/router.py` (completado)

- `api/router.py`: `api_router.include_router(tenders.router)`, mismo patrón que `health.router` — `main.py` no se toca, tal como se diseñó desde la 1.1.
- Verificado vía el esquema OpenAPI de la app real (`create_app().openapi()["paths"]`), no vía `app.routes` directamente: en esta versión de FastAPI, `app.routes` no aplana los routers incluidos (aparecen envueltos en un `_IncludedRouter` interno) — un detalle de representación interna, no un fallo de registro. `openapi()["paths"]` → `['/health', '/tenders']`, confirmando ambos endpoints activos en la app real.
- `ruff check`/`format --check` sin avisos.

### Paso 4 — Tests (completado)

- `tests/test_tender_repository.py`: 6 tests nuevos para `list_tenders()` (cpv exacto, status, rango de importe, location, combinación AND, orden `published_at desc` + paginación `limit`/`offset`). Todos usan un CPV sintético fuera de la división 72 (`LIST_TEST_CPV = "99999999"`) como filtro de aislamiento — Docker persiste ~1.200+ licitaciones reales en el mismo Postgres que usan los tests (1.9), así que un test sin ese filtro contaría también esas filas reales en `total`.
- `tests/test_tenders_endpoint.py` (nuevo): 4 tests sobre la app real vía `TestClient` — forma del sobre (`items`/`total`/`limit`/`offset`), un filtro aplicado de extremo a extremo (basta uno: la lógica exhaustiva de filtros ya está cubierta a nivel de repositorio), y las dos validaciones de límites (`limit > 100`, `offset < 0` → 422). Fixture nueva `db_client`: sobrescribe `get_db` (`app.dependency_overrides`) para que el endpoint use el mismo `db_session` del test — así los datos con solo `flush()` (sin `commit()`) son visibles en la petición HTTP, y el rollback de `db_session` limpia todo al terminar.
- **Bug real encontrado al correr contra Postgres de verdad, no un fallo de test**: `Tender.cpv_codes` estaba declarado con el `ARRAY` genérico de `sqlalchemy` (no el específico de PostgreSQL) — ese `ARRAY` base no implementa `.contains()`, solo lanza `NotImplementedError`; el operador `@>` nativo solo está disponible en `sqlalchemy.dialects.postgresql.ARRAY`. Fix en `tenders/models.py`: importar `ARRAY` desde `sqlalchemy.dialects.postgresql` en vez de `sqlalchemy`. Sin migración: ambas clases compilan a la misma columna Postgres (`text[]`), la diferencia es solo qué operadores expone el lado Python — confirmado con `alembic check` → "No new upgrade operations detected."
- Suite completa: **56 passed** (46 previos + 10 nuevos). `ruff check`/`format --check` sin avisos.

### Paso 5 — Verificación final: servidor real, Swagger UI, ruff, pytest (pendiente)
