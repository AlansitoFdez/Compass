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
pesan.

> **Corrección hecha al medir, antes de tocar código.** Al escribir este plan se dio por
> invención un cuarto caso: la fila «Garantía complementaria: ☒No ☐Sí», que no aparecía
> entera en ninguna página. No es invención. La página 4 la contiene, partida por el
> mismo mecanismo: `Garantía` / `☒No ☐Sí` / `complementaria:`, con la fila de casillas de
> la columna derecha metida entre las dos mitades de la etiqueta. O sea que en
> `040-2026-0075` **las nueve citas son fieles** y el 56% publicado es íntegramente
> artefacto del linearizador. El caso de invención real está en otro pliego (`1583900M`,
> ver el Paso 1), y esa es la frontera que hay que saber trazar.

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
   linearizador partió. Demostrado sobre los análisis reales, con las cuatro citas de tabla
   de `040-2026-0075` cayendo del lado bueno y las de `1583900M` —que cita «3 meses» a una
   página que no contiene ninguna de las dos palabras— del otro.
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

### Paso 1 — Medir la fidelidad de citas antes de tocarla

Recalculadas las nueve citas de los seis análisis de la base contra sus PCAP reales, bajo
tres reglas candidatas: substring contiguo (la de hoy), subsecuencia de tokens en orden, y
cobertura de tokens sobre la página citada. Cero llamadas al modelo: las extracciones ya
estaban guardadas y los PDF se bajan de PLACSP.

La subsecuencia ordenada se descartó con los datos delante, y por un motivo que no se veía
antes de medir: el linearizador no sólo **intercala** texto ajeno, también **reordena**. En
`040-2026-0075` la etiqueta «Garantía complementaria:» sale partida en dos con la fila de
casillas en medio, así que el orden de la página (`Garantía`, `☒No ☐Sí`, `complementaria`)
no es el de la cita (`Garantía`, `complementaria`, `☒No ☐Sí`). Ninguna regla basada en
orden sobrevive a eso.

Lo que queda es la cobertura, y como regla binaria sería demasiado laxa. Así que
`verify_citation` deja de devolver un booleano y `check_citation` devuelve **tres**
resultados: `VERIFIED` (aparece literal), `VERIFIED_REORDERED` (todas sus palabras están en
esa página, pero no seguidas) y `UNVERIFIED` (a la página le falta alguna). Sólo la tercera
significa que el modelo escribió algo que el pliego no dice. Y se quedan en clases
separadas a propósito, porque la segunda es evidencia más débil: al ignorar el orden no
puede distinguir `☒No ☐Sí` de `☐No ☒Sí`. `citation_report` las publica por campo.

Resultado sobre los seis análisis:

| expediente | antes | ahora | literales | reordenadas | sin verificar |
| --- | --- | --- | --- | --- | --- |
| `040-2026-0075` | 56% | **100%** | 5 | 4 | 0 |
| `INN 26 002` | 56% | 67% | 5 | 1 | 3 |
| `1583900M` | 22% | 44% | 2 | 2 | 5 |
| `0025-26` | 78% | 78% | 7 | 0 | 2 |
| `1276564F` | 67% | 67% | 6 | 0 | 3 |
| `2026/20` | 50% | 50% | 3 | 0 | 3 |

Lo importante no es que suba, es **que no sube en todas**: tres de los seis no se mueven.
La regla no perdona, discrimina. Y sigue cazando lo que tiene que cazar — `1583900M` cita
«3 meses» a una página 1 que no contiene ni «3» ni «meses», y en otro campo cita el texto
de subcontratación bajo el plazo de presentación. La basura de `2026/20` que provoca el
falso NO APTO tampoco verifica: dos señales independientes apuntando a la misma fila.

El pliego de la captura del README pasa de 56% a 100%, y ese número era el que peor
mentía: las nueve citas eran correctas y el producto publicaba un 56% como señal de
confianza.

### Paso 2 — Un solo cambio de esquema para las dos causas

`certifications` pasa de `list[str]` con una cita compartida a una lista de
`RequiredCertification`, cada una con su `role` (`CertificationRole`: exigida para licitar,
criterio de adjudicación, o papeleo) y **su propia cita**. Desaparece
`certifications_citation`, que era el único campo del esquema que no emparejaba un valor
con su evidencia. `verdict.compute_verdict` sólo bloquea con el primer rol.

