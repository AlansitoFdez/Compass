# Subfase 2.7 — Revisión completa de la fase

## Plan acordado

Del desglose de la Fase 2 (`docs/phases/phase2/phase2.md`): repaso exhaustivo de todo lo construido en 2.1-2.6, buscando errores que se hayan podido escapar durante el desarrollo incremental. Tests adicionales o ajustados donde haga falta. Métricas reales del embudo para el README -- mismo patrón que la 1.11.

### Criterios de aceptación

1. Cada hallazgo real se aborda: decisión → implementación → tests → verificación contra infraestructura real, no solo lectura.
2. Números reales del embudo (Etapa 1 → Etapa 2 léxico/vectorial → fusión) documentados en el README, contra el perfil sembrado y el corpus real.
3. `uv run pytest`, `ruff check --fix`, `ruff format`, `mypy` limpios sobre todo el código de la fase.
4. `alembic check` sin drift entre modelos y migraciones.

## Progreso

Lectura completa de `matching/`, `providers/`, y lo tocado en `tenders/`/`api/` durante 2.1-2.6, con verificación empírica de cada hipótesis -- mismo criterio que la 1.11.

### Hallazgo real 1 -- `upsert_tender` no invalidaba el embedding cuando el título cambiaba (bug, corregido)

- **El caso roto**: una licitación republicada con el `title` editado (PLACSP republica cualquier modificación, no solo importe/estado/plazo -- ya había un test propio, `test_upsert_tender_updates_fields_and_preserves_created_at` desde la 1.x, que cambia el título en una republicación) actualizaba `title_tsv` automáticamente (columna generada por Postgres) pero dejaba `title_embedding` intacto, calculado sobre el texto viejo. Sin nada que lo distinga de un embedding fresco y correcto -- rompe justo la garantía que `vector_matches` (2.5) da por sentada: `title_embedding IS NOT NULL` significa "tenemos una opinión", pero aquí la opinión sería sobre un título que ya no existe.
- `tenders/repository.py::upsert_tender`: `update_values["title_embedding"]` ahora es un `CASE` de SQL -- `NULL` si `Tender.title != stmt.excluded.title`, si no, se conserva el valor existente (`Tender.title_embedding`). Comparación en el propio `UPDATE`, no una lectura previa: no hace falta una consulta extra ni tocar `TenderSchema`.
- Al resetear a `NULL`, `matching.tasks.generate_embeddings_task` (2.5, ya corre cada 15 min por `celery beat`) recoge la fila sola en su próximo ciclo -- no hace falta embeber en línea dentro del propio upsert.
- Tests nuevos en `test_tender_repository.py`: el embedding se invalida cuando el título cambia; se conserva cuando la republicación solo toca otro campo (estado, en el caso del test).
- Verificado: los dos tests nuevos pasan contra Postgres real; los 13 tests de `test_tender_repository.py` (incluidos los ya existentes que cambian el título) siguen en verde.

### Hallazgo real 2 -- Colisión de CPV de aislamiento entre dos ficheros de test (patrón, corregido)

- `test_matching_repository.py::MATCH_CPV` y `test_vector.py::VECTOR_CPV` usaban el mismo valor (`"99777777"`) para "aislarse del corpus real" -- pero no se aíslan el uno del otro. Hoy no falla (ninguno de los dos hace `commit()` real, y pytest corre secuencial con rollback por test), pero es la misma clase de fragilidad latente que la 1.11 catalogó como patrón mal (hallazgo 6, sesión compartida entre event loops): funciona hoy por cómo está montado el runner, no porque el aislamiento sea real.
- `VECTOR_CPV` renombrado a `"99555555"`, verificado sin colisión contra el resto de CPVs sintéticos del proyecto (`grep` de todos los literales `"99*"` en `tests/`).
- Suite completa reejecutada tras el cambio: sigue en verde, sin que ningún test dependiera del valor concreto.

### Hallazgo real 3 -- El README real nunca se escribió (criterio de aceptación de la propia fase, no cumplido hasta ahora)

- El documento de diseño pide explícitamente "documenta el embudo con números reales en el README" -- tanto en la 1.11 como en el desglose de esta misma fase (`phase2.md`). Pero `README.md` en la raíz del repo era solo `# Compass`, un título sin contenido. Los números reales sí existían -- en `phase1.11.md` y en los `phaseN.X.md` de esta fase -- pero no en el sitio que de verdad ve alguien que abre el repo.
- Números medidos de nuevo, en vivo, contra el corpus y el perfil reales (no reciclados de memoria de subfases anteriores): `funnel_stage_counts` para la Etapa 1 (3.583 → 508 en plazo → 131 + CPV → 61 + presupuesto → 61 + ubicación), conteo directo de la coincidencia léxica (`@@`) dentro de esos 61 supervivientes (28), conteo de embebidos listos (61, el 100% -- backfill de la 2.5 sigue completo), y `fused_matches` con `limit=100` para ver el total único tras RRF (52: 26 en ambos rankings, 2 solo léxico, 24 solo vectorial).
- **La cifra que de verdad justifica el diseño híbrido, con datos reales delante**: 24 de las 52 licitaciones finales (46%) las trajo *solo* el recuperador vectorial -- se habrían perdido con búsqueda puramente léxica. No es la teoría del documento de diseño, es el resultado real contra el perfil sembrado.
- `README.md` reescrito: encuadre del producto (una frase, tomada del documento de diseño), estado real de las fases, las dos tablas de embudo (Fase 1, Fase 2) con estos números, stack, y los comandos mínimos para arrancar en local -- `CLAUDE.md` no sirve para esto porque está en `.gitignore`, nadie más lo ve.
- Verificado: `total: 3583, leftover TEST- rows: 0` contra la base real antes de medir -- ninguna fila sintética de los tests contaminaba los números.

### Hallazgo documentado, no corregido aquí -- codificar embeddings bloquea el event loop

- `matching.embeddings.embed_texts()` (y `vector_matches`, que la llama en cada petición para embeber `provider.description` al vuelo) es una función síncrona invocada sin `await` desde una ruta `async` de FastAPI. `SentenceTransformer.encode()` es CPU-bound -- mientras corre, bloquea el único hilo del event loop entero, no solo la petición que lo pidió.
- **No se arregla en esta subfase**: a la escala actual (un proveedor, sin usuarios concurrentes, un embed de una sola frase por petición) es irrelevante en la práctica -- el mismo criterio que la 1.11 aplicó al límite conocido del filtro CPV por prefijo (paso 5), documentado en vez de resuelto de inmediato. La solución real (`asyncio.to_thread()` o un executor dedicado) es una decisión de la capa de despliegue, más propia de una fase posterior si el patrón de uso cambia -- anotado para entonces.

### Verificación de infraestructura

- `uv run alembic check` → sin drift entre modelos y migraciones.
- Cadena de migraciones inspeccionada de extremo a extremo (`revision`/`down_revision` de las 7 versiones): lineal, sin huecos ni ramas.
- Suite completa: **120 passed** (118 previos + 2 nuevos del hallazgo 1). `ruff check`/`format --check`/`mypy` sin avisos.

Subfase 2.7 completada -- y con ella, la Fase 2 entera. Los cuatro criterios de aceptación se cumplen: los hallazgos reales se abordaron con el mismo ritmo que el resto de la fase (decisión → implementación → tests → verificación contra infraestructura real), el README lleva los números reales del embudo, la suite y el linter están limpios, y no hay drift de esquema.
