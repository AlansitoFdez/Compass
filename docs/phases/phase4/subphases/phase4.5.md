# Subfase 4.5 — Endurecimiento de prompt injection

## Plan acordado

Del desglose de la Fase 4 (`docs/phases/phase4/phase4.md`): delimitadores explícitos alrededor del texto del PDF (no confiable) dentro del prompt de usuario, separado con claridad del prompt de sistema; política concreta de qué contenido no se loguea en las trazas de Langfuse. El resto de las mitigaciones del documento de diseño (agente sin herramientas de escritura, validación Pydantic antes de persistir) ya existen desde la 3.6/3.8 -- se documentan como tales, no se reconstruyen.

### Criterios de aceptación

1. El prompt de usuario delimita el texto del pliego con marcas explícitas, y el prompt de sistema instruye al modelo a ignorar cualquier instrucción dentro de esas marcas.
2. Las trazas de Langfuse no vuelcan el texto completo del PDF en cada nodo del grafo.
3. `uv run pytest`, `ruff check --fix`, `ruff format`, `mypy` limpios.

## Progreso

### Delimitadores en el prompt

`analysis/graph.py`: `build_prompt` envuelve el texto del PCAP entre `<PLIEGO>` y `</PLIEGO>`; `SYSTEM_PROMPT` instruye explícitamente al modelo a tratar cualquier instrucción dentro de esas marcas como texto inerte, nunca como una orden a seguir. El pliego es un PDF de un tercero no confiable -- el agente lector ya no tenía herramientas que un *prompt injection* pudiera abusar (3.6, principio de menor privilegio), pero el prompt en sí no marcaba antes dónde empezaba y terminaba el contenido ajeno.

### Qué no se loguea en Langfuse

`analysis/tracing.py`: `_mask_long_text`, pasada como `mask` al construir el cliente de Langfuse. Trunca cualquier cadena de más de 500 caracteres (recorriendo diccionarios y listas), dejando intactas las citas y descripciones de la extracción final (unos pocos cientos de caracteres como mucho).

**No es un control de confidencialidad** -- un PCAP es un documento público de PLACSP, nada de lo que maneja este grafo es secreto. Existe porque el `CallbackHandler` de LangGraph (4.1) traza automáticamente la entrada/salida completa de cada nodo, y `PliegoAnalysisState["pages"]` lleva el texto completo del PCAP página a página -- sin esto, cada traza duplicaría decenas de miles de caracteres de texto del PDF por nodo, sin ningún beneficio sobre leer el PDF real.

**Hallazgo real al testear, corregido antes de dar el paso por cerrado**: el primer test usaba una cadena apenas por encima del umbral (501 caracteres) para comprobar el truncado -- y falló, porque el propio mensaje de truncado ("... [N caracteres, truncado]") tiene un coste fijo de caracteres que puede hacer que el resultado sea *más largo* que el original cuando este está justo por encima del límite. No es un bug real para el caso que motiva esto (páginas de PCAP de miles de caracteres, donde el ahorro es enorme), pero sí una aserción de test mal elegida -- corregida usando un tamaño de página realista (10.000 caracteres) en vez de un valor al borde del umbral.

Tests nuevos: `test_tracing.py` (cadenas cortas intactas, cadenas largas truncadas con su longitud original indicada, recursión real en un diccionario con listas anidadas -- la forma real de `PliegoAnalysisState` --, y que los valores no-string pasan sin tocar) y una prueba en `test_graph.py` de que `build_prompt` envuelve el texto en `<PLIEGO>`/`</PLIEGO>`.

Suite completa: **198 passed** (193 previos + 5 nuevos). `ruff check`/`format --check`/`mypy` sin avisos.

Subfase 4.5 completada. Los tres criterios de aceptación se cumplen.
