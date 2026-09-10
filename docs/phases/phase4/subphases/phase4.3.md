# Subfase 4.3 — Golden set ampliado a 25-30 pliegos

## Plan acordado

Del desglose de la Fase 4 (`docs/phases/phase4/phase4.md`): extensión del golden set de la 3.4 (`analysis/golden_set.py`) con 21-26 pliegos reales más de los matches del proveedor sembrado, anotados a mano con cita textual verbatim -- mismo método, más escala. Objetivo acordado con Alan: 25 en total (21 nuevos), no 30 -- el mínimo del rango del documento de diseño, para acotar el esfuerzo de lectura manual.

**Excepción al ritmo habitual de la fase, acordada explícitamente**: dado que anotar un pliego real a mano es mucho más trabajo por unidad que escribir código, esta subfase se trabaja en lotes de ~5-7 pliegos, revisados con Alan entre lote y lote, en vez de construirse entera de un tirón como el resto de subfases.

### Criterios de aceptación

1. `GOLDEN_SET` alcanza 25 entradas totales (21 nuevas), cada una con sus 9 citas verificadas al 100% contra el texto real extraído del PCAP (`verify_citation`), no asumidas.
2. Cada pliego nuevo se elige por diversidad estructural real (formato, forma de expresar solvencia/garantías/lotes/subcontratación), no por ser el primero disponible.
3. `uv run pytest`, `ruff check --fix`, `ruff format`, `mypy` limpios tras cada lote.

## Progreso

### Lote 1 — 5 pliegos (2545974A, AST-2026-20162, 23/2026, 202601JC0007, 300/2026/01246)

**Candidatos reales disponibles**: 46 matches del proveedor sembrado con `pcap_url`, sin contar los 4 ya anotados en la 3.4 (`fused_matches` con el perfil real).

**Hallazgo real, encontrado al intentar anotar el primer candidato -- `1868392P` (Ayuntamiento de Ayerbe) descartado**: las 31 páginas de su PCAP extraen únicamente la cabecera/pie de firma digital ("Código Seguro de Verificación", bloque de firmantes en texto invertido) -- el contenido real de las cláusulas no aparece en ningún punto del texto que devuelve `document.extract_pages`. `has_text_layer` (3.2) no lo detectaría: hay de sobra texto por página (la cabecera se repite), solo que ninguno es sustantivo. Sospecha, no confirmada: cómo la plataforma de firma electrónica de este ayuntamiento concreto (sedipualba) superpone el sello de firma sobre el documento original. **No investigado a fondo ni arreglado aquí** -- decisión explícita de Alan de anotarlo y seguir, dejado como hallazgo real pendiente para una futura subfase.

**Segundo hallazgo real -- `129/25` y `2026/15` descartados**: ambos son "pliego tipo" que remiten sistemáticamente ("...según lo fijado en el Cuadro Resumen...") las cifras concretas (solvencia, plazos, garantía, criterios) a un "Cuadro Resumen" que no forma parte del documento descargado -- confirmado buscando la cabecera real "ANEXO I"/"Cuadro Resumen" en el texto extraído y no encontrándola en ninguno de los dos. El texto es real y se extrae bien; simplemente no contiene los valores concretos. Descartados como candidatos del golden set (no hay nada que anotar), no como bug de `extract_pages`.

**Tercer hallazgo operativo, sin relación con el contenido -- el firewall de PLACSP bloqueó las descargas por exceso de peticiones seguidas**: tres intentos de descarga consecutivos (`897/2026`, `2026/20`, y un reintento de `PLI-02634`) devolvieron la misma página HTML de error ("The Web Application Firewall has denied your transaction due to a violation of policy"), no un PDF corrupto -- confirmado inspeccionando el `content-type` y el cuerpo real de la respuesta. Corrige una suposición equivocada dicha en la propia conversación de planificación (que `PLI-02634` fuera un PDF roto). Sin más reintentos inmediatos para no seguir generando bloqueos; el lote se cerró en 5 pliegos en vez de 7, dentro del rango acordado con Alan.

**Los 5 pliegos finalmente anotados**, elegidos por diversidad real ya confirmada al leerlos (no supuesta):