`ExecutionDeadline` gana `extensions_allowed` (tri-estado: sí, no, o «el PCAP no lo
aborda») y `extensions_description`. La descripción pasa a ser sólo la duración base. Un
campo obligatorio aparte no se puede contestar por omisión, que es exactamente lo que pasó
con «Durada del contracte: 1 any».

Y `scoring.py`, que era la mitad ciega. El regex viejo (`ISO\d+|CMMI|ENS|IEC\d+|CCN-CERT`)
**se queda**, porque la tolerancia al fraseo que compra es real: «ISO 27000 o equivalente»
e «ISO27000» son la misma exigencia. Lo que cambia es qué pasa cuando no casa: antes el
nombre se **descartaba**, ahora se conserva entero. Con eso, la basura que provocaba los
falsos NO APTO deja de reducirse al conjunto vacío. Además compara por igualdad y no por
contención —una certificación de más es justo lo que se convierte en un falso NO APTO— y
sólo mira las de rol bloqueante, que son las únicas que el veredicto lee. Un décimo campo
puntuable, `execution_deadline.extensions_allowed`, entra en la misma tanda.

Un intento intermedio quedó por el camino y merece quedar escrito: la primera versión
comparaba el nombre normalizado completo, lo que cambiaba una ceguera por una fragilidad
—«ISO 27001» y «UNE-EN ISO 27001:2013 o equivalente» habrían puntuado como distintas—. Un
estándar se identifica por su número, no por la familia que lo prefija.

### Paso 3 — El golden set, re-anotado contra los PCAP y no por conversión

Las 22 certificaciones de las nueve entradas anotadas se re-leyeron en su propio pliego
antes de asignarles rol, en vez de heredar la etiqueta. Las nueve resultaron exigencias
reales de admisión: la cláusula 6.4 de `A41119033-2026/000065-PeAS` («los licitadores
deberán acreditar además el cumplimiento de los requisitos de solvencia técnica y
profesional que se refieren a continuación»), la 10.1.l) de `2545974A`
(«**Obligatoriamente** licitador deberá entregar…»), la «Habilitación» de la cláusula 12.A)
de `SERV-2026000088`, y las cláusulas «se exige la presentación de certificado» de los tres
pliegos de Red.es. O sea que las etiquetas humanas eran correctas: lo que el rol arregla es
la salida del **modelo**, no este fichero.

Las prórrogas salieron de las descripciones que el anotador ya había escrito («prorrogable
hasta dos años más», «sin posibilidad de prórroga»). Cinco entradas no las mencionaban, y
ahí se abrió el PCAP en vez de marcarlas «no se dice» — **y eso cazó dos que habrían
quedado mal etiquetadas**: `A41119033-2026/000065-PeAS` difiere la *duración* al PPT pero
dice en su página 2 «No se ha previsto la posibilidad de prórroga», y `2026000731` dice en
la 16 «Dado que no se prevén prórrogas ni modificaciones». Las dos son `False`, no `None`.
Quedan tres en `None`, que no mencionan prórrogas en ninguna página.

El reparto final: 13 con prórroga, 9 sin ella, 3 sin pronunciarse.

### Paso 4 — La migración: cambia la forma, no inventa lo que nadie leyó

`c3f1ab90d742` reescribe el JSONB guardado. Es a mano y no autogenerada por una razón que
conviene no olvidar: la extracción vive en una columna JSONB sin estructura declarada, así
que un cambio de forma en `PliegoExtraction` es **invisible** para un diff de esquema — y
sin embargo cada fila escrita antes deja de validar en cuanto la aplicación la lee, porque
el modelo es `extra="forbid"`. Sin migración, una instalación existente responde 500 en
cada `GET /analysis` que tenga extracción.

Cada certificación migrada recibe `role = "required_to_bid"`, que es exactamente lo que el
campo viejo decía ser. Es la conversión fiel, y conserva a propósito los veredictos
equivocados que una extracción anterior ya producía: una migración que reetiquetara en
silencio cambiaría veredictos sobre evidencia que nadie ha vuelto a leer. `extensions_allowed`
queda en `null` por lo mismo — «esta extracción nunca contestó a eso» es cierto; una
suposición se leería como una respuesta. La cita compartida va sólo al primer elemento: es
una frase literal, y nombra como mucho a la certificación para la que se escribió.

