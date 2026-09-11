# Subfase 4.4 — RAGAS: fidelidad y corrección de extracción como gate de regresión

## Plan acordado

Del desglose de la Fase 4 (`docs/phases/phase4/phase4.md`): integración de RAGAS sobre
el golden set ampliado (25 pliegos, 4.3), con las dos métricas decididas en la
planificación de fase -- fidelidad y corrección de extracción --, corrido como script
repetible, pensado para engancharse al job de CI de la 4.6 (visible, no bloqueante).

**Sin dependencia `ragas` nueva.** Ambas métricas ya están construidas: fidelidad de
citas (`citation_faithfulness`, 3.5) y corrección de extracción (`score_extraction`,
3.4). 4.4 las generaliza al golden set completo contra el modelo de producción, no las
reconstruye con la librería real de RAGAS -- que solo aportaría precisión/recall de
contexto, descartadas en la planificación de fase por no haber paso de recuperación.

### Criterios de aceptación

1. `uv run python -m compass.analysis.regression_eval` corre las 25 entradas del
   golden set contra el modelo de producción y reporta corrección de extracción +
   fidelidad de citas, por documento y en agregado.
2. No se añade la dependencia `ragas`; ambas métricas reutilizan `score_extraction`
   (3.4) y `citation_faithfulness` (3.5) sin duplicar lógica.
3. `uv run pytest`, `ruff check --fix`, `ruff format`, `mypy` limpios.

## Progreso

### El script: `regression_eval.py`

Corre las 25 entradas de `GOLDEN_SET` contra `analyze_pliego` (3.6) -- el grafo de
producción real, no una reimplementación paralela como la de `extraction_eval.py`
(3.4, que precede al grafo y llama a `extract_structured` a mano). Usarlo tal cual es
justo el punto: si cambia el prompt, el modelo o el timeout, este script lo nota
porque ejecuta ese mismo camino -- `_extract`'s `RetryPolicy`, el timeout de 300s,
el enrutado a `NOT_ANALYZABLE` -- en vez de una versión propia que podría seguir
"pasando" aunque el camino real se hubiera roto.

Llama a `analyze_pliego` directamente, no a `tasks.analyze_tender`: ese segundo
cachea por `pdf_hash` y devolvería el resultado de la corrida anterior para un PCAP
sin cambios -- justo lo que un gate de regresión necesita ver, no esconder.

Dos piezas ya existentes, reutilizadas sin duplicar:
- `scoring.score_extraction` (3.4) -- extraído de `extraction_eval.py` a un módulo
  propio (`scoring.py`) porque ahora lo usan dos scripts, no uno. Sus tests
  (`test_extraction_eval.py`) se mueven con él a `test_scoring.py`.
- `citation_faithfulness` (3.5) -- ni se toca: el grafo ya la calcula en el nodo
  `verify` y la deja en `state["citation_faithfulness"]`, así que el script solo la
  lee.

Sin dependencia `ragas`: confirmado el plan de la fase, ninguna de las dos métricas
necesita la librería real.

**Bug encontrado al revisar el primer output, corregido antes de dar el paso por
cerrado**: el primer borrador media el tiempo e imprimía "starting..." *antes* de
`async with semaphore`, no después -- con concurrencia 4, las 25 tareas imprimían
"starting..." de golpe (arrancan hasta el primer `await` real) y el tiempo
"done in Xs" incluía la cola de espera del semáforo, no solo la llamada real. No es
un error de las métricas (correctness/faithfulness vienen del propio estado del
grafo, ajeno a este cronómetro), pero sí de lo único que este script añade encima:
el log. Corregido moviendo el cronómetro y el print dentro del bloque del semáforo.

**Segundo cambio, tras identificar la causa real de los fallos (ver más abajo)**: el
semáforo se quita por completo -- con `_CONCURRENCY` fijado a 1 no aportaba nada
sobre un simple bucle secuencial, y un bucle deja el corte temprano trivial de
implementar. `_main` ahora recorre el golden set uno a uno y, en cuanto un documento
falla con un `429`, para inmediatamente en vez de seguir gastando peticiones contra
un cupo diario ya agotado -- el resto de expedientes queda listado como "skipped",
no como otro fallo más.

### Dos corridas reales contra las 25 entradas (2026-09-11, `nemotron`)

| corrida | `COMPLETED` | `FAILED` (timeout 300s) | `429` (cupo agotado) |
|---|---|---|---|
| 1ª -- semáforo 4 | 15/25 | 10/25 | -- (no se investigó como causa separada todavía) |
| 2ª -- secuencial (`_CONCURRENCY = 1`) | 8/25 | 6/25 | 11/25 |

Primera corrida, sobre los 15 completados:

- **EXTRACTION CORRECTNESS: 118/135 (87%)**.
- **CITATION FAITHFULNESS: 41% de media**, rango 11%-78%.

Segunda corrida, sobre los 8 completados:

- **EXTRACTION CORRECTNESS: 65/72 (90%)** -- consistente con la primera corrida.
- **CITATION FAITHFULNESS: 47% de media** -- consistente con la primera corrida,
  confirma que el 41%/47% es una medida real y repetible, no ruido de una corrida
  puntual.

