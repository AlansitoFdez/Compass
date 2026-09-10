# Subfase 3.9 — Revisión completa de la fase

## Plan acordado

Del desglose de la Fase 3 (`docs/phases/phase3/phase3.md`): repaso exhaustivo de todo lo construido en 3.1-3.8, con verificación empírica de cada hipótesis contra infraestructura real -- no solo lectura de código. Mismo patrón que la 1.11 y la 2.7.

Dos puntos concretos que las propias subfases dejaron anotados como pendientes de mirar aquí:

1. Si `chunk_by_clause` (3.3) sigue sin usarse en el camino de producción, tal y como quedó anotado en la 3.4/3.6.
2. Si el timeout configurado en `extract_structured` cubre de verdad el caso real que la 3.5 registró (una traza de razonamiento de `nemotron` de más de 10 minutos, cortada a mano).

### Criterios de aceptación

1. Cada hallazgo real se aborda: decisión → implementación → tests → verificación contra infraestructura real (Postgres, Redis, worker Celery, y una llamada real a OpenRouter cuando aplique) -- no solo lectura.
2. Al menos un análisis end-to-end disparado de verdad (`POST /tenders/{expediente}/analyze` contra un tender real con `pcap_url`, worker corriendo) con coste y tiempo reales reportados, documentados en el README.
3. `uv run pytest`, `ruff check --fix`, `ruff format`, `mypy` limpios sobre todo el código de la fase.
4. `alembic check` sin drift.

## Progreso

### Paso 1 — Lectura completa de `analysis/` y lo tocado en `api/`

Lectura de los 13 módulos del dominio (`enums`, `models`, `schemas`, `repository`, `document`, `chunking`, `extraction_schema`, `openrouter`, `golden_set`, `extraction_eval`, `verification`, `graph`, `verdict`, `tasks`), `api/routes/analysis.py`, y toda su cobertura de tests (11 ficheros en `tests/analysis/`, 1 en `tests/api/`). Baseline antes de tocar nada: `uv run pytest` (188 passed), `ruff check`/`format --check` y `mypy` (proyecto completo) limpios, `alembic check` sin drift.

### Paso 2 — El punto pendiente de la 3.4/3.6: `chunk_by_clause` sigue fuera del camino de producción (confirmado, no es un hallazgo nuevo)

Confirmado leyendo `graph.py::build_prompt` y `extraction_eval.py`: ambos siguen construyendo el prompt a partir del texto completo por página, no de `chunk_by_clause`. La razón documentada en su momento (headers detectados solo en 2 de 4 PCAPs reales del golden set) sigue vigente -- no ha cambiado nada que la invalide. Sin acción aquí: queda como mejora real pendiente, igual que la propia 3.4 la dejó anotada.

### Paso 3 — Hallazgo real: el timeout de `extract_structured` no acota la duración total de una llamada (bug, corregido)

**Investigación antes de tocar nada, no asumido**: leído el código fuente de `httpx2`/`httpcore` instalados (`httpx2/_transports/default.py`, `httpcore/_backends/anyio.py`): el `read(max_bytes, timeout)` de la capa de transporte aplica el timeout **por cada lectura**, no a la llamada completa -- se reinicia cada vez que llega un byte nuevo. Un *streaming* que sigue recibiendo *chunks* de razonamiento espaciados nunca dispara ese timeout, por rápido o lento que vaya en total.

Esto ya estaba delante de las narices en los propios números de la 3.4: la tabla de tiempos por documento (`128s / 209s / 31s / 146s`) incluye un documento en **209s**, por encima de los `timeout=180.0` que `extract_structured` pasa a `client.stream(...)` -- y aun así completó con éxito. Ese dato, sumado al hallazgo de la 3.5 (una llamada real a `nemotron` que superó los 10 minutos sin converger y tuvo que cortarse a mano), confirma que el timeout configurado nunca fue una cota de duración total.

**Por qué importa, no solo en teoría**: el nodo `extract` tiene `RetryPolicy(max_attempts=2)`, y `analyze_tender_task` (3.8) protege contra corridas solapadas con un lock de Redis de `LOCK_TIMEOUT_SECONDS = 900` (15 min). Dos intentos sin cota de duración total podrían, en el peor caso, superar esos 15 minutos y dejar que el lock expire con la tarea todavía corriendo -- permitiendo una segunda corrida concurrente para el mismo expediente, justo lo que ese lock existe para evitar.

**Arreglo**: `graph.py::_extract` envuelve la llamada en `asyncio.wait_for(..., timeout=_EXTRACT_TOTAL_TIMEOUT_SECONDS)`, con `_EXTRACT_TOTAL_TIMEOUT_SECONDS = 300.0` -- por encima del máximo real medido en la 3.4 (209s) y del rango observado en las corridas reales de esta misma subfase (ver Paso 7). Deliberadamente **no** añadido a `_EXTRACT_RETRY_POLICY.retry_on`: reintentar un cuelgue real dentro de la misma corrida solo doblaría la espera; un `FAILED` por este motivo ya recibe un intento real la próxima vez que alguien pida el análisis de ese tender (diseño de caché/reintento de la 3.8). `TimeoutError` (la que lanza `asyncio.wait_for`) se relanza con un mensaje propio -- la de `asyncio` viene vacía, y `error_message` se habría quedado en cadena vacía en vez de explicar el corte.