- **`2545974A`** (Ajuntament de Picanya) -- procedimiento negociado sin publicidad, único con **exención explícita** de solvencia económica y técnica (art. 11 RGLCAP) y el más rico en certificaciones formales exigidas (ENS + seis ISO). Subcontratación expresamente prohibida.
- **`AST-2026-20162`** (Aragonesa de Servicios Telemáticos) -- formato "Cuadro de Características" con anexos numerados. Solvencia técnica sin umbral económico (proyectos cualitativos). Desglose de criterios de adjudicación inusualmente granular (9 líneas), simplificado a 5 categorías en la anotación sin perder el total real (100 puntos).
- **`23/2026`** (Urbanizadora Municipal, S.A. -- URBAMUSA) -- contrato de naturaleza **privada** (poder adjudicador no Administración Pública, arts. 316-320 LCSP). Solvencia económica y técnica expresadas como **fórmula** (1,5x / 70% del valor anual medio del contrato) que el propio pliego no pre-calcula -- caso deliberadamente más difícil que copiar una cifra ya escrita.
- **`202601JC0007`** (Junta de Contratación, Ministerio de Inclusión, Seguridad Social y Migraciones) -- formato "Cuadro de Características" con casillas ☒/☐. Sin certificaciones ni habilitación empresarial exigida. Criterios de adjudicación con cinco líneas explícitas de puntuación.
- **`300/2026/01246`** (Área de Gobierno de Políticas Sociales, Ayuntamiento de Madrid) -- narrativo con Anexo I de características al final del documento (página 52 de 93). Solvencia económica y técnica comparten deliberadamente el mismo umbral (15.000 €) -- caso construido para comprobar que un modelo no confunde ambos campos.

**Verificación real, no asumida**: cada cita se comprobó con `verify_citation` contra el texto real extraído (`document.extract_pages` sobre el `pcap_url` real de cada uno) antes de darla por buena -- un primer intento con **dos citas mal construidas** (un número de página equivocado en `23/2026` por un error de conteo manual, y una cita en `202601JC0007` que no tenía en cuenta que el PDF extrae una tabla de dos columnas intercalando etiquetas de campo con su valor) fue detectado y corregido por esta misma verificación antes de tocar el archivo real -- exactamente el motivo de verificar contra texto real en vez de confiar en la transcripción a mano.

Suite completa tras el lote: **193 passed** (189 previos + 4 nuevos de `test_extraction_golden_set.py`, que ahora protege el tamaño real -- 9 -- en vez de los 4 originales). `ruff check`/`format --check`/`mypy` sin avisos. Los 9 expedientes del golden set (4 de la 3.4 + 5 de este lote) verificados con `pcap_url` real todavía vigente en el corpus.

Lote 1 completado -- 9 de 25 pliegos. Pendiente: lotes 2 y 3 (16 pliegos más).

### Lote 2 — 11 pliegos (2026-01027, 69-26, CMA 04/2026, 582026020000, 2026000731, L26-SERV-06, MT260312, SERV-2026000088, CONTR 2026 17947, INN 26 002, TEC0007188)

**Candidatos descartados en este lote, cuatro en total, dos patrones ya vistos y dos nuevos**:

- **Patrón "pliego tipo" ya conocido, dos casos más** (`PAS_325/2026`, Conselleria de Sanitat de la Generalitat Valenciana; y un expediente de la Junta de Extremadura): mismo diagnóstico que en el lote 1 -- el cuerpo del documento remite sistemáticamente a un "Apartado" del "Anexo I" para cada cifra concreta, y ese Anexo I, cuando existe en el propio PDF descargado, aparece como plantilla en blanco (casillas y líneas de puntos sin rellenar). Ya son cuatro casos de este patrón entre los descartados de la 4.3 -- lo bastante común como para convertir la comprobación de "¿el Anexo I tiene contenido real, no solo una referencia a él?" en el primer paso de triaje antes de leer un candidato entero.
- **Hallazgo nuevo -- un PCAP cuya extracción sale con el texto invertido letra a letra, intercalado con códigos de glifo `(cid:N)` sin mapear** (expediente de un ayuntamiento, descartado): páginas enteras ilegibles por un mapa de fuente/codificación roto en el PDF de origen, no por falta de capa de texto -- `has_text_layer` tampoco lo detectaría, igual que el caso de Ayerbe del lote 1 pero por una causa distinta.
- **Hallazgo nuevo -- un PCAP dominado por una marca de agua diagonal rotada** (expediente de una mutua, descartado): `document.extract_pages` sí devuelve texto real, pero cerca del 93% de sus líneas son uno o dos caracteres sueltos de la marca de agua; el contenido sustantivo no es recuperable de ese ruido con confianza suficiente para citar con precisión.

