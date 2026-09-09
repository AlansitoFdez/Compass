# Subfase 3.6 — Grafo LangGraph completo

## Plan acordado

Del desglose de la Fase 3 (`docs/phases/phase3/phase3.md`): ensamblar los nodos de las subfases anteriores (3.2 descarga+hash+detección de capa de texto, 3.4 extracción cerrada contra OpenRouter, 3.5 verificación de citas) como un grafo LangGraph real, con manejo de estado y errores propio de LangGraph, aplicando el principio de menor privilegio (el agente lector sin herramientas de escritura). Consulta a `context7` antes de escribir contra la API de LangGraph, como pide la subfase.

### Decisiones tomadas en la conversación de planificación

- **Dependencia nueva, avisada antes de añadirla**: `langgraph`. `uv add langgraph` resolvió `langgraph==1.2.11` (más reciente que la `1.0.8` indexada en `context7` en el momento de consultar, que fue de todos modos la referencia para la forma general de la API -- `StateGraph`, nodos, aristas condicionales -- antes de escribir código).
- **Módulo nuevo `analysis/graph.py`**, con el estado del grafo (`TypedDict`), `SYSTEM_PROMPT`/`build_prompt` migrados aquí desde `extraction_eval.py` (que pasa a importarlos en vez de duplicarlos -- ese script es la herramienta de decisión de modelo de la 3.4, no el camino de producción), y 4 nodos: `fetch` → `check_text_layer` (arista condicional a `END` si `NOT_ANALYZABLE`) → `extract` → `verify`.
- **Menor privilegio**: `extract` no tiene ninguna tool vinculada -- una única llamada de salida estructurada, no un bucle ReAct. Documentado en el módulo para que quede trazable si una subfase futura añade herramientas.

### Criterios de aceptación

1. `analyze_pliego` sobre el fixture de texto real da `COMPLETED` con `extraction` y `citation_faithfulness` poblados.
2. Sobre el fixture escaneado da `NOT_ANALYZABLE` sin llamar a OpenRouter.
3. Un fallo de red en la descarga y un agotamiento de reintentos en la extracción dan `FAILED` con `error_message`, nunca una excepción sin atrapar.
4. Tests, `ruff`, `mypy` limpios.

## Progreso

### Paso 1 — Consulta a `context7` y verificación contra el paquete instalado

`context7` (`/langchain-ai/langgraph`) dio la forma general (`StateGraph`, nodos async con `Runtime[Context]` para inyectar dependencias, `add_conditional_edges`), pero solo indexa hasta la `1.0.8` y `uv add` instaló la `1.2.11`. Antes de escribir el nodo de extracción se verificó contra el paquete real instalado (`RetryPolicy`, la firma de `add_node`, el tipo de retorno de `ainvoke`) en vez de asumir que la documentación indexada seguía siendo exacta.

**Hallazgo que cambió el diseño de errores**: `add_node` acepta un `error_handler` -- un nodo que se invoca cuando otro nodo lanza, en teoría el mecanismo "nativo" para traducir un fallo a estado. Se descartó tras leer el código fuente instalado (`langgraph/pregel/_algo.py`, `_loop.py`): es una feature reciente, mal cubierta por `context7` en esa versión, con una forma de invocación (vía un task especial, no como argumento directo de la función) que habría exigido reverse-engineering en vez de una API estable y documentada. Se optó por lo simple y verificable: un único `try/except` en el borde del grafo (`analyze_pliego`, alrededor de `ainvoke`), que atrapa cualquier excepción que sobreviva a los reintentos y la traduce a `status=FAILED`. `RetryPolicy` (sí bien documentada, un dataclass de configuración simple) es la única pieza "nativa" de LangGraph que gestiona reintentos; el resto del manejo de errores es Python liso, a propósito.

