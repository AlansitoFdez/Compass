# Subfase 3.3 — Chunking consciente de la estructura

## Plan acordado

Del desglose de la Fase 3 (`docs/phases/phase3/phase3.md`): segmentación del texto en cláusulas numeradas con título como metadato, en vez de bloques de tamaño fijo -- medible con un before/after real, no solo con la teoría del documento de diseño.

### Decisiones tomadas en la conversación de planificación

- **Regex de primera pasada, no un parser exhaustivo.** Cubre `Cláusula N[.-:]? Título` (número con puntos tipo `12.2`, acento opcional). No cubre ordinales en letra ("CLÁUSULA PRIMERA") ni pliegos que numeren sin la palabra "Cláusula" -- limitación anotada explícitamente, a revisar en la 3.4 contra pliegos reales, no adivinada ahora sin tenerlos delante.
- **Página de inicio, no todas las páginas que ocupa.** `Clause.page` es donde empieza la cabecera -- lo que hace falta para una cita ("cláusula 12.2, página 7") -- no un rango.
- **`chunk_fixed_size` existe solo para la comparación, no para producción.** Es el "antes" del before/after que pide el diseño; nada más lo usa.

### Criterios de aceptación

1. `chunk_by_clause` extrae las 4 cláusulas del fixture con número, título y página correctos.
2. Demostración real (test) de que el chunking ingenuo parte al menos una cláusula, y el chunking por cláusula no.
3. `uv run pytest`, `ruff check --fix`, `ruff format`, `mypy` limpios.

## Progreso

`analysis/chunking.py`: `chunk_by_clause(pages) -> list[Clause]` concatena las páginas llevando un mapa de offset a página, encuentra las cabeceras con `CLAUSE_HEADER`, y corta cada cláusula desde su cabecera hasta la siguiente. `chunk_fixed_size(pages, size=500)` es el chunker ingenuo de comparación.

**Verificado contra el fixture real antes de escribir las aserciones** (no asumido): las 4 cláusulas de `sample_pliego.pdf` salen con número, título y página exactos (`1`/`2` en página 1, `3`/`4` en página 2 -- coincide con dónde arranca cada cabecera de verdad). Con `size=100`, el chunk `[300:400]` contiene la cabecera de la cláusula 3 pero el chunk siguiente ya no tiene ninguna cabecera dentro -- solo cuerpo de la cláusula 3 huérfano de su propio número y título. Ese es el before/after real: no una comparación en abstracto, sino el fallo concreto que el diseño describe ("parte cláusulas de solvencia por la mitad") reproducido sobre datos reales.

Tests: extracción de las 4 cláusulas con sus tres campos exactos, cada cláusula empieza por su propia cabecera (nunca por el cuerpo de otra), y la demostración del chunk ingenuo que deja cuerpo de cláusula sin cabecera -- con una aserción que falla ruidosamente si el fixture o el tamaño de chunk cambiaran y dejaran de demostrar el fallo, en vez de pasar en falso.

Suite completa: **136 passed** (133 previos + 3 nuevos). `ruff check`/`format --check`/`mypy` sin avisos.

Subfase 3.3 completada. Los tres criterios de aceptación se cumplen.
