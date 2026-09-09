# Subfase 3.4 — Esquema Pydantic cerrado y primera extracción real

## Plan acordado

Del desglose de la Fase 3 (`docs/phases/phase3/phase3.md`): todos los campos del esquema (solvencia económica y técnica, certificaciones, criterios de adjudicación con sus porcentajes, garantías, plazo de ejecución, fecha límite, subcontratación, lotes), cada uno con su cita de origen. Decisión final de modelo de extracción medida contra un golden set pequeño de pliegos reales, mismo método que decidió el modelo de embeddings en la 2.4 -- no a ciegas.

### Decisiones tomadas en la conversación de planificación

- **Hallazgo que invalidó la premisa de `phase3.md`**: al llegar a esta subfase, ni DeepSeek R1 ni Qwen3 Coder 480B (los candidatos escritos en la planificación de Fase 3) seguían siendo gratuitos en OpenRouter -- verificado contra `GET /api/v1/models` el 2026-09-09: ningún modelo DeepSeek o Qwen tiene precio 0 en el catálogo actual. El nivel gratuito de OpenRouter había rotado por completo a otra generación de modelos. Decisión de Alan: sustituir por los dos candidatos gratuitos más fuertes del catálogo vigente con `structured_outputs` soportado -- `nvidia/nemotron-3-super-120b-a12b:free` (120B, 262K de contexto) y `nex-agi/nex-n2.5-pro:free` (262K de contexto). `phase3.md` actualizado para reflejar el cambio.
- **Golden set de 4 pliegos reales, no 25-30.** El golden set de 25-30 pliegos del documento de diseño es el de RAGAS (Fase 4); esta subfase solo necesita comparar dos candidatos sobre datos reales heterogéneos, mismo criterio de tamaño que el golden set de embeddings de la 2.4 (pequeño, real, no a ciegas).
- **Cita verificada en Python (3.5) todavía no se construye aquí.** El esquema ya lleva `Citation` (cláusula, página, cita textual) en cada campo, pero el paso que comprueba que la cita existe de verdad en el texto parseado es la 3.5, no esta subfase.
- **Sin SDK de OpenRouter.** Confirmado: su API es compatible con el formato de OpenAI vía REST normal, y `httpx2` (ya dependencia) bastó para el único endpoint que hace falta (`/api/v1/chat/completions` con `response_format: json_schema, strict: true`).

### Criterios de aceptación

1. `PliegoExtraction` (Pydantic, `extra="forbid"` en cada submodelo) cubre los 9 campos del documento de diseño, cada uno con su `Citation` (cláusula, página, cita textual) opcional -- `None` solo cuando el pliego no aborda ese punto.
2. Golden set de 4 `expediente` reales (de los matches vivos del perfil sembrado), anotado a mano campo a campo contra el PCAP real descargado, con cita textual verbatim -- no una paráfrasis.
3. Los dos candidatos gratuitos medidos contra el golden set con números reales de aciertos, no a ciegas; modelo decidido y documentado aquí con el número delante.
4. `uv run pytest`, `ruff check --fix`, `ruff format`, `mypy` limpios sobre todo el código nuevo.

## Progreso

### Paso 1 — Catálogo de OpenRouter y elección de candidatos

Antes de escribir ningún esquema, se comprobó si los dos candidatos de la planificación seguían vigentes: consulta directa a `GET https://openrouter.ai/api/v1/models` (709 KB, 100% de los modelos del catálogo). **Ni un solo modelo DeepSeek ni Qwen tiene precio 0** en el catálogo actual -- ni con el sufijo `:free` ni sin él. El nivel gratuito de OpenRouter había rotado por completo desde que se escribió `phase3.md`: de los 18 modelos `:free` vigentes hoy, solo 6 declaran `structured_outputs` soportado. Alan decidió sustituir por `nvidia/nemotron-3-super-120b-a12b:free` y `nex-agi/nex-n2.5-pro:free` -- los dos con mayor tamaño/contexto de esos 6. `phase3.md` actualizado en el sitio con este hallazgo, en vez de dejar la nota obsoleta.

### Paso 2 — Esquema Pydantic cerrado

`analysis/extraction_schema.py`: `PliegoExtraction` con un submodelo por campo del documento de diseño (`EconomicSolvency`, `TechnicalSolvency`, `AwardCriteria`/`AwardCriterion`, `Guarantees`, `ExecutionDeadline`, `SubmissionDeadline`, `Subcontracting`, `Lots`) más `certifications: list[str]`, cada uno con su `Citation` (`clause`, `page`, `quote`) -- `None` solo cuando el pliego no aborda ese punto en absoluto. Todos con `model_config = ConfigDict(extra="forbid")`: verificado que esto es lo que hace que `model_json_schema()` emita `additionalProperties: false` en cada objeto anidado, el requisito real de OpenRouter/OpenAI para `strict: true` -- comprobado contra el JSON Schema generado, no asumido.

