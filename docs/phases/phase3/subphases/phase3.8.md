# Subfase 3.8 — Orquestación bajo demanda: tarea Celery + endpoint

## Plan acordado

Del desglose de la Fase 3 (`docs/phases/phase3/phase3.md`): tarea Celery bajo demanda (no programada por `beat`, a diferencia de `daily_ingestion`/`generate_embeddings`), con caché por hash y lock de Redis contra doble encolado -- mismo patrón que `daily_ingestion_task`. Endpoint para disparar/consultar el análisis desde la ficha de la licitación.

### Lo que faltaba antes de escribir código

`TenderAnalysis` (3.1) no tenía columna para `citation_faithfulness` -- el grafo (3.6) la calcula en su nodo `verify`, pero nadie la persistía. Migración nueva antes de tocar la tarea.

### Decisiones tomadas en la conversación de planificación

- **Lock de Redis por `expediente`, no por `pdf_hash`.** El hash no se conoce hasta descargar el PDF, así que no puede ser la clave del lock que protege contra doble encolado -- el lock existe precisamente para decidir *si merece la pena* iniciar esa descarga.
- **Caché por hash, con una descarga aceptada dos veces en el caso de fallo de caché.** La tarea descarga y hashea el PCAP una vez para consultar `get_analysis(pdf_hash)`. Si hay caché (`COMPLETED`/`NOT_ANALYZABLE`), termina ahí sin llamar a OpenRouter -- el "segundo usuario gratis" del documento de diseño. Si no, llama a `analyze_pliego` (3.6), que descarga el mismo PCAP una segunda vez dentro de su propio nodo `fetch`. Descarga duplicada solo en el caso real de fallo de caché, aceptada a propósito: la alternativa era tocar el grafo de 3.6 (ya cerrado y testeado) para que aceptase un `fetch` ya hecho, a cambio de ahorrar una descarga que es barata frente a la llamada al LLM que sí evita.
- **`FAILED` se reintenta; `NOT_ANALYZABLE` no.** Coherente con el propio docstring de `AnalysisStatus` desde 3.1 ("`NOT_ANALYZABLE` is terminal, not a failure to retry"). Un `FAILED` (fallo transitorio de red o del LLM) recibe un intento real la próxima vez que alguien dispare el análisis; un documento escaneado no.
- **El veredicto se calcula en el momento de la lectura, nunca se guarda** -- ya fijado por el modelo de datos desde 3.1 y confirmado en 3.7. El endpoint `GET` es el único sitio que llama a `compute_verdict`.
- **`analyze_tender` (la orquestación real) es una función pública, separada de `analyze_tender_task` (el envoltorio de Celery/lock)** -- mismo split que `run_daily_ingestion`/`daily_ingestion_task` y `generate_embeddings`/`generate_embeddings_task`. Permite testear la lógica de caché contra Postgres real sin pasar por Celery ni por un motor de tareas.

### Criterios de aceptación

1. `POST /tenders/{expediente}/analyze` -- 404 si el tender no existe, 422 si no tiene `pcap_url`, 202 y tarea encolada en caso contrario.
2. `GET /tenders/{expediente}/analysis` -- 404 si nunca se ha analizado.
3. Un análisis `COMPLETED` devuelve el veredicto calculado en vivo contra el perfil de proveedor real.
4. Un análisis no completado (`PENDING`, etc.) nunca lleva veredicto.
5. Un `COMPLETED` sin perfil de proveedor sembrado da 404 (mismo criterio que `GET /matches`).
6. La tarea reutiliza un análisis `COMPLETED`/`NOT_ANALYZABLE` cacheado sin llamar a OpenRouter; reintenta uno `FAILED`.
7. El lock de Redis por expediente evita una segunda ejecución concurrente y se libera tanto en éxito como en fallo.
8. Tests, `ruff`, `mypy` limpios.

## Progreso

### Paso 1 — Migración: `citation_faithfulness`

`op.add_column("tender_analyses", sa.Column("citation_faithfulness", sa.Float(), nullable=True))`, generada con `alembic revision --autogenerate` y revisada a mano (docstrings reales en `upgrade()`/`downgrade()`, no el placeholder autogenerado). Aplicada con `alembic upgrade head`.

