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

### Paso 2 — `GET /tenders`: filtros + paginación (pendiente)

### Paso 3 — Registrar el router en `api/router.py` (pendiente)

### Paso 4 — Tests (pendiente)

### Paso 5 — Verificación final: servidor real, Swagger UI, ruff, pytest (pendiente)
