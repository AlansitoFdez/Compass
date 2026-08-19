# Subfase 1.11 — Revisión completa de la fase

## Plan acordado

Del desglose de la Fase 1 (`docs/phases/phase1/phase1.md`): repaso exhaustivo de todo lo construido en 1.1-1.10, buscando errores que se hayan podido escapar durante el desarrollo incremental. Tests adicionales o ajustados donde haga falta. Métricas reales de cierre para el README.

La revisión (lectura completa de todo `backend/src/compass`, con verificación empírica de cada hipótesis — no solo lectura) encontró 4 bugs reales y 4 patrones mal, más un puñado de detalles menores. Se abordan uno a uno, con el mismo ritmo que el resto de la fase: decisión → implementación → tests → commit, verificando cada fix contra infraestructura real antes de darlo por cerrado.

### Hallazgos — bugs reales

1. **La ingesta "diaria" re-recorre el feed entero cada vez que se agota el checkpoint** (`ingestion/feed_reader.py:24-25`). Al vaciar el feed, el checkpoint se borra; la siguiente corrida arranca otra vez en `FEED_URL` y repite el backlog completo. Contradice lo documentado en 1.9 ("coste de arranque en frío, de una sola vez" — no lo es). Los upserts lo hacen idempotente, pero la tarea no hace lo que su nombre promete.

2. **Sin protección contra corridas solapadas de la tarea Celery** (`core/celery_app.py:15-20`). Beat dispara cada día a las 3:00; dado el hallazgo 1, es probable que una corrida siga viva cuando arranca la siguiente. Sin lock ni `soft_time_limit`, dos corridas concurrentes pisan la misma clave de checkpoint en Redis y se saltan páginas sin que nada lo detecte.

3. **`published_at` no es la fecha de publicación, es la de última modificación** (`ingestion/codice_parser.py:95-96`, `tenders/repository.py:19`). Ambos campos (`published_at` y `updated_at_source`) salen de `atom:updated`, y el upsert sobrescribe `published_at` en cada actualización. Verificado contra los 1.216 registros reales: el 100% tiene `published_at == updated_at_source`, y 508 (42%) ya han sido republicados. El endpoint (`GET /tenders`) ordena por este campo — el orden que ve el usuario es "modificado recientemente", no "nuevo".

4. **Un código CPV vacío en el XML tumba la corrida entera** (`ingestion/codice_parser.py:40-42`). `_cpv_codes()` está anotada `-> list[str]` pero devuelve `[None]` si el XML trae `<ItemClassificationCode/>` vacío — confirmado ejecutándolo. `matches_it_vertical()` revienta con `AttributeError` sobre ese `None`. Mismo patrón en `codice_codes.py` (`get_contract_type`/`get_status`/`get_procedure_type_label`): un código nuevo que PLACSP no había usado nunca lanza `ValueError` sin capturar. No hay `try/except` por entrada en ningún punto de la ingesta — una sola licitación rara se lleva por delante las ~800 del día.

### Hallazgos — patrones mal

5. **No hay type checker configurado** (solo `pytest` + `ruff`, sin `mypy`/`pyright`). El código está anotado meticulosamente pero nada valida esas anotaciones — es la causa raíz del hallazgo 4 (`_text()` devuelve `str | None`, se pasa a parámetros `str` sin verificar en media docena de sitios). Es la deuda más barata de pagar y la que más bugs de esta clase evitaría en CI.

6. **Sesión async compartida entre dos event loops en `test_tenders_endpoint.py`** (`db_client` fixture, líneas 44-56). Verificado empíricamente: `TestClient` corre la app en un hilo con su propio event loop, distinto del de `pytest-asyncio`; la fixture inyecta una `AsyncSession` (con conexión psycopg atada al loop de pytest-asyncio) en ese otro loop. Es justo el peligro que `create_task_engine()`/`NullPool` existen para evitar desde la 1.9 — reintroducido sin darme cuenta en un test.

7. **Semántica de CPV incompatible entre ingesta y API**. La ingesta (`tenders/vertical.py`) filtra por prefijo y normaliza el dígito de control (`72212730-0` → `72212730`). La API (`tenders/repository.py:42`, decisión consciente de la planificación de 1.10) filtra por igualdad exacta sin normalizar. Consecuencia: `GET /tenders?cpv=72` — la división que define el producto entero — devuelve cero resultados siempre.

8. **Ningún índice más allá de la clave primaria**. Confirmado con `EXPLAIN ANALYZE`: el filtro por CPV (`cpv_codes @> ...`) y el `ORDER BY published_at` de `GET /tenders` hacen `Seq Scan` de la tabla completa en cada petición. A 1.216 filas es irrelevante (1,7ms); el problema es que la tabla solo crece y no hay ningún índice preparado.

### Detalles menores

- `TenderListResponse` vive en `api/routes/tenders.py`, no en `tenders/schemas.py` junto al resto de schemas.
- La fixture `db_client` hace `app.dependency_overrides.clear()`, que borra todos los overrides, no solo el suyo (hoy es el único, pero es una trampa a futuro).
- `get_last_processed_atom_url()` en realidad guarda la **próxima** URL a procesar (el `next_url` de la última página vista), no la última procesada — el nombre engaña.
- `historical_loader.py::_main()` usa `print()`; el resto del proyecto usa `logging`.

## Progreso

### Paso 1 — (pendiente)
### Paso 2 — (pendiente)
### Paso 3 — (pendiente)
### Paso 4 — (pendiente)
### Paso 5 — (pendiente)
### Paso 6 — (pendiente)
### Paso 7 — (pendiente)
### Paso 8 — (pendiente)
