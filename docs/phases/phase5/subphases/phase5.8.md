# Subfase 5.8 — Revisión completa de la fase

## Plan acordado

Del desglose de la Fase 5 (`docs/phases/phase5/phase5.md`): repaso exhaustivo de todo lo
construido en 5.1-5.7, con verificación empírica contra la aplicación en marcha y el
corpus real — no solo lectura de código. Mismo patrón que la 1.11, la 2.7, la 3.9 y la
4.7.

Dos puntos que las propias subfases dejaron anotados para aquí:

1. El campo `certifications`, que produce falsos NO APTO (5.5 y 5.7).
2. Las descripciones que se quedan cortas donde el esquema pide más (5.6).

### La línea base, medida antes de tocar nada

Verde: `ruff check`, `ruff format --check`, `mypy --strict`, `alembic check`,
`npm run lint`, `npm run build`.

Rojo: `uv run pytest` — **2 failed, 266 passed**. Los dos fallan solo en local y pasan en
CI, que es exactamente el problema (ver hallazgo D).

### Los hallazgos que esta subfase tiene que atacar

**A. `certifications` produce falsos NO APTO, y el gate que debería cazarlo es ciego por
construcción.**

Los seis análisis de la base, con su campo literal:

| expediente | `certifications` | qué es en realidad |
| --- | --- | --- |
| `INN 26 002` | ISO 27001, **ISO 20000** | la 20000 sólo *puntúa* 6 puntos como criterio de adjudicación |
| `2026/20` | 3 × «Certificación positiva… al corriente de obligaciones tributarias / SS» | papeleo; su propia cita lo delata: «Cláusula 27ª. Requerimiento a la primera empresa clasificada» |
| `1276564F` | «Declaración responsable ANEXO III…», **`citation`** | papeleo, más la cadena literal del nombre de un campo del esquema |
| `1583900M` | ISO9001 / ISO27001-ENS / ISO14001 | por comprobar si exigidas o puntuadas |
| `0025-26` | `[]` | limpio |
| `040-2026-0075` | `[]` | limpio |

Dos causas, no una:

1. **El esquema no tiene dónde decir *por qué* aparece una certificación.**
   `certifications: list[str]` con **una sola** `certifications_citation` para toda la
   lista — es el único campo del esquema que no empareja valor con cita. Y `verdict.py`
   bloquea con *cada* cadena de esa lista, sin distinguir un requisito de admisión de un
   criterio puntuable o del papeleo que presenta cualquier licitador.
2. **El gate de regresión no puede verlo.** `scoring._cert_tokens` sólo reconoce
   `ISO\d+|CMMI|ENS|IEC\d+|CCN-CERT`. Ejecutado contra la basura real devuelve `set()`, y
   con `expected=[]` el campo puntúa **correcto**. O sea que los 25 pliegos del golden set
   pueden llevar esta basura y `regression_eval` sale verde: lo que actúa (bloquear con
   cualquier cadena) y lo que se mide (sólo tokens ISO) no son lo mismo.

**B. `citation_faithfulness` castiga al modelo justo donde acierta.**

`040-2026-0075` —el pliego de la captura del README, 91 páginas— puntúa **56%**: fallan
`award_criteria`, `guarantees`, `subcontracting` y `lots`. Recomprobadas las nueve citas
una a una contra el PDF real, el motivo no es invención. El PCAP mete todo lo decisivo en
el Cuadro de Características, una tabla de dos columnas que `pdfplumber` lineariza así:

```
A excepción de aquellas tareas críticas que deban ser ejecutadas
Subcontratación: necesariamente por el contratista principal y que se indican a
```

La etiqueta de la columna izquierda cae **dentro** de la frase de la derecha. El modelo
reconstruyó la celda correctamente; `verify_citation` exige substring contiguo, así que
falla. Y el valor extraído es correcto en los tres casos de tabla.

El sesgo es sistemático y va **contra** el modelo, precisamente en las páginas que más
pesan. Pero no todo es layout, y esa es la otra mitad del problema: en `guarantees` el
modelo añadió una fila («Garantía complementaria: ☒No ☐Sí») que no aparece en ninguna
página del documento. Eso sí es invención — y hoy el mismo número la mezcla con lo
anterior, así que no distingue «el modelo se lo inventó» de «pdfplumber desordenó una
tabla».

**C. Las descripciones se quedan cortas donde el esquema pide más.**

Lo cazó el eval de la 5.6 en su primera corrida: «Durada del contracte: 1 any» en un
contrato con cinco prórrogas, con el esquema pidiendo ya «duration **and any
extensions**». Los números del propio anuncio lo confirman sin leer el pliego: 10.679 € de
presupuesto contra 52.954 € de valor estimado.

**D. Dos tests rojos en local que pasan en CI.**