Comprobado aplicándola: los seis veredictos salen idénticos a los de antes, que es el
criterio de que una migración fiel funciona.

### Paso 5 — El criterio 2, demostrado sobre los datos reales

Con los roles que cada pliego le da a sus certificaciones —leídos de las citas que el
propio modelo dejó guardadas, y del PCAP donde hacía falta— recalculados los seis
veredictos:

| expediente | guardado | con el rol real | |
| --- | --- | --- | --- |
| `INN 26 002` | NO APTO | **APTO CON RESERVAS** | dos certificaciones que sólo puntúan |
| `1276564F` | NO APTO | **APTO** | una declaración responsable, más la cadena `citation` |
| `2026/20` | NO APTO | **APTO** | tres certificados del requerimiento al adjudicatario |
| `1583900M` | NO APTO | NO APTO | exigencias reales (arts. 93 y 94 LCSP) |
| `0025-26` | APTO | APTO | sin certificaciones |
| `040-2026-0075` | APTO CON RESERVAS | APTO CON RESERVAS | sin certificaciones |

Tres falsos NO APTO desaparecen y **`1583900M` sigue siendo NO APTO**, correctamente: su
ANEXO III exige ISO 9001, ISO 27001/ENS e ISO 14001 como solvencia técnica, y el perfil
declara dos de las tres. El arreglo discrimina; no afloja.

**Una desviación del plan, y por qué.** El plan acordado decía migrar a mano los seis
análisis guardados. No se ha hecho, y la demostración de arriba es offline. El motivo
apareció al ir a ejecutarlo: editar a mano la salida del modelo en la base deja una base de
demostración que enseña algo que el modelo no produjo, y de ahí salen las capturas del
README. El límite que el plan ya reconocía —que migrar a mano no demuestra que el modelo
rellene bien el rol— se vuelve peor si además el dashboard finge datos corregidos. Así que
la base conserva lo que el modelo dijo, el README lo dice en sus limitaciones conocidas, y
la corrección real llegará al reanalizar.

### Paso 6 — Dos tests que afirmaban cosas sobre la base ambiente

`test_generate_embeddings_embeds_every_tender_missing_one` exigía `count == 2`, pero
`generate_embeddings` **drena todo el backlog** por diseño: devolvió 245 la mañana en que
se encontró. Pasaba en CI, donde el corpus está vacío, y fallaba en la máquina de quien de
verdad usa Compass. Afirma ahora sobre sus propias dos filas.

`test_golden_set_covers_exactly_the_real_etapa1_survivors` fallaba con cuatro expedientes
sin anotar, los cuatro ingeridos esa misma mañana. La anotación cubre una foto del corpus
del 7 de septiembre, y eso vivía sólo en la prosa; ahora es `ANNOTATED_THROUGH` y la
aserción se acota por `Tender.created_at`. Una licitación ingerida **después** de la foto no
era anotable, así que no prueba que el golden set esté rancio; una anterior y sin etiqueta
sí, y esa alarma sigue en pie.

### Paso 7 — Lo que la documentación decía y ya no era verdad

Números remedidos hoy, con el comando al lado:

| Dato | Antes | Ahora | De dónde sale |
| --- | --- | --- | --- |
| Corpus | 3.583 | 5.363 | `GET /matches`, `funnel.total` |
| Embudo | 3.583 → 71 → 25 → 6 | 5.363 → 104 → 35 → 10 | ídem |
| Sólo vectorial | 3 de 6 | 6 de 10 | `GET /matches`, `lexical_rank` nulo |
| Estado abierto con plazo vencido | 429 de 508 (84%) | 1.636 de 1.740 (94%) | consulta directa |
| Análisis trazados | 35 | 36 | `python -m compass.analysis.cost_report` |
| Tokens por análisis | 31.729–118.486 (60.399) | 22.300–118.569 (59.341) | ídem |
| Tiempo | 36–338 s (159 s) | 20–338 s (155 s) | ídem |
| Tests | 268 | 288 | `uv run pytest` |

