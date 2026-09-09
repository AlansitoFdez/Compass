# Subfase 3.5 — Citas verificadas

## Plan acordado

Del desglose de la Fase 3 (`docs/phases/phase3/phase3.md`): construcción en Python de la verificación de que la cita que el modelo dice haber usado (`clause`, `page`, `quote`) existe de verdad en el texto ya parseado del pliego -- lo que hace el resultado medible para RAGAS faithfulness en la Fase 4.

### Decisión tomada en la conversación de planificación, con datos reales delante

Antes de escribir el código se comprobó, contra una extracción real completa (`nex-agi/nex-n2.5-pro:free` sobre `1276564F`, capturada en vivo), qué tan "verbatim" son de verdad las citas de un modelo:

- Las **8 citas** de esa extracción (una por campo con cita) verifican **exactas** contra el texto real parseado de su página citada -- con una única normalización: colapsar espacios en blanco (incluyendo saltos de línea embebidos donde el PDF envuelve una línea a media frase).
- **No hizo falta tocar acentos ni símbolos de moneda.** Una sospecha inicial en ese sentido (de una prueba de humo anterior con un fragmento sintético sin acentos escrito a mano) quedó descartada al repetir la comprobación contra el documento real completo: el modelo preserva acentos y el símbolo `€` con fidelidad cuando el texto de origen los tiene.
- Los 8 números de página también fueron exactos -- no hizo falta tolerancia de página ±1.

Esto simplificó la implementación: normalización de espacios en blanco y comparación de substring exacto, nada de *fuzzy matching* ni umbrales de similitud (que habrían arriesgado dar por buena una cita parecida pero inventada, justo lo que este paso existe para detectar).

### Criterios de aceptación

1. `verify_citation` verifica correctamente citas reales de una extracción real completa y rechaza una cita fabricada.
2. `citation_faithfulness` da un número real (no un 0/1 forzado por construcción) sobre al menos un documento real del golden set.
3. Tests, `ruff`, `mypy` limpios.

## Progreso

### Paso 1 — Comprobación con datos reales antes de diseñar

Se capturó la extracción completa de `nex-n2.5-pro` sobre `1276564F` (el pliego más corto del golden set) y se comparó cada una de sus 8 citas contra el texto real de la página que decían citar, usando `document.extract_pages` sobre el mismo `pcap_url` de producción. Las 8 verificaron exactas tras normalizar solo espacios en blanco -- la evidencia que fijó el diseño de la sección anterior, en vez de adivinar una estrategia de comparación difusa por adelantado.

**Nota operativa, no bloqueante**: durante esta misma investigación, una llamada a `nemotron-3-super-120b` (el modelo elegido en la 3.4) sobre este mismo documento entró en una traza de razonamiento anómalamente larga (>10 minutos sin converger, cortada manualmente) y, en un reintento posterior, el proveedor (Nvidia) devolvió un 502 explícito ("Service temporarily overloaded"). Ninguno de los dos afecta la decisión de modelo de la 3.4 -- la corrida completa del golden set fue consistente y rápida -- pero es una variabilidad real del nivel gratuito a tener en cuenta cuando la 3.8 diseñe la orquestación (timeout y reintentos ya existen en `extract_structured`/`extraction_eval.py` desde la 3.4).

### Paso 2 — Verificación

`analysis/verification.py`:

- `verify_citation(citation, pages) -> bool`: normaliza espacios en blanco en la cita y en el texto de la página citada (`citation.page`, 1-indexado, mismo convenio que `Clause.page` de la 3.3), y comprueba que la cita normalizada es substring exacto. `False` si la página está fuera de rango, en vez de lanzar.
- `citation_faithfulness(extraction, pages) -> float`: fracción de las citas *presentes* (no `None`) que verifican. Un campo sin cita (el pliego no aborda ese punto) no cuenta ni a favor ni en contra -- no hay nada que verificar. Vacío (extracción sin ninguna cita) puntúa 1.0 por convención: nada que verificar no es lo mismo que no ser fiel.

### Paso 3 — Tests

`tests/analysis/test_verification.py`, contra el fixture real `sample_pliego.pdf` (3.2/3.3), no cadenas sintéticas: cita exacta que verifica, cita fabricada que no, cita real atribuida a la página equivocada que no, página fuera de rango que no lanza, y el caso central de la 3.5 -- una cita que reordena en una sola línea el salto de línea real del fixture (`"cifra de negocio\nminima de 100000 euros"`) y sigue verificando tras normalizar. `citation_faithfulness`: vacío, todo verificado, y una mezcla que da exactamente 0.5 (protege que es una fracción real, no una bandera booleana).

**Criterio de aceptación 2, verificado con datos reales**: `citation_faithfulness` sobre la extracción real completa capturada en el paso 1 (8 citas, todas contra el `pcap_url` real de `1276564F`) da **1.0** -- no un número forzado por construcción del test, sino el resultado real de medir una extracción real contra su pliego real.

Suite completa: **158 passed** (150 previos + 8 nuevos). `ruff check`/`format --check`/`mypy` sin avisos.

Subfase 3.5 completada. Los tres criterios de aceptación se cumplen.