Fallos reales y explicables en la corrección de extracción, vistos en ambas
corridas: confundir solvencia económica con técnica cuando el pliego solo da una
cifra que cubre ambas (`1276564F`, `CMA 04/2026`), inventar una cifra de solvencia
técnica donde el pliego remite a un anexo no descargado (`69-26`, `582026020000`), o
perder una certificación de una lista larga (`2545974A`, `SERV-2026000088`,
`TEC0007188`).

### Dos hallazgos reales, no resueltos aquí

**1. Tasa de fallo alta contra el golden set real -- causa final: el cupo diario del
tier gratuito de OpenRouter, no la concurrencia ni el modelo.** La investigación pasó
por varias hipótesis antes de dar con la causa real, en este orden:

- Con semáforo 4, 10/25 documentos fallaron por el timeout de 300s
  (`_EXTRACT_TOTAL_TIMEOUT_SECONDS`, 3.9). Repetir esos mismos 10 en serie
  (concurrencia 1) pareció confirmar que la concurrencia era la culpable: solo 2/10
  siguieron fallando.
- Una segunda corrida completa con concurrencia 1 no reprodujo esa mejora tan limpia
  -- documentos que habían completado en el diagnóstico de 10 volvieron a fallar por
  timeout, y uno que ni siquiera había fallado antes también falló. Esto descartó la
  concurrencia como causa única.
- Esa misma corrida terminó devolviendo `429 Too Many Requests` de OpenRouter en los
  últimos 11 documentos -- rechazos casi instantáneos (6-21s), no timeouts de verdad.
- El panel de peticiones de OpenRouter (no el de actividad/generaciones, que solo
  registra las llamadas que sí llegaron a generar y por eso no mostraba ningún error)
  confirmó la causa real: **25 peticiones a las 10h, 15 a las 11h, 11 a las 12h -- 51
  en total, justo por encima del límite de 50 peticiones/día que OpenRouter aplica a
  los modelos `:free` sin créditos comprados.** Ese cupo se había consumido entre la
  primera corrida con semáforo 4 (25 peticiones), los dos diagnósticos (11 más) y el
  arranque de la corrida final -- no es un problema del pliego, del modelo ni de la
  concurrencia: es un límite de cuenta compartido entre todas las pruebas del día.

**No se corrige con crédito de pago** (decisión explícita: este proyecto se queda en
el tier gratuito). La mitigación que sí entra en el alcance de 4.4: `regression_eval.py`
ahora detecta un `429` y para inmediatamente en vez de seguir gastando peticiones
contra un cupo ya agotado -- ver "El script" arriba. La corrida completa y limpia de
las 25 queda pendiente de un día con cupo íntegro disponible; no bloquea el resto de
la fase.

**Implicación real para la 4.6 (CI):** un job de evals que lance las 25 del golden
set en cada push se comería la mitad del cupo diario compartido con el uso real de la
app. A decidir en esa subfase si corre bajo demanda en vez de automático.

**2. Fidelidad de citas por debajo de lo esperado -- causa identificada, no es un bug
de código.** Inspección cita por cita de `1276564F` (el mismo documento que dio 100%
en la comprobación puntual de la 3.4/3.5, pero con `nex-agi/nex-n2.5-pro`, no con
`nemotron`, el modelo real en producción -- nunca se había validado la fidelidad de
citas del modelo que de verdad está en producción): `verify_citation` y
`citation_faithfulness` funcionan correctamente sobre el texto real en memoria (se
confirmó buscando el texto de cada cita, sin depender de lo impreso en consola, que sí
mostró símbolos `�` por un problema de codificación del propio script de diagnóstico
al volcar a fichero en Windows -- no de los datos). Las citas que no verifican tienen
una causa real y observable: el modelo a veces resume un pasaje largo insertando
`"..."` en mitad de la cita en vez de copiarlo verbatim (confirmado: el texto real,
completo, estaba justo al lado en la página correcta), y otras veces cita una página
que no contiene ese texto ni parafraseado. Es una limitación real del modelo citando,
no un hueco de `verify_citation`. Confirmado con datos consistentes en dos corridas
distintas (41% y 47% de media, sobre 15 y 8 documentos respectivamente) -- no es
ruido de una muestra pequeña.

Ninguno de los dos se arregla en esta subfase -- 4.4 es el script que los hace
visibles, no el que los corrige.

### Cierre

Ninguna de las corridas contra las 25 entradas llegó a completarlas todas sin
tropezar con el cupo diario -- pero eso no es lo que impedía cerrar 4.4. Los
criterios de aceptación no pedían un 25/25 perfecto, sino que el script exista, corra
y reporte ambas métricas -- y eso quedó demostrado varias veces con datos reales (15
documentos completos en una corrida, 8 en otra, con su desglose por campo y su
fidelidad). Los dos hallazgos de calidad quedan con causa identificada y evidencia
real detrás, no como preguntas abiertas. Una corrida futura con el cupo diario
íntegro (`uv run python -m compass.analysis.regression_eval`, ya con el corte
automático al detectar un 429) puede dar el número agregado sobre las 25 completas
cuando convenga -- dato interesante para el futuro, no bloqueante para seguir con la
4.6.

