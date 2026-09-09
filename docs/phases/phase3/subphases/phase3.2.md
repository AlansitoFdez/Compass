# Subfase 3.2 — Descarga de PDF y detección de capa de texto

## Plan acordado

Del desglose de la Fase 3 (`docs/phases/phase3/phase3.md`): descarga del pliego desde `pcap_url` vía `httpx2`, hash del documento, y detección determinista de PDF escaneado sin capa de texto -- sin OCR.

### Decisiones tomadas en la conversación de planificación

- **`pdfplumber`, no `pypdf`.** Investigado antes de añadir la dependencia (regla de `CLAUDE.md`): mejor calidad de extracción de texto que `pypdf` -- relevante porque el mismo texto lo reutiliza el chunking por cláusula de la 3.3 -- y licencia MIT, igual de permisiva. `PyMuPDF` descartado desde la propia planificación de fase por su licencia AGPL.
- **Umbral bajo y deliberadamente poco sofisticado para "tiene capa de texto".** Un PCAP real de 60-80 páginas tiene miles de caracteres por página; un escaneado sin OCR, prácticamente cero -- el contraste es tan claro que no hace falta nada más fino que una media de caracteres no-espacio por página (`MIN_CHARS_PER_PAGE = 20`). Coherente con lo que pide el propio diseño: "detectarlos y marcarlos", no diagnosticar con precisión.
- **Fixtures de PDF reales, no mockeadas.** Dos PDFs mínimos válidos construidos a mano (xref con offsets de byte correctos, sin depender de ninguna librería de escritura de PDF) en vez de simular la detección con un booleano de test: uno con texto real extraíble (con cláusulas numeradas, pensado para reutilizarse en la 3.3), otro con una página con stream de contenido vacío -- sin ningún operador de texto -- para representar de verdad "sin capa de texto", no un doble simulado.

### Criterios de aceptación

1. `hash_document` es determinista y estable byte a byte.
2. `has_text_layer` distingue correctamente el fixture con texto del fixture sin capa de texto.
3. `uv run pytest`, `ruff check --fix`, `ruff format`, `mypy` limpios.

## Progreso

`analysis/document.py`: cuatro funciones puras, sin orquestación (eso es de la 3.8) -- `fetch_pcap(url, client)` (mismo patrón de `httpx2` que `ingestion/atom_client.py`, incluido el orden de argumentos), `hash_document(content) -> str` (sha256, clave de `TenderAnalysis.pdf_hash`), `extract_pages(content) -> list[str]` (vía `pdfplumber`, sobre `io.BytesIO` -- `pdfplumber.open` no acepta `bytes` a secas, necesita un objeto tipo archivo), y `has_text_layer(pages) -> bool`.

Fixtures reales verificadas contra `pdfplumber` de verdad antes de darlas por buenas (no solo generadas y asumidas correctas): `sample_pliego.pdf` extrae 375 y 214 caracteres de sus dos páginas con las cláusulas de prueba intactas; `scanned_document.pdf` extrae 0 caracteres en su única página.

Tests: hash determinista y sin colisión entre fixtures, extracción por página, `has_text_layer` verdadero/falso contra ambos fixtures reales más el caso borde de lista vacía, y `fetch_pcap` con transporte mockeado (URL solicitada, bytes devueltos, y `HTTPStatusError` en un 404 -- mismo patrón que `test_atom_client.py`).

Suite completa: **133 passed** (125 previos + 8 nuevos). `ruff check`/`format --check`/`mypy` sin avisos.

Subfase 3.2 completada. Los tres criterios de aceptación se cumplen.
