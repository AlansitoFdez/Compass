# Subfase 2.2 — Etapa 1 del embudo: filtros duros

## Plan acordado

Del desglose de la Fase 2 (`docs/phases/phase2/phase2.md`): la primera etapa del embudo de matching -- CPV, importe, estado, ubicación, todo en SQL, sin ranking ni IA -- instrumentada para poder medir cuántas licitaciones sobreviven a cada escalón (dato real para el README de cierre de fase, 2.7).

### Decisión tomada al planificar

- **El perfil de proveedor (2.1) no tenía ningún campo de ubicación**, pero el documento de diseño lista "provincia o ámbito" junto a CPV e importe como uno de los tres filtros duros. Se añade `locations: list[str] | None` a `Provider` en esta subfase (migración aditiva, sin romper el perfil ya sembrado): `None` significa sin restricción geográfica, no "no aplica ninguna licitación".

### Criterios de aceptación

1. `uv run alembic upgrade head` aplica la migración de `locations` sin drift.
2. `uv run pytest` cubre el filtro de estado, el solape de CPV, el rango de importe (incluida la exclusión conservadora de licitaciones sin importe declarado cuando el proveedor sí fija un rango), el filtro de ubicación (incluida su ausencia = sin restricción), y la propiedad de que cada escalón del embudo es acumulativo y no creciente -- y sigue en verde junto con los tests existentes.
3. `uv run mypy` y `uv run ruff check`/`format --check` limpios.
4. Ejecutado de extremo a extremo contra Postgres real con el perfil de proveedor ya sembrado (no solo con datos sintéticos de test), con un número real de cuántas licitaciones sobreviven a cada escalón.

## Progreso

### Paso 1 — Campo de ubicación en el perfil de proveedor

- `providers/models.py`/`schemas.py`: nuevo campo `locations: list[str] | None`, mismo patrón `ARRAY(String)` que `cpv_codes`/`certifications`. Migración `332a9cf3f9c4_add_locations_to_providers.py`, aditiva y aplicada contra Postgres real -- la fila `id="default"` ya sembrada en la 2.1 queda con `locations=NULL` (sin restricción), consistente con el default de `ProviderSchema`.

### Paso 2 — Dominio `matching/`: filtros duros e instrumentación

- Nuevo paquete `matching/repository.py`, con dos funciones que comparten la misma construcción de filtros (`_build_filters`), mismo patrón que `tenders/repository.list_tenders`:
  - `list_matches(session, provider, limit, offset)` -- página de licitaciones que superan todos los filtros duros del perfil, ordenadas por `published_at` descendente.
  - `funnel_stage_counts(session, provider)` -- cuenta acumulativa de supervivientes tras cada escalón (`total` → `after_status` → `after_cpv` → `after_budget` → `after_location`), aplicando los mismos filtros uno a uno en el mismo orden fijo.
- **Filtros construidos, en orden**:
  - **Estado**: `status == open_for_submission` ("en plazo") -- fijo, no depende del perfil.
  - **CPV**: `cpv_codes && provider.cpv_codes` (operador de solape de Postgres) -- cualquier código compartido basta, no hace falta que coincidan todos. Reutiliza el índice GIN de la 1.11 (`ix_tenders_cpv_codes_gin`), que sí acelera `&&` a diferencia del `LIKE` sobre `unnest()` que usa el filtro por prefijo de `tenders/repository.py`.
  - **Importe**: `min_budget`/`max_budget` del proveedor, cada uno opcional e independiente. **Decisión conservadora**: una licitación sin `budget_with_vat` declarado se excluye en cuanto el proveedor fija cualquier extremo del rango -- no se puede confirmar que esté dentro, así que no entra gratis. Se apoya en que comparar `NULL` con `>=`/`<=` en SQL da `NULL`, que `WHERE` trata como "no cumple", sin necesitar ninguna condición extra.
  - **Ubicación**: `location IN provider.locations`, solo si el proveedor restringe zona (misma razón conservadora que el importe: una licitación sin `location` no entra si el proveedor sí restringe). `None`/lista vacía en el proveedor = sin filtro.
- **Hallazgo real durante los tests, no antes**: el primer intento de test de `funnel_stage_counts` afirmaba un número absoluto (`after_status == 2`) y falló con `510 == 2` -- `after_status` cuenta sobre toda la tabla por diseño (es el propósito de instrumentar el embudo: el ritmo de supervivencia real del corpus completo), y Docker ya persiste miles de licitaciones reales, la mayoría en plazo. El test se corrigió para comparar el delta que provocan sus propias filas (antes/después de insertarlas), en vez de un valor absoluto -- la misma necesidad de aislamiento que ya resolvían los CPV sintéticos (`LIST_TEST_CPV`/`MATCH_CPV`) en los tests de `tenders`, aplicada aquí a un agregado que por diseño no se puede aislar por CPV.
- 7 tests en `tests/matching/test_matching_repository.py`: exclusión por estado, solape de CPV, rango de importe, exclusión conservadora de importe ausente, filtro de ubicación, ausencia de restricción de ubicación, y la propiedad acumulativa/no creciente del embudo completo.
- Suite completa: **88 passed** (81 previos + 7 nuevos). `mypy` limpio en 55 archivos (un `ColumnElement[bool]` anotado explícitamente para evitar que el tipo `Any` de `ARRAY.Comparator.overlap()`, no completamente tipado aguas arriba, escape de la función). `ruff check`/`format --check` limpios. `alembic check` sin drift.

### Paso 3 — Verificación de extremo a extremo contra datos reales

Ejecutado contra Postgres real, con el perfil de proveedor sembrado en la 2.1 (sin restricción de ubicación):

```
FunnelStageCounts(total=3583, after_status=508, after_cpv=131, after_budget=61, after_location=61)
```

**El primer número real del embudo de la Fase 2**: de 3.583 licitaciones del vertical, 508 siguen en plazo, 131 comparten algún CPV con el perfil, y 61 caen además dentro del rango de importe (10.000 €-200.000 €) -- las mismas 61 llegan a `list_matches`, verificado devolviendo licitaciones reales con su expediente, título, importe y CPV.

Subfase 2.2 completada. Los cuatro criterios de aceptación se cumplen.
