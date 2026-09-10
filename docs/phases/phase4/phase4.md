# Fase 4 — Trazas, coste y evals

## Objetivo

Hasta la Fase 3, el agente analista funciona pero es una caja opaca: no hay forma de ver cuánto cuesta de verdad un análisis en producción (el `logger.info` de la 3.9 es un parche de visibilidad mínima, no observabilidad), y la única medida de calidad de la extracción es el golden set de 4 pliegos de la 3.4 -- demasiado pequeño para detectar una regresión real cuando cambie el prompt, el modelo o el chunking. La Fase 4 cierra ambos huecos: Langfuse traza cada análisis con su coste y tokens desglosados, y un golden set de 25-30 pliegos con RAGAS lo convierte en un gate de regresión medible. De paso, endurece el único punto del sistema que ingiere contenido no confiable (el PDF de un tercero) y añade CI para que ninguna de estas garantías dependa de acordarse de ejecutar los comandos a mano.

## Decisiones de arquitectura tomadas en la planificación

- **Langfuse Cloud, no self-hosted.** Self-hosted (desde la v3) son 6 contenedores -- ClickHouse, MinIO, Redis propio, Postgres propio, web y worker --, con un dimensionamiento recomendado de 4 CPU/16 GiB/~100 GB, una tecnología nueva (ClickHouse) que no se usa en ningún otro sitio del proyecto, y sin beneficio real: los PCAP que se trazan son documentos públicos de PLACSP, no datos confidenciales, así que el argumento habitual de "que no salga de mi máquina" no aplica aquí. Cloud es `pip install langfuse` + una API key en `.env`, cero infraestructura nueva.
- **Alcance de la fase confirmado con Alan**: Langfuse + RAGAS + endurecimiento de prompt injection + CI -- las cuatro subsecciones de "transversales" del documento de diseño (§6.2-6.5), no solo las dos que `CLAUDE.md` nombraba explícitamente.
- **Las métricas de RAGAS del documento de diseño (fidelidad, precisión de contexto, recall de contexto) asumen un paso de recuperación que Compass no tiene.** Precisión/recall de contexto miden si los *chunks* recuperados por un RAG son los relevantes -- pero la 3.9 confirmó que `chunk_by_clause` sigue sin usarse en producción: el pliego completo, página a página, va entero al modelo, sin recuperación de ningún tipo. Aplicar esas dos métricas tal cual mediría un componente que no existe.
  - **Lo que sí se mide**: **fidelidad** (`citation_faithfulness`, ya construido en la 3.5 -- RAGAS aquí es la generalización a un golden set de verdad, no una pieza nueva) y **corrección de la extracción** contra el terreno real (extensión del `score_extraction` de la 3.4 al golden set ampliado, como gate de regresión sobre los campos que alimentan el veredicto).
  - Si en el futuro cambia la arquitectura (p. ej. se retoma el chunking para no mandar el documento entero), ahí sí tendría sentido añadir precisión/recall de contexto -- no antes.
- **El golden set de RAGAS extiende el de la 3.4, no lo sustituye.** Los 4 pliegos ya anotados a mano (con cita textual verbatim) se quedan; se anotan entre 21 y 26 más con el mismo método, hasta 25-30 -- mismo criterio de "pequeño, real, no a ciegas" que ya se usó dos veces (2.4, 3.4).

## Subfases

1. **4.1 — Langfuse: cuenta, dependencia, primera traza real**
   Cuenta en Langfuse Cloud, `langfuse` como dependencia nueva (avisada), instrumentación del grafo (3.6) para que cada nodo (`fetch`, `check_text_layer`, `extract`, `verify`) aparezca como un *span* con su duración, y la llamada a `extract_structured` con tokens/coste reales -- sustituye al `logger.info` de la 3.9, no convive con él.

2. **4.2 — Coste real en el README**
   Consulta a Langfuse (API o dashard) para agregar coste/tokens reales de las trazas acumuladas; la métrica "coste medio de analizar un pliego: 0,0X €" del documento de diseño, con datos reales detrás, no una única corrida.

3. **4.3 — Golden set ampliado a 25-30 pliegos**
   Extensión del golden set de la 3.4 (`analysis/golden_set.py`) con 21-26 pliegos reales más de los matches del proveedor sembrado, anotados a mano con cita textual verbatim -- mismo método, más escala.

4. **4.4 — RAGAS: fidelidad y corrección como gate de regresión**
   Integración de RAGAS sobre el golden set ampliado, con las dos métricas decididas arriba (fidelidad, corrección de extracción). Corrido como script repetible (mismo patrón que `extraction_eval.py` de la 3.4), pensado para engancharse al job de CI de la 4.6.

5. **4.5 — Endurecimiento de prompt injection**
   Delimitadores explícitos alrededor del texto del PDF (no confiable) dentro del prompt de usuario, separado con claridad del prompt de sistema; política concreta de qué contenido no se loguea en las trazas de Langfuse. El resto de las mitigaciones del documento de diseño (agente sin herramientas de escritura, validación Pydantic antes de persistir) ya existen desde la 3.6/3.8 -- aquí se documentan como tales, no se reconstruyen.

6. **4.6 — CI con GitHub Actions**
   Job principal (`pytest` + `ruff` + `mypy` en cada push, con Postgres/Redis como *service containers*) que bloquea el merge; job de evals (RAGAS de la 4.4) separado, visible pero no bloqueante.

7. **4.7 — Revisión completa de la fase**
   Mismo patrón que 1.11/2.7/3.9.