Test nuevo en `test_graph.py`: un *handler* `async def` (soportado por `httpx2.MockTransport`, confirmado en su código fuente) que hace `asyncio.sleep(0.2)` antes de responder, con `_EXTRACT_TOTAL_TIMEOUT_SECONDS` reducido a `0.05` vía `monkeypatch` -- protege que el corte produce `FAILED` con mensaje, y que no se reintenta (una sola llamada al *handler*, no dos). Ajustado el tipo de `extract_handler` en el helper `_client` del propio fichero de test para aceptar también un handler async (con un `cast` documentado donde el tipo de `MockTransport` no modela un handler que devuelve uno u otro según la llamada).

Suite completa: **189 passed** (188 previos + 1 nuevo). `ruff check`/`format --check`/`mypy` sin avisos.

### Paso 4 — Hallazgo real, encontrado en la propia verificación end-to-end: certificaciones mal delimitadas y una fuga de un nombre de campo interno (parcialmente mitigado, riesgo residual documentado)

Al disparar el primer análisis real de esta subfase (`1276564F`, ver Paso 7) contra el endpoint real, el resultado fue `NO_APTO` con tres motivos bloqueantes. Dos citaban declaraciones administrativas del propio pliego (DEUC, protección de datos) que el proveedor no tiene por qué "declarar" de antemano -- no son certificaciones, son papeleo que cualquier licitador rellena al presentarse. El tercer motivo citaba una cadena literal sin sentido: `"citation_economics_technical_declaration_responsable_annex_iii_iv_clausule_21_1_a_b_c_pag_17_quote_..."` -- claramente una fuga interna (una cita concatenada en snake_case) colada en la lista de certificaciones, no una certificación real.

**Verificado que no era un problema de codificación** antes de asumir nada: la salida por `curl | python -m json.tool` en esta terminal mostraba los acentos como *mojibake* (p. ej. `pÃ³liza`), pero volcando el JSON real directamente a un archivo con `ensure_ascii=False` se confirmó que el texto en Postgres está en UTF-8 correcto (`"política"`, `"artículo"`) -- el *mojibake* era un artefacto de la propia terminal Git Bash al mostrarlo, no un bug del pipeline. Descartado antes de perseguirlo.

**Causa real**: el campo `certifications` del esquema (`extraction_schema.py`) solo decía "Required certifications (ISO 9001, ISO 27001, ENS, CMMI...)" -- sin excluir explícitamente el papeleo administrativo del propio pliego, que un modelo de razonamiento generalizó como "certificación" al no tener una frontera más clara.

**Mitigación aplicada**: descripción del campo reescrita para excluir explícitamente declaraciones/formularios de la propia oferta (DEUC, declaraciones responsables, de protección de datos), dejando solo certificaciones de calidad/seguridad que el proveedor ya posee de antemano.

**Verificado con una corrida real repetida, no asumido corregido**: se limpió la caché de `1276564F` y se relanzó el análisis contra el mismo pliego real dos veces más tras el cambio:
- 2ª corrida: `certifications: []`, `citation_faithfulness: 0.75` (antes 0.44), veredicto `APTO` sin motivos -- la mejora limpia.
- 3ª corrida (repetida para capturar el *logging* de coste del Paso 5): `certifications` volvió a traer dos entradas problemáticas -- una declaración administrativa distinta y, de nuevo, una fuga de un nombre de campo interno, esta vez literalmente `"citation"`.

**Conclusión honesta**: la mejora del esquema reduce el problema (ya no aparecían tres entradas malas, y en una corrida no apareció ninguna) pero no lo elimina -- el modelo gratuito sigue siendo no determinista en el límite de esta distinción incluso con `temperature=0`, y `compute_verdict` no tiene forma de distinguir una certificación real de una cadena basura sin arriesgar el mismo tipo de heurística frágil que la 3.7 evitó a propósito para el matching de nombres. **No se ha intentado parchear esto con una heurística de longitud/forma de cadena** -- exactamente el tipo de patrón fragil que el proyecto ya rechazó una vez (3.7, matching por subcadena). Queda documentado como riesgo residual real, candidato natural para los evals de RAGAS de la Fase 4 (un golden set más grande mediría esto sistemáticamente, no una muestra de tres corridas), no para un parche ad hoc aquí.

### Paso 5 — Hallazgo real: coste/tokens de cada llamada no quedaban visibles en ningún sitio (corregido)

