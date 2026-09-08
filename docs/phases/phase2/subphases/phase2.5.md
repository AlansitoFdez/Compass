# Subfase 2.5 — Recuperador vectorial

## Plan acordado

Del desglose de la Fase 2 (`docs/phases/phase2/phase2.md`): una columna `Vector(n)` con la dimensión decidida en la 2.4, una tarea Celery de generación de embeddings, y un backfill del corpus existente.

### Decisiones de alcance tomadas al planificar

- **`title_embedding Vector(768)`, nullable.** A diferencia de `title_tsv` (2.3), no puede ser una columna generada -- calcular un embedding exige invocar el modelo, no solo SQL. `NULL` significa "aún no embebido", el criterio que usa la tarea de backfill para saber qué falta.
- **Índice HNSW sobre `vector_cosine_ops`, no IVFFlat.** Sin fase de entrenamiento (a diferencia de IVFFlat, que exige fijar `lists` en función del número de filas) y con mejor recall/latencia por defecto para un corpus de unos pocos miles de filas como el actual.
- **Tarea Celery periódica (`celery beat`, cada 15 minutos), desacoplada de `daily_ingestion_task`.** Un fallo en una no bloquea la otra. La misma tarea, en un único run, drena todo el backlog pendiente en lotes -- así sirve igual para el goteo diario de tenders nuevos que para el backfill inicial del corpus completo, sin necesitar un script aparte.
- **El recuperador (`vector_matches`) se construye en esta misma subfase, no se deja para la 2.6.** Es la contraparte simétrica de `lexical_matches` (2.3): sin él, la fusión RRF de la 2.6 no tendría un segundo ranking que fusionar.
- **Dependencia nueva: `pgvector` (el paquete Python, distinto del `sentence-transformers` de la 2.4).** Da el tipo `Vector` para SQLAlchemy y los operadores de distancia (`cosine_distance()`, que compila a `<=>`). Avisada antes de añadirla.

### Criterios de aceptación

1. `uv run alembic upgrade head` deja la extensión `vector` activada, la columna `title_embedding` y el índice HNSW creados.
2. La tarea de embeddings, ejecutada contra el corpus real, deja 0 filas con `title_embedding IS NULL`.
3. `vector_matches` devuelve resultados no vacíos y en orden de distancia coseno creciente contra el perfil real, respetando los mismos filtros duros que `lexical_matches`.
4. `uv run pytest`, `ruff check --fix`, `ruff format`, `mypy` limpios sobre todo el código nuevo.

## Progreso

### Paso 1 — Columna, extensión e índice

`pgvector` (el paquete Python, distinto de `sentence-transformers`) añadido como dependencia -- da el tipo `Vector` para SQLAlchemy y `cosine_distance()`, que compila al operador `<=>`.

Migración `57bad4ff539e`: `CREATE EXTENSION IF NOT EXISTS vector`, columna `title_embedding Vector(768)` nullable en `tenders`, e índice HNSW (`m=16, ef_construction=64`, `vector_cosine_ops`).

**Un rodeo real durante la migración, no cosmético**: `compass.core.db` registra el códec del tipo `vector` en cada conexión nueva (`register_vector_async`, vía `pgvector.psycopg`) -- sin él, cualquier consulta que toque `title_embedding` falla con `UnknownTypeError`. Pero ese mismo motor es el que Alembic reutiliza para *ejecutar* la propia migración que crea la extensión: la primera conexión, contra una base sin `vector` todavía, intentaba registrar un tipo que aún no existe y tumbaba la conexión antes de poder crear la extensión. Arreglado con un `try/except psycopg.ProgrammingError` alrededor del registro -- una base sin la extensión simplemente no registra el tipo (y no lo necesita, todavía no hay columna vectorial que consultar); en cuanto la migración corre, la siguiente conexión sí lo registra.

### Paso 2 — Módulo de embeddings y tarea de backfill

`matching/embeddings.py`: `embed_texts()`, singleton perezoso de `SentenceTransformer` (mismo modelo que decidió la 2.4), `normalize_embeddings=True` para que la distancia coseno de pgvector y un producto escalar simple coincidan.

`matching/tasks.py`: `generate_embeddings()` (async, testeable directamente) hace el trabajo real -- selecciona lotes de 200 tenders con `title_embedding IS NULL`, los embebe, comitea, y repite hasta vaciar lo pendiente en una sola llamada. `generate_embeddings_task()` es el envoltorio Celery (mismo puente sync/async que `daily_ingestion_task`). Registrada en `celery beat` cada 15 minutos, desacoplada de la ingesta diaria -- un fallo en una no bloquea la otra, y el mismo mecanismo sirve igual para el goteo diario de tenders nuevos que para vaciar de una vez el backlog inicial de todo el corpus.

### Paso 3 — Recuperador (`vector_matches`)

`matching/vector.py`: simétrico a `lexical_matches` (2.3) -- reutiliza `build_filters` de la Etapa 1, embebe `provider.description` al vuelo, y ordena por `title_embedding.cosine_distance(...)`. Excluye explícitamente filas sin embedding todavía (`IS NOT NULL`) en vez de dejarlas caer al final del ranking -- una fila sin embedder no es "la peor coincidencia", es "todavía no evaluable".

### Paso 4 — Backfill real y verificación

Ejecutado contra el corpus real (no simulado): **3.583 de 3.583** tenders embebidos en una sola llamada a `generate_embeddings_task()`, confirmado después con `title_embedding IS NULL` -> 0 filas.

Sanity check contra el perfil real con `vector_matches` -- mismo top-5 que había encontrado el script de la 2.4 (Hipatia, bolsa de empleo de veterinarios, mantenimiento de aplicaciones, hosting web), esta vez desde la columna indexada real, no desde una comparación ad-hoc en memoria.

**Hallazgo real con `EXPLAIN ANALYZE` (vía `psql`, el MCP de Postgres no conectó en esta sesión)**: el índice HNSW existe y está bien formado (`ix_tenders_title_embedding_hnsw`, confirmado con `\d tenders`), pero el planificador **no lo usa todavía** -- ni filtrando por `status` (508 filas) ni sin filtrar (3.583 filas), ambas consultas resuelven con `Seq Scan + Sort` en unos pocos milisegundos. No es un fallo: con un corpus de miles de filas, un escaneo secuencial completo es más barato que los saltos de acceso aleatorio de un índice ANN -- el cruce de coste solo llega a una escala mayor (decenas o cientos de miles de filas). El índice existe y queda listo para cuando el corpus crezca lo suficiente para que el planificador lo prefiera; hoy no hace falta.

Subfase 2.5 completada. Los cuatro criterios de aceptación se cumplen: migración aplicada limpia, backlog real vaciado a 0, `vector_matches` devuelve resultados razonables en orden de distancia creciente respetando los filtros duros, y `pytest`/`ruff`/`mypy` limpios.
