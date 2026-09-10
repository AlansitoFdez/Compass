# Subfase 4.1 — Langfuse: cuenta, dependencia, primera traza real

## Plan acordado

Del desglose de la Fase 4 (`docs/phases/phase4/phase4.md`): cuenta en Langfuse Cloud, `langfuse` como dependencia nueva, instrumentación del grafo (3.6) para que cada nodo aparezca como *span* con su duración, y la llamada a `extract_structured` con tokens/coste reales -- sustituye al `logger.info` de la 3.9, no convive con él.

### Criterios de aceptación

1. `POST /tenders/{expediente}/analyze` real produce una traza real en el dashboard de Langfuse, con los cuatro nodos del grafo (`fetch`, `check_text_layer`, `extract`, `verify`) visibles.
2. El nodo `extract` lleva tokens y coste reales, no simulados.
3. Los tests no dependen de red real contra Langfuse.
4. `uv run pytest`, `ruff check --fix`, `ruff format`, `mypy` limpios.

## Progreso

### Paso 1 — Cuenta y dependencias

Alan creó la cuenta en Langfuse Cloud y añadió `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` reales a su `.env` antes de que existiera siquiera `.env.example` con esos nombres -- documentados ahí después, junto a `LANGFUSE_BASE_URL` (por defecto la región EU).

`uv add langfuse` resolvió `langfuse==4.15.2` (SDK basado en OpenTelemetry, no el cliente REST simple de versiones anteriores) más sus dependencias de OTEL. **Dependencia adicional no anticipada, añadida también**: `langfuse.langchain.CallbackHandler` hace `import langchain` en tiempo de import (para comprobar su versión) aunque solo use símbolos de `langchain_core` -- sin el paquete `langchain` completo instalado, revienta con `ModuleNotFoundError` al arrancar la API. `uv add langchain` (1.4.0) resuelto sin más dependencias nuevas -- ya comparte `langchain-core` con LangGraph.

### Paso 2 — `core/config.py` y `.env.example`

`Settings` gana `langfuse_public_key: str`, `langfuse_secret_key: str` (obligatorios, sin default -- mismo criterio que `openrouter_api_key`) y `langfuse_base_url: str = "https://cloud.langfuse.com"` (con default: es el valor por defecto real del propio SDK, y la mayoría de cuentas nuevas caen en la región EU).

### Paso 3 — `analysis/tracing.py`: por qué un cliente construido a mano, no `langfuse.get_client()` a secas

Investigado antes de escribir el nodo: la forma "idiomática" del SDK es llamar a `get_client()` sin argumentos, que lee `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_BASE_URL` directamente de `os.environ`. Pero `pydantic-settings` (todo el resto del proyecto) lee `.env` hacia el modelo `Settings`, **no** vuelca esas variables al entorno real del proceso -- nada en el proyecto hace ese volcado hoy. Confiar en `get_client()` a secas habría dependido de que esas variables también estuvieran exportadas de verdad en el entorno, algo que nunca se ha necesitado hasta ahora y que no está garantizado.

`get_langfuse_client()` construye el cliente explícitamente desde `Settings` (`Langfuse(public_key=..., secret_key=..., base_url=...)`), cacheado con `@lru_cache` igual que `get_settings()`. Verificado contra el propio comportamiento del SDK (confirmado en su documentación vía `context7` y contrastado con el código fuente instalado): en modo de un solo proyecto, construir un cliente así lo registra como el *singleton* por defecto -- cualquier `get_client()` posterior (incluido el que `CallbackHandler()` hace internamente) devuelve esta misma instancia, sin duplicar clientes ni pelear con el mecanismo de variables de entorno del SDK.

### Paso 4 — Instrumentación del grafo

`analysis/graph.py`:

