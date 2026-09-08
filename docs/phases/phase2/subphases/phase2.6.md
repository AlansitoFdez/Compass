# Subfase 2.6 — Fusión y endpoint de matches

## Plan acordado

Del desglose de la Fase 2 (`docs/phases/phase2/phase2.md`): Reciprocal Rank Fusion sobre los dos rankings de la Etapa 2 (`lexical_matches` de la 2.3, `vector_matches` de la 2.5), y un endpoint que devuelve los matches con su motivo de encaje.

### Decisiones de alcance tomadas al planificar

- **`RRF_K = 60`**, la constante estándar del paper original de Cormack et al. (2009) -- sin motivo para desviarse.
- **`CANDIDATE_POOL = 50`** candidatos por recuperador antes de fusionar -- margen suficiente para que RRF tenga con qué trabajar incluso si uno de los dos recuperadores falla (p. ej. el léxico sin ningún término compartido), sin pedir de más contra un corpus de unos pocos miles de filas.
- **"Motivo de encaje" mínimo**: qué recuperador(es) trajeron el match, con sus puntuaciones crudas (`lexical_rank`/`lexical_score`, `vector_rank`/`vector_distance`) -- ya disponibles en `lexical_matches`/`vector_matches`, cero cómputo nuevo. Una versión enriquecida (qué términos léxicos concretos coincidieron) queda fuera de esta subfase.
- **Sin `provider_id` en el endpoint.** Un único perfil (ver `providers.models.Provider`): `GET /matches` siempre rankea contra el perfil sembrado, sin parámetro de proveedor.
- **`404`, no un crash, si el perfil no está sembrado.** Primer sitio del proyecto donde ese caso se maneja de verdad en la capa API.
- **`limit` sin `offset`.** El propósito del endpoint es "aquí tienes tus mejores matches", no paginar un corpus grande -- coherente con que ya se piden como mucho `2 * CANDIDATE_POOL` candidatos únicos antes de fusionar.

### Criterios de aceptación

1. `GET /matches` devuelve resultados reales, ordenados por `rrf_score` descendente, contra el perfil sembrado.
2. Un tender que aparece en ambos rankings puntúa por encima de uno que solo aparece en uno -- verificado con un caso real, no solo con la fórmula.
3. `404` si el perfil no está sembrado, sin excepción sin manejar.
4. `uv run pytest`, `ruff check --fix`, `ruff format`, `mypy` limpios.

## Progreso

### Paso 1 — Fusión RRF

`matching/fusion.py`: `fused_matches()` pide `CANDIDATE_POOL=50` candidatos a `lexical_matches` y a `vector_matches` (secuencial, no concurrente -- comparten la misma `AsyncSession`), acumula `1/(RRF_K + rank)` por cada ranking en que aparece cada `expediente`, y devuelve el top `limit` por `rrf_score` descendente. `MatchResult` guarda también el rango/puntuación crudos de cada recuperador -- `None` en los que no lo trajeron -- que es exactamente el "motivo de encaje" acordado.

### Paso 2 — Endpoint `GET /matches`

`matching/schemas.py` (`MatchSchema`, `MatchListResponse`) y `api/routes/matches.py`: sin `provider_id` (perfil único), `404` explícito si `get_provider` devuelve `None`, `limit` sin `offset`. Registrado en `api/router.py`.

### Paso 3 — Verificación real, no solo tests

111 → 118 tests (los nuevos: `test_fusion.py` con un caso construido para ser determinista -- un tender nunca embebido, así que `vector_matches` no puede traerlo por diseño de la 2.5, garantiza el caso "solo léxico" sin depender de la suerte del corpus real; `test_matches_endpoint.py` con el perfil y corpus reales para la forma del envelope, y el `404` mockeando `get_provider` en vez de borrar el perfil real -- es el único de toda la fase, borrar y luego tener que restaurar el singleton real es un riesgo innecesario para un caso que se puede aislar con un mock).

**Hallazgo real al probar contra el servidor vivo, no solo contra `TestClient`**: `uv run uvicorn compass.main:app --port 8010` (sin `--reload`) devuelve `500` en *cualquier* endpoint que toque la base -- incluido `/tenders`, que ya existía antes de esta subfase. La causa: en Windows, `ProactorEventLoop` (la política de asyncio por defecto) es incompatible con el modo async de psycopg, y solo Alembic, Celery y el `conftest.py` de los tests fijan explícitamente `WindowsSelectorEventLoopPolicy` -- el proceso de `uvicorn` sin más nunca la fija. No es un bug de esta subfase: es una condición previa del arranque en Windows que nadie había disparado a mano contra el servidor vivo hasta ahora. **El comando documentado en `CLAUDE.md` (`--reload`) no lo sufre** -- verificado contra `/tenders` y `/matches` en vivo, ambos devuelven resultados reales y con sentido (el portal Drupal de la Universidad de Jaén primero, con rango 1 léxico y 3 vectorial; Hipatia segundo, con rango 1 vectorial y 7 léxico -- RRF premiando el acuerdo entre ambos rankings, justo el efecto buscado).

Subfase 2.6 completada. Los cuatro criterios de aceptación se cumplen.