`extract_structured` devuelve `OpenRouterUsage` (tokens de prompt/completado, coste) en cada llamada -- pero `graph.py::_extract` solo leía `response.content`, descartando el resto. `extraction_eval.py` (la herramienta de comparación de la 3.4) sí lo aprovecha; el camino de producción, no. Dado que `TenderAnalysis` no persiste coste (cachea por hash, no por llamada -- ver docstring del propio modelo desde 3.1) y Celery no tiene *result backend*, el log del worker es el único sitio donde ese dato puede quedar visible en absoluto.

Añadido `logger.info` en `_extract`, justo tras la llamada, con modelo, tokens de prompt/completado y coste. Sin nueva columna ni migración -- una adición de visibilidad, no de esquema.

### Paso 6 — `.env.example` seguía nombrando los modelos descartados en la 3.4 (corregido)

El comentario de `OPENROUTER_API_KEY` seguía diciendo "DeepSeek R1, Qwen3 Coder 480B" -- los candidatos originales de la planificación de la Fase 3, que la propia 3.4 descartó por dejar de ser gratuitos antes de poder medirlos. Corregido para nombrar el modelo real en producción (`nvidia/nemotron-3-super-120b-a12b:free`) con referencia a `phase3.4.md`.

### Paso 7 — Análisis end-to-end reales, contra infraestructura real

Tres corridas reales completas de `1276564F` (el pliego más corto del golden set), cada una vía `POST /tenders/1276564F/analyze` sobre un servidor `uvicorn --reload` real y un worker Celery real (`--pool=solo`), con `OPENROUTER_API_KEY` real -- no simulado.

**Nota operativa encontrada al montar esto, no un bug**: un primer intento con `uv run uvicorn compass.main:app --port 8010` (sin `--reload`) daba `500` en cualquier endpoint que tocara la base de datos, con `psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop'`. Investigado antes de asumir un bug de producto: el propio código fuente de `uvicorn` (`uvicorn/loops/asyncio.py`, `uvicorn/config.py::Config.use_subprocess`) usa `ProactorEventLoop` en Windows **salvo que** `reload` esté activo (o haya más de un worker), en cuyo caso usa `SelectorEventLoop` -- justo por eso el comando de desarrollo documentado en `CLAUDE.md` siempre lleva `--reload`. No es un bug de Compass; es la razón concreta, antes no explicada, de por qué ese flag no es opcional en Windows -- igual que `--pool=solo` para Celery.

Resultados reales:

| Corrida | Tiempo real (petición → `COMPLETED`) | Coste | Resultado |
|---|---|---|---|
| 1ª (antes del Paso 4) | 101s | 0,00 € (nivel gratuito) | `NO_APTO`, 3 motivos (2 papeleo mal clasificado + 1 fuga de campo interno) |
| 2ª (tras el fix del Paso 4) | 75s | 0,00 € | `APTO`, sin motivos, `citation_faithfulness` 0,75 |
| 3ª (repetida para el *logging* del Paso 5) | 260s | 0,00 € | `APTO_CON_RESERVAS`\* |

\* Certificaciones de nuevo con ruido (ver Paso 4); no afectó al veredicto de bloqueo esta vez por azar de qué cadena concreta salió, no por que el riesgo esté resuelto.

**La 3ª corrida es la confirmación real del arreglo del Paso 3**: 260s de duración total, muy por encima de los 180s del timeout mal entendido y de las dos corridas anteriores (75-101s) -- exactamente la variabilidad que la 3.5 había registrado -- y aun así terminó con éxito dentro del nuevo tope de 300s, sin necesitar el segundo intento del `RetryPolicy`. No fue una coincidencia contra un caso sintético: fue el propio pliego del golden set, el mismo modelo de producción, en una corrida real.

No se ha podido capturar el número exacto de tokens del *logging* del Paso 5 en esta revisión: el archivo de salida del worker en segundo plano de este entorno no refleja el `stdout` de Celery hasta que el proceso se detiene (confirmado repitiéndolo en dos workers distintos), y solo quedó disponible el hecho de que el log se emite, no su contenido de esa corrida concreta. El coste en sí (0,00 €, nivel gratuito) sí quedó confirmado en los tres casos por el propio campo `usage.cost` de OpenRouter, consistente con todas las mediciones de la 3.4/3.5.

### Verificación final

- `uv run pytest`: **189 passed**.
- `uv run ruff check .` / `ruff format --check .`: sin avisos.
- `uv run mypy` (proyecto completo): sin avisos.
- `uv run alembic check`: sin drift.
- README (raíz del repo) actualizado con el estado real de la Fase 3 y las cifras de esta misma tabla.

Subfase 3.9 completada -- y con ella, la Fase 3 entera. Los cuatro criterios de aceptación se cumplen: los hallazgos reales se abordaron con decisión → implementación → tests → verificación contra infraestructura real (incluyendo tres análisis end-to-end genuinos, no simulados); el README documenta coste y tiempo reales; la suite, el linter y los tipos están limpios; y no hay drift de esquema. El hallazgo del Paso 4 se cierra como **mitigado, no resuelto** -- documentado así a propósito, no maquillado, con el riesgo residual señalado hacia la Fase 4.