- `test_generate_embeddings_embeds_every_tender_missing_one` afirma `count == 2`, pero
  `generate_embeddings` **drena todo el backlog**: hoy devuelve 245. No lleva
  `real_corpus`, así que pasa en CI (base vacía) y falla en la máquina de quien usa
  Compass de verdad. Y como la función hace `commit()` por lotes, el rollback de la
  fixture no lo deshace: el test **escribe en la base de desarrollo**.
- `test_golden_set_covers_exactly_the_real_etapa1_survivors` falla con cuatro expedientes
  nuevos sin anotar. Ahí la alarma funciona como se diseñó — pero significa que
  `uv run pytest` no sale limpio nunca más, y el README anuncia 268 tests en verde.

**E. Deriva de documentación y comentarios.**

- El embudo real hoy es **3.845 → 106 → 38 → 10**; el README dice 3.583 → 71 → 25 → 6.
- `matching/repository.py` sigue diciendo que la etapa 2 es «a later subphase», y atribuye
  a la 5.4 el filtro de fecha viva que el resto de la documentación sitúa en la 5.3.
- `next.config.ts` aplaza la CSP «a la decisión de despliegue de la 5.4», que cerró sin
  ella.

### La restricción que ordena el trabajo: la cuota de OpenRouter

El nivel gratuito son 50 peticiones al día y se renueva a las 00:00 UTC. No hay forma de
leer el contador: `GET /api/v1/key` devuelve `usage_daily` en **dólares**, y los modelos
`:free` cuestan 0 €, así que siempre marca 0.

Así que el plan no se apoya en tener cuota. Y resulta que casi nada la necesita:

| Trabajo | Peticiones |
| --- | --- |
| B — separar layout de invención en la verificación | **0** (se recalcula sobre las extracciones ya guardadas; los PDFs se bajan de PLACSP) |
| A — esquema, `verdict.py`, `scoring.py`, tests | **0** |
| A — pasar los 6 análisis guardados a la forma nueva | **0** (migrados a mano) |
| C — plazo y prórrogas en campos separados | **0** |
| D — los dos tests | **0** |
| E — documentación, comentarios, números, CSP | **0** |
| Comprobar que el modelo rellena bien el campo nuevo | **1 por pliego** |
| `regression_eval` completo / `freetext_eval` | 25 / 14 por pliego — fuera |

**Dos decisiones que salen de ahí.**

La primera: **los 6 análisis guardados se migran a mano, no se reanalizan.** El rol de
cada certificación ya está en la cita que hay almacenada — la de `2026/20` dice
literalmente «Requerimiento a la primera empresa clasificada», la de `INN 26 002` dice
«s'atorgaran 6 punts en el cas de disposar». No es adivinar: es anotar desde la evidencia
que el propio modelo dejó escrita, y de paso demuestra que la información *estaba ahí* y
lo que faltaba era una casilla donde ponerla.

La segunda: **A y C se hacen como un solo cambio de esquema.** Los dos tocan
`PliegoExtraction` y los dos invalidan lo guardado (`extra="forbid"`); separarlos
significaría migrar las seis filas dos veces y tocar el golden set dos veces.

Y un límite que se escribe aquí para no colárnosla luego: migrar a mano demuestra que **el
código decide bien** —que el falso NO APTO de `2026/20` desaparece—, pero **no** demuestra
que el modelo rellene bien el campo nuevo. Son dos afirmaciones distintas. La segunda
queda pendiente de una sola llamada, explícitamente marcada como tal.

### Criterios de aceptación

1. **B:** `citation_faithfulness` distingue una cita inventada de una cita correcta que el
   linearizador partió. Demostrado sobre los análisis reales, con los dos casos de
   `040-2026-0075` —`subcontracting` (tabla) y `guarantees` (fila inexistente)— cayendo en
   lados distintos.
2. **A:** el falso NO APTO de `2026/20` desaparece, y `verdict.py` sólo bloquea con
   certificaciones exigidas para licitar. Verificado contra la base real, no sólo en tests.
3. **A:** `scoring.py` deja de ser ciego a la basura: un `certifications` con papeleo donde
   se anotó `[]` puntúa **incorrecto**. Con un test que lo fija.
4. **C:** el esquema no admite una respuesta a medias sobre el plazo: duración base y
   prórrogas son campos distintos.
5. **D:** `uv run pytest` sale limpio en local y en CI, y ningún test escribe en la base de
   desarrollo por sorpresa.
6. **E:** ningún número ni comentario del repositorio contradice lo que la aplicación hace
   hoy.
7. Los cinco gates limpios: `pytest`, `ruff check`, `ruff format --check`, `mypy`,
   `alembic check`, más `npm run lint` y `npm run build`.

## Progreso
