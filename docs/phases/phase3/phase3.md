# Fase 3 — El agente analista de pliegos

## Objetivo

El embudo de la Fase 2 ya redujo el volumen a un puñado de matches reales por proveedor (52, hoy, para el perfil sembrado). La Fase 3 lee de verdad el pliego (PCAP) de esas licitaciones -- nunca de todo el volumen, siempre bajo demanda -- y responde a la pregunta que de verdad importa antes de preparar una oferta: *¿puedo presentarme, y por qué cláusula concreta si no?* Un agente LangGraph descarga el pliego, lo trocea por cláusula (no por bloques de texto ciegos), y extrae los campos que deciden el encaje -- solvencia, certificaciones, criterios de adjudicación, garantías, plazos, lotes -- cada uno con su cita de origen verificada. El veredicto (APTO / APTO CON RESERVAS / NO APTO) no lo emite nunca el modelo: se calcula en Python, comparando esa extracción contra el perfil del proveedor de la Fase 2, de forma determinista y auditable. Al terminar la fase, desde la ficha de una licitación se puede pedir "analiza este pliego" y recibir un veredicto citado, con el resultado cacheado por hash de documento -- el segundo usuario que mire la misma licitación no vuelve a pagar el análisis.

## Decisiones de arquitectura tomadas en la planificación

- **Modelo de extracción: OpenRouter, nivel gratuito.** Sin coste, sin tarjeta, sin Google (descartado explícitamente). Candidatos a medir en la 3.4 con un golden set real, no a ciegas -- mismo método que decidió el modelo de embeddings en la 2.4: DeepSeek R1 y Qwen3 Coder 480B (262K de contexto, de sobra para un pliego de 60-80 páginas). La API de OpenRouter es compatible con el formato de OpenAI vía REST normal -- probablemente no hace falta ni un SDK nuevo, `httpx2` (ya es dependencia) podría bastar.
- **Citas verificadas en Python, no citas nativas de un proveedor concreto.** Esquema Pydantic con cita textual (`clause`, `page`, `quote`) autoreportada por el modelo, más un paso de verificación local que comprueba que esa cita existe de verdad en el texto ya parseado. Hace el output medible para RAGAS faithfulness en la Fase 4, y de paso hace el extractor agnóstico de proveedor -- encaja con la elección de OpenRouter en vez de depender de una función de citas propietaria de un único proveedor de LLM.
- **Sin OCR.** Pliegos escaneados sin capa de texto se detectan localmente y se marcan `not_analyzable` -- explícitamente fuera de v1 (documento de diseño, riesgos identificados).
- **Resultado cacheado por hash de PDF, en una tabla Postgres nueva.** Celery no tiene result backend ("el log del worker es la única señal de si una tarea terminó bien"), así que el resultado tiene que vivir en algo consultable por HTTP. Extracción cacheada por `pdf_hash` (cara, agnóstica de proveedor); veredicto calculado en el momento de lectura contra el `Provider` actual.
- **Nuevo dominio: `analysis/`.** No `pliegos` (rompería la regla sin excepciones de código en inglés); no `agent/` (nombraría el mecanismo LangGraph, no el dominio). Sigue el mismo patrón que `matching/`: nombra el proceso, no un sustantivo concreto.
- **El nodo de veredicto no tiene LLM ni herramientas de ningún tipo.** Es la materialización directa de "el LLM extrae, el código decide" -- la regla de diseño más importante del proyecto. El agente lector, además, no tiene ninguna herramienta de escritura (principio de menor privilegio: procesa PDFs de terceros no confiables).
- **El análisis corre siempre bajo demanda, nunca en batch sobre todos los matches.** Caro y lento a propósito; el embudo de las Fases 1-2 ya hizo el trabajo de reducir volumen antes de llegar aquí.

## Subfases

1. **3.1 — Dominio `analysis/` y tabla de caché por hash de documento**
   Modelo SQLAlchemy, schema, repositorio, migración. Sin PDF ni LLM todavía -- solo la forma de la tabla (hash, expediente como FK a tenders, estado, columnas vacías para extracción y veredicto).

2. **3.2 — Descarga de PDF y detección de capa de texto**
   Descarga desde `pcap_url` vía `httpx2`, hash del documento, detección determinista de PDF escaneado sin capa de texto (sin OCR). Nueva dependencia de PDF, avisada antes de añadirla.

3. **3.3 — Chunking consciente de la estructura**
   Segmentación del texto en cláusulas numeradas con título como metadato, en vez de bloques de tamaño fijo -- medible con un before/after real.

4. **3.4 — Esquema Pydantic cerrado y primera extracción real**
   Todos los campos del esquema (solvencia económica y técnica, certificaciones, criterios de adjudicación con sus porcentajes, garantías, plazo de ejecución, fecha límite, subcontratación, lotes). Decisión final de modelo (DeepSeek R1 vs. Qwen3 Coder 480B) medida contra un golden set pequeño de pliegos reales, no a ciegas.

5. **3.5 — Citas verificadas**
   Construcción de la verificación en Python: la cita que el modelo dice haber usado existe de verdad en el texto parseado localmente -- lo que hace el resultado medible para RAGAS faithfulness en la Fase 4.

6. **3.6 — Grafo LangGraph completo**
   Ensambla los nodos de las subfases anteriores como un grafo real, con manejo de estado y errores propio de LangGraph, y aplica el principio de menor privilegio (el agente lector sin herramientas de escritura). Consulta a `context7` antes de escribir contra la API de LangGraph.

7. **3.7 — Veredicto determinista**
   Función Python pura que compara la extracción contra el perfil del proveedor y produce APTO / APTO CON RESERVAS / NO APTO con motivo citado. Tests exhaustivos de la lógica de comparación, sin LLM en el camino crítico.

8. **3.8 — Orquestación bajo demanda: tarea Celery + endpoint**
   Tarea Celery bajo demanda (no programada por `beat`, a diferencia de las dos tareas existentes), con caché por hash y lock de Redis contra doble encolado -- mismo patrón que `daily_ingestion_task`. Endpoint para disparar/consultar el análisis desde la ficha de la licitación.

9. **3.9 — Revisión completa de la fase**
   Repaso exhaustivo de 3.1-3.8, mismo patrón que la 2.7 y la 1.11. Coste real medido por análisis contra pliegos reales, README actualizado con los números reales.