- `analyze_pliego` abre un `span` raíz (`langfuse.start_as_current_observation(name="analyze_pliego", ...)`) alrededor de la invocación del grafo, y pasa un `CallbackHandler()` en `config={"callbacks": [handler]}` a `_GRAPH.ainvoke(...)`. LangGraph propaga ese `config` a cada nodo igual que cualquier *Runnable* de LangChain -- `fetch`, `check_text_layer`, `_route_after_text_layer_check`, `extract` y `verify` aparecen como *spans* hijos automáticamente, sin instrumentar cada nodo a mano.
- `_extract` abre además su propia observación de tipo `generation` (`as_type="generation"`, con el modelo real) alrededor de la llamada a `extract_structured`, y la actualiza con `usage_details` (tokens de prompt/completado/total) y `cost_details` (`{"total": ...}`, el mismo formato que el propio SDK usa internamente para el coste de OpenRouter -- verificado leyendo `langfuse/openai.py`, no adivinado). **Sustituye por completo** el `logger.info` que la 3.9 había dejado como parche de visibilidad mínima.
- `langfuse.flush()` en un `finally` de `analyze_pliego`: un proceso de Celery puede reciclarse entre tareas, así que no basta con confiar en el intervalo de *flush* en segundo plano del cliente -- mismo criterio que los commits explícitos de `tasks.py`.

### Paso 5 — Tests sin red real contra Langfuse

`tests/conftest.py`: `os.environ.setdefault("LANGFUSE_TRACING_ENABLED", "false")` antes de cualquier importación de test -- el propio cliente de Langfuse combina su parámetro `tracing_enabled` con esta variable de entorno, así que desactiva toda actividad de red real para toda la sesión de tests sin tocar cómo se construye el cliente. Mismo criterio que mockear siempre OpenRouter: un test no debería escribir trazas sintéticas en el proyecto real de Langfuse de Alan.

**Hallazgo operativo durante la verificación, no un bug**: la suite completa se quedó colgada al ejecutarla -- Docker Desktop se había cerrado en algún momento entre la planificación y la ejecución de esta subfase, y Redis/Postgres rechazaban la conexión. Nada que ver con Langfuse; confirmado reproduciendo el mismo cuelgue con el código de la 3.9 sin tocar, y resuelto en cuanto Alan reabrió Docker Desktop.

Suite completa: **189 passed** (sin tests nuevos -- el criterio de aceptación 3 se protege con la configuración de `conftest.py`, no con una aserción nueva). `ruff check`/`format --check`/`mypy` sin avisos. `alembic check` sin drift (esta subfase no toca el esquema).

### Paso 6 — Verificación real, contra la cuenta real de Langfuse

Disparado un análisis real (`POST /tenders/0025-26/analyze`, un tender nunca antes analizado, servidor `uvicorn --reload` y worker Celery reales) y confirmado en el dashboard real de Langfuse -- no solo "no lanzó excepción":

- Traza `analyze_pliego` con los cinco *spans* del grafo (`fetch`, `check_text_layer`, `_route_after_text_layer_check`, `extract`, `verify`) más la propia envoltura `LangGraph`, cada uno con su latencia real (`fetch`: 4,27s; el par `extract`: 2m 49s).
- El nodo `extract` de tipo `generation` con **`Provided Model Name: nvidia/nemotron-3-super-120b-a12b:free`** y **coste real: $0,00** -- el nivel gratuito, coherente con todas las mediciones anteriores (3.4, 3.5, 3.9).
- **Hallazgo propio durante la verificación**: `client.api.observations.get_many()` (la API REST de lectura) devuelve una vista reducida que no incluye `usage_details`/`cost_details` -- confirmado con dos trazas de depuración construidas a mano (coste ficticio $0,001/$0,0042) que tampoco aparecían por esa vía a pesar de que el log de depuración del SDK mostraba el *span* de OpenTelemetry con los atributos correctos. La confirmación real vino del propio dashboard (captura de Alan), no de la API -- anotado para no repetir el mismo callejón sin salida si una subfase futura necesita leer costes por API en vez de a mano.

## Verificación final

- `uv run pytest`: **189 passed**.
- `uv run ruff check .` / `ruff format --check .`: sin avisos.
- `uv run mypy` (proyecto completo): sin avisos.
- `uv run alembic check`: sin drift.
- Traza real verificada en el dashboard de Langfuse Cloud (captura de pantalla de Alan), con coste y modelo reales en el nodo `extract`.

Subfase 4.1 completada. Los cuatro criterios de aceptación se cumplen.