Y tres afirmaciones caducadas: el README describía la verificación de citas como una
comparación literal a secas (ahora cuenta los tres resultados y por qué), su apartado de
limitaciones conocidas anunciaba el fallo de `certifications` como pendiente, y
`matching/repository.py` decía que la Etapa 2 era «a later subphase» y atribuía a la 5.4 el
filtro de fecha viva que hizo la 5.3.

**La CSP, escrita en vez de aplazada otra vez.** El comentario de `next.config.ts` la
difería «a la decisión de despliegue de la 5.4», que cerró sin ella. La 5.4 sí resolvió lo
que bloqueaba —dónde está la API para el navegador—, así que la política se escribe a
partir de `NEXT_PUBLIC_API_URL`. Con su límite dicho en el propio comentario: `script-src`
tiene que admitir `'unsafe-inline'` porque Next arranca la hidratación con scripts en
línea, así que esto no detiene una inyección que ya haya conseguido meter un script; lo que
detiene es el paso siguiente —cargar código de otro origen, o mandar algo a uno—, que es el
riesgo real de una aplicación cuyo trabajo es renderizar texto de PDF ajenos.

Verificado levantando la pila entera con las imágenes reconstruidas: la cabecera viaja, la
portada renderiza con su embudo y su tipografía, y la ficha de `2026/20` enseña el análisis
completo con las etiquetas de rol y la cita por certificación.

### El incidente de CI

Los commits `94e4e92` a `4a8b260` salieron en rojo. Al partir el commit del esquema en
código y tests, la reescritura de `scoring.py` se quedó sin añadir al índice: HEAD llevaba
la versión estricta de `_blocking_names` y los tests ya publicados esperaban la de
`_identities`. Corregido en `0e24434`. Lo que lo dejó pasar fue ejecutar los gates sobre el
árbol de trabajo y no sobre lo commiteado; el `git status` antes de cada push es lo que lo
habría cazado.

### Estado al cerrar

Los cinco gates del backend en verde sobre el árbol commiteado: **288 tests**
(283 con la selección de CI), `ruff check`, `ruff format --check`, `mypy --strict` y
`alembic check`. `npm run lint` y `npm run build`, limpios. La pila entera reconstruida y
levantada, y el recorrido comprobado en pantalla.

Criterios 1, 3, 4, 6 y 7, cumplidos. El **2** está demostrado sobre las extracciones
reales pero no escrito en la base, por la desviación razonada en el Paso 5.

El **5 sólo a medias, y conviene decir cuál**. `uv run pytest` sale limpio en local y en
CI, y ningún test vuelve a *afirmar* nada sobre la base ambiente. Pero
`test_generate_embeddings_embeds_every_tender_missing_one` sigue **actuando** sobre ella:
`generate_embeddings` drena todo el backlog por diseño, así que ejecutarlo embebe de paso
las licitaciones que la última ingesta dejó pendientes, y eso se confirma con un `commit()`
que el rollback de la fixture no deshace. Es trabajo que el tic de beat haría igualmente en
menos de quince minutos, así que no corrompe nada — pero no es lo que el criterio pedía, y
acotarlo exigiría darle a la función un alcance que la ruta de arranque en frío necesita
que no tenga. Queda escrito en vez de dado por hecho.

### Lo que queda pendiente, y cuesta una llamada por pliego

Nada de lo anterior demuestra que **el modelo** rellene bien lo que el esquema nuevo le
pide. Eso son dos afirmaciones distintas y sólo una está probada: el código decide bien con
los roles correctos delante (Paso 5), y el esquema ya no admite una respuesta a medias
sobre las prórrogas (Paso 2). Que el modelo elija `required_to_bid` frente a
`award_criterion` en un pliego real, y que describa las prórrogas donde antes las callaba,
exige analizar de nuevo — una petición por pliego, con el nivel gratuito en 50 al día.

Los candidatos están elegidos por lo que demuestran, no al azar:

- **`INN 26 002`**, donde la ISO/IEC 20000 sólo puntúa 6 puntos, y cuyo plazo («1 any»)
  esconde cinco prórrogas. Un solo análisis cubre las dos correcciones.
- **`2026/20`**, cuyos tres certificados salen del requerimiento al adjudicatario.

Con eso, y una corrida de `regression_eval` cuando la cuota lo permita, la fase queda
cerrada del todo.