### Paso 2 — `analysis/tasks.py`

`analyze_tender(session, client, expediente)`: busca el tender, corta si no existe o no tiene `pcap_url`; descarga y hashea el PCAP; consulta `get_analysis` por ese hash; si el estado está en `{COMPLETED, NOT_ANALYZABLE}` termina ahí; si no, crea/reutiliza la fila, la marca `IN_PROGRESS` (commit intermedio, visible a quien haga *polling*), llama a `analyze_pliego` (3.6) y persiste el resultado completo -- `status`, `extraction` (serializado con `model_dump(mode="json")`), `citation_faithfulness`, `error_message`.

`analyze_tender_task`: envoltorio de Celery, lock de Redis (`analysis:{expediente}:lock`, no bloqueante, 900s de timeout), mismo patrón try/finally de liberación que `daily_ingestion_task`. Registrada en `celery_app.py` (`include`) **sin** entrada en `beat_schedule` -- bajo demanda, nunca programada.

`analysis/repository.py`: nueva `get_latest_analysis_for_tender(session, expediente)`, usa el índice `ix_tender_analyses_expediente` que ya existía desde 3.1 sin usarse.

### Paso 3 — Endpoints

`api/routes/analysis.py`, montado bajo `/tenders/{expediente}`:
- `POST /analyze` -- valida tender/`pcap_url` de forma síncrona (404/422) antes de encolar; todo lo demás (caché, lock, reintento) es decisión de la propia tarea, no duplicada aquí.
- `GET /analysis` -- 404 si nunca se analizó; si `COMPLETED`, calcula `compute_verdict` (3.7) contra el `Provider` actual, 404 si no hay perfil sembrado.

`analysis/schemas.py`: `TenderAnalysisResultSchema`, construido a mano en el endpoint (no vía `from_attributes`, porque `verdict` no es un atributo de la fila).

### Paso 4 — El bug real de los tests: commits reales escapando al rollback de los fixtures

Los primeros tests de `analyze_tender` usaban el fixture `db_session` (que hace rollback al final) sin más cuidado -- y fallaron con `UniqueViolation` en `pdf_hash`, entre tests que a primera vista no debían chocar. La causa: `analyze_tender` hace *commit* de verdad dentro de sí misma (necesario para que `IN_PROGRESS` sea visible a quien haga *polling*), así que el rollback del fixture no deshace nada una vez que se llega a esa rama. El primer test dejó una fila real en la base de datos de desarrollo; el siguiente test, que reutiliza el mismo hash de `sample_pliego.pdf`, chocó contra ella. Mismo patrón exacto que `test_tenders_endpoint.py` ya documentaba para `GET /tenders` (commits reales por el *event loop* del `TestClient`) y que `test_tasks.py` de `matching` ya aplicaba para `generate_embeddings`: los tests que llegan a un commit real necesitan `try/finally` con limpieza explícita, no basta con confiar en el rollback del fixture.

### Paso 5 — Tests

`tests/analysis/test_analysis_tasks.py` (11 casos): `analyze_tender` contra Postgres real con `httpx2.MockTransport` (mismo patrón que `test_graph.py`) -- tender inexistente, sin `pcap_url`, cache-miss end-to-end, cache-hit `COMPLETED` sin llamar a OpenRouter, cache-hit `NOT_ANALYZABLE`, reintento de un `FAILED`; y `analyze_tender_task` con la orquestación mockeada -- *wiring* de éxito, lock ocupado, liberación del lock en éxito y en fallo.

`tests/api/test_analysis_endpoints.py` (7 casos): sobre la app real (`TestClient`), con commits reales y limpieza explícita -- mismo patrón que `test_tenders_endpoint.py`. Cubre los 5 primeros criterios de aceptación uno a uno, incluyendo el veredicto real calculado contra el perfil de proveedor sembrado de verdad en la base de datos de desarrollo (certificaciones `['ENS', 'ISO 27001']`).

Suite completa: **188 passed** (170 previos + 18 nuevos). `ruff check`/`format --check`/`mypy` (proyecto completo, sin argumentos) sin avisos. Verificado además que `app.openapi()` genera el esquema sin errores con los dos endpoints nuevos registrados.

Subfase 3.8 completada. Los ocho criterios de aceptación se cumplen.