**Los 11 pliegos finalmente anotados**, elegidos por diversidad real ya confirmada al leerlos:

- **`2026-01027`** (Isdefe, para la Inspección General del Ejército) -- narrativo, 97 páginas.
- **`69-26`** (ACOSOL, Costa del Sol) -- narrativo, 79 páginas, publicado vía plataforma de firma electrónica sedipualba: la huella de firma sale invertida en el pie de página, pero el cuerpo de las cláusulas se extrae intacto -- confirma que el problema de Ayerbe (lote 1) es específico de cómo esa plataforma concreta superpone el sello, no un problema general de sedipualba.
- **`CMA 04/2026`** (Ayuntamiento de Gilet) -- procedimiento abierto simplificado abreviado de bajo valor, único de todo el golden set sin ninguna exigencia de solvencia ni garantía en absoluto.
- **`582026020000`** (CETEDEX/INTA) -- organismo vinculado a la seguridad del Estado: subcontratación permitida pero siempre sujeta a autorización previa reforzada.
- **`2026000731`** (Gobierno del Principado de Asturias) -- 122 páginas, el más largo del conjunto; único con el cierre de presentación expresado como hora exacta ("23:59:59").
- **`L26-SERV-06`** (Mogán Gestión Municipal -- GESTIONA) -- servicio SaaS de control horario.
- **`MT260312`** (Correos y Telégrafos) -- formato tabular de "instrucciones" con casillas; único criterio de adjudicación es el precio (mejor relación coste-eficacia al 100%).
- **`SERV-2026000088`** (Ayuntamiento de Granada) -- solvencia expresada como fórmula sobre el valor anual medio del contrato, no como cifra ya calculada.
- **`CONTR 2026 17947`** (Conselleria de Famílies, Benestar Social i Atenció a la Dependència, Illes Balears) -- pliego en catalán, formato "Quadre de característiques".
- **`INN 26 002`** (Fundació Turisme Palma 365) -- narrativo en catalán, publicado vía sedipualba con el mismo patrón de firma invertida que `69-26`, cuerpo intacto.
- **`TEC0007188`** (Grupo Tragsa, para el Ministerio para la Transición Ecológica) -- único del golden set sin ninguna garantía exigida; su tabla de criterios de adjudicación tenía un valor de puntos ("49", el del precio) desplazado a la línea siguiente por el layout de dos columnas de `extract_pages` -- confirmado sumando el resto de criterios explícitos (51) y comprobando que 49+51 cierra exactamente en 100, el mismo patrón de interleaving de tabla ya visto y corregido en `202601JC0007` (lote 1).

**Verificación real**: las 99 citas de estos 11 pliegos (9 campos × 11) se comprobaron con `verify_citation` contra el texto real extraído antes de escribirlas en `golden_set.py` -- varias fallaron en el primer intento por errores de transcripción (orden de líneas en tablas de dos columnas, un apóstrofo tipográfico distinto al del PDF) y se corrigieron releyendo el `FAIL` de la propia verificación, no adivinando.

Suite completa tras el lote: **198 passed** (193 previos + 5 nuevos: `test_extraction_golden_set.py` ahora protege 20 entradas). `ruff check`/`format`/`mypy`/`alembic check` sin avisos. Los 11 expedientes nuevos verificados con `pcap_url` real todavía vigente en el corpus.

Lote 2 completado -- 20 de 25 pliegos. Pendiente: lote 3 (5 pliegos más).