Los campos numéricos (`minimum_annual_turnover_eur`, `minimum_amount_eur`, `definitive_percentage`) son `float | None` deliberadamente: un pliego real puede no expresar la solvencia como una cifra en euros en absoluto (visto en el paso 3), y forzar un número ahí sería inventar dato donde el pliego no lo da.

### Paso 3 — Golden set: 4 pliegos reales, anotados a mano

Candidatos: los matches reales del perfil sembrado (`GET /matches`, 52 hoy, 50 con `pcap_url` no nulo). Se descargaron y clasificaron 8 candidatos por diversidad estructural; se anotaron a fondo 4, elegidos por variar deliberadamente en cómo (o si) cada campo se expresa -- no por ser fáciles:

- **`SER/2026/0000006435`** (Hipatia, Gobierno de Canarias) -- PCAP narrativo de 53 páginas. Solvencia económica y técnica como cifras exactas (37.305,00 € / 26.113,50 €); sin certificaciones formales exigidas; fecha límite de presentación **no** fijada en el PCAP, remite al anuncio de licitación.
- **`A41119033-2026/000065-PeAS`** (INPRO, soporte OpenCms/PHP) -- formato "Cuadro de Características" (tabla resumen), estructuralmente distinto a los otros tres. El más rico en certificaciones explícitas: CMMI nivel 3, cuatro familias ISO (9000/14000/20000/27000), ENS vía CCN-CERT.
- **`1276564F`** (Ayuntamiento de Cieza, hosting/plugins WordPress) -- solvencia económica **no** expresada como cifra de negocio: se acredita con una póliza de seguro de responsabilidad civil (100.000 €). Caso deliberado para comprobar que el modelo no fuerza un número donde el pliego da otro tipo de garantía.
- **`69/2026`** (Ayuntamiento de San Andrés del Rabanedo, mantenimiento AYTOS) -- procedimiento negociado sin publicidad por exclusividad de proveedor: precio como único criterio de adjudicación (100 puntos), subcontratación **expresamente prohibida** (el único de los cuatro), y el plazo de presentación remite al escrito de invitación, no a un anuncio público -- un tercer mecanismo de "no fijado en el PCAP" distinto de los dos anteriores.

Cada campo anotado en `analysis/golden_set.py` con su cita textual copiada literalmente del PCAP descargado (`compass.analysis.document.extract_pages` contra el `pcap_url` real), no parafraseada.

**Hallazgo real, no buscado**: al construir el golden set con `chunk_by_clause` (3.3) se comprobó que solo detecta cabeceras de verdad en 2 de los 4 PCAPs reales (32 y 91 cláusulas en `1276564F` y `69/2026`, que sí usan la palabra "Cláusula"). En `SER/2026/0000006435` detecta solo 2 (falsos positivos, referencias cruzadas a media frase) y en `A41119033-2026/000065-PeAS` detecta 0 -- ambos numeran sus secciones ("1. OBJETO DEL CONTRATO", "6. SOLVENCIA:") sin la palabra "Cláusula" en absoluto, exactamente la limitación que la 3.3 dejó anotada explícitamente para revisar aquí "contra pliegos reales, no adivinada ahora". Se investigó una extensión del regex (exigir título en mayúsculas para la cabecera sin "Cláusula"), pero un caso real la tira abajo: `4.3.1. Solvencia económica y financiera` en el propio Hipatia es un título en Title Case, no en mayúsculas -- justo el campo más importante de citar bien. Una heurística de solo texto no basta para distinguir de forma fiable una cabecera real de un ítem numerado dentro del cuerpo de otra cláusula (ej. "1. Resumen Ejecutivo" como sub-apartado de la cláusula 14 de Hipatia); probablemente necesite metadatos de fuente/tamaño de fuente del PDF, que `extract_pages` no conserva hoy. **No se tocó `chunking.py`** (3.3 sigue cerrada tal cual): en su lugar, `extraction_eval.py` construye el prompt a partir del texto completo por página, no de `chunk_by_clause`, para que la comparación entre los dos modelos sea igual de justa en los 4 documentos. Queda anotado como mejora real pendiente para cuando la Fase 3 construya el grafo LangGraph (3.6) o si se decide abordarlo antes.