**Segundo hallazgo, con consecuencia real en el diseño del reintento**: el `retry_on` por defecto de `RetryPolicy` (`default_retry_on` en `langgraph/_internal/_retry.py`) reconoce `httpx.HTTPStatusError` -- la librería `httpx`, no `httpx2` (el fork que usa todo el proyecto). Como son clases distintas, el retry por defecto de LangGraph **no habría reintentado nunca** un fallo HTTP transitorio de `httpx2`. Se pasa `retry_on` explícito al nodo `extract`: `(OpenRouterError, httpx2.HTTPError, ValidationError, json.JSONDecodeError)` -- los mismos cuatro fallos que `extraction_eval.py` ya reintentaba a mano en la 3.4, ahora declarativos en vez de un `try/except` duplicado.

### Paso 2 — El grafo

`analysis/graph.py`: estado `PliegoAnalysisState` (`TypedDict, total=False` -- solo `pcap_url` existe al arrancar; cada campo posterior existe únicamente una vez que el nodo responsable ha corrido, lo que hace que leerlo en el nodo siguiente sea seguro por construcción de las aristas, no por convención). Dependencias (`httpx2.AsyncClient`, `api_key`, `model`) inyectadas vía `AnalysisContext` y el mecanismo `context` de LangGraph (`Runtime[AnalysisContext]`) en vez de estado a nivel de módulo -- así los tests pueden pasar un cliente con `MockTransport` sin *monkeypatching*.

4 nodos, como en el plan: `fetch` (descarga+hash+páginas; una URL muerta lanza sin reintento, un 404 no va a arreglarse en el segundo intento), `check_text_layer` (marca `NOT_ANALYZABLE` y corta a `END` por arista condicional, sin gastar nunca una llamada de extracción en un PDF escaneado), `extract` (con el `RetryPolicy` de un único reintento, `max_attempts=2` -- coincide con la evidencia real de 3.4/3.5, no con el valor por defecto de LangGraph, que es 3), `verify` (`citation_faithfulness` contra las páginas ya extraídas).

`analyze_pliego` nunca lanza: compila e invoca el grafo dentro de un único `try/except` en ese borde, y cualquier excepción que llegue hasta ahí (reintentos agotados, o cualquier fallo de `fetch` que no sea reintentable) se traduce a `status=FAILED` con `error_message`.

### Paso 3 — Tests

`tests/analysis/test_graph.py`, contra los fixtures reales de 3.2/3.5 (`sample_pliego.pdf`, `scanned_document.pdf`), con `httpx2.MockTransport` para ambas llamadas de red (descarga del PCAP y `POST` a OpenRouter) -- mismo patrón que `test_document.py`, más un SSE enlatado para la respuesta de *streaming* de OpenRouter.

- **Camino feliz**: `sample_pliego.pdf` + una extracción con una cita real (que verifica, la misma que 3.5 probó explícitamente por reflujar un salto de línea del PDF) y una cita fabricada (que no verifica) → `COMPLETED`, `pdf_hash` correcto, `citation_faithfulness == 0.5` -- una fracción real calculada contra el texto del fixture, no un 0.0/1.0 que la sola construcción del test ya garantizaría.
- **Documento escaneado**: `NOT_ANALYZABLE`, con el *handler* de `extract` configurado para lanzar `AssertionError` si se le llega a llamar -- protege que el corte por arista condicional de verdad evita la llamada, no solo que el estado final sea el correcto.
- **`pcap_url` muerto (404)**: `FAILED` con `error_message`, sin excepción sin atrapar.
- **Completions vacías persistentes**: cuenta las llamadas al *handler* de `extract` y confirma que son exactamente 2 (el `max_attempts` configurado, no el 3 por defecto) antes de dar `FAILED` -- protege el hallazgo del Paso 1 sobre `retry_on`, no solo que el reintento exista.

Suite completa: **162 passed** (158 previos + 4 nuevos). `ruff check`/`format --check`/`mypy` (proyecto completo, sin argumentos) sin avisos.

Subfase 3.6 completada. Los cuatro criterios de aceptación se cumplen.