### Paso 4 — Cliente OpenRouter

`analysis/openrouter.py`: `extract_structured()`, una función async, POST directo a `/api/v1/chat/completions` con `response_format: {type: json_schema, json_schema: {strict: true, schema: <esquema>}}` y `temperature: 0`. Sin SDK nuevo -- confirmado con una llamada real de humo antes de construir el resto: `httpx2` (ya dependencia) fue suficiente. `OpenRouterError` cubre el caso real encontrado en la primera corrida -- OpenRouter puede devolver HTTP 200 con un objeto `error` en vez de `choices` bajo fallo del proveedor upstream (visto contra `nemotron` en la corrida real, no en teoría); antes se colaba como un `KeyError` opaco.

### Paso 5 — Medición real contra el golden set

`analysis/extraction_eval.py`: para cada uno de los 4 `expediente`, descarga el PCAP real (mismo `pcap_url` que usaría producción), construye el prompt con el texto completo por página, llama a cada candidato, valida la respuesta contra `PliegoExtraction`, y puntúa 9 subcampos objetivamente comprobables por documento (los numéricos/booleanos/de lista de los que depende el veredicto de la 3.7 -- no la prosa libre de las descripciones, que no es comparable mecánicamente). Un reintento absorbe el ruido de fallos transitorios del nivel gratuito (visto en la corrida real: un `error` inline de OpenRouter y un `content` vacío, ambos antes de añadir el reintento).

**Hallazgo operativo real, no anticipado**: la primera corrida completa (`nemotron` + `nex-n2.5-pro`, 8 llamadas) se lanzó en segundo plano con una sola llamada HTTP bloqueante por documento -- sin ninguna señal intermedia, 63 minutos sin una sola línea de salida, indistinguible de un cuelgue real. Se cambió `extract_structured()` a modo streaming (`stream: true` + `stream_options.include_usage`) con un callback de progreso que reporta caracteres de razonamiento/contenido recibidos cada 5s -- necesario para poder diferenciar "va lento" de "está colgado" en un nivel gratuito, no una comodidad. También reveló que ambos candidatos son modelos de razonamiento: la mayor parte del tiempo se va en una traza de razonamiento (`delta.reasoning`) antes de emitir el JSON final, no en el JSON en sí.

**Resultado real, con streaming delante en vez de a ciegas**:

| | `nemotron-3-super-120b` | `nex-n2.5-pro` |
|---|---|---|
| Aciertos (36 checks: 9 campos × 4 pliegos) | **36/36 (100%)** | Interrumpido tras 258s en el 1er documento (0/4 completados) |
| Tiempo por documento | 128s / 209s / 31s / 146s | >258s en el primero, sin terminar |
| Coste | 0,00 € | 0,00 € |

`nemotron-3-super-120b-a12b:free` completó los 4 documentos con acierto perfecto en los 9 subcampos objetivos de cada uno (turnover/importe de solvencia, certificaciones, puntos de criterios, garantías, subcontratación, lotes), incluyendo los casos deliberadamente difíciles del golden set: no fuerza un número de solvencia donde `1276564F` da una póliza de seguro en su lugar, recupera las 6 certificaciones completas de `A41119033-2026/000065-PeAS`, y detecta correctamente la subcontratación prohibida de `69/2026`.

`nex-agi/nex-n2.5-pro:free` iba, en el mismo primer documento, más del doble de lento que `nemotron` sin haber emitido aún ningún contenido a los 258s (frente a los 128s en los que `nemotron` ya había terminado el documento entero). Decisión de Alan, con ese margen ya decisivo delante: cortar la corrida de `nex-n2.5-pro` en vez de esperar a que completase los 4 documentos -- la comparación queda incompleta para este candidato (documentado como tal, no ocultado), pero el margen de velocidad y el 100% de `nemotron` no dejaban ambigüedad real que una corrida más larga fuese a cambiar.

### Decisión

**Modelo de extracción elegido: `nvidia/nemotron-3-super-120b-a12b:free`.** Gratuito, 100% de aciertos sobre los 36 checks del golden set, y sensiblemente más rápido que el otro candidato gratuito sobre el mismo documento. Reemplaza a los candidatos originales de la planificación (DeepSeek R1, Qwen3 Coder 480B), que dejaron de ser gratuitos antes de llegar a esta subfase (paso 1).

Subfase 3.4 completada. Los cuatro criterios de aceptación se cumplen -- el tercero con la salvedad documentada de que la medición de `nex-n2.5-pro` quedó incompleta por decisión explícita, no por descuido.
