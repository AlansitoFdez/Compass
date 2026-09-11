# Subfase 5.2 — Revisión completa de la aplicación y corrección de los hallazgos

## Plan acordado

Con el dashboard de la 5.1 recién cerrado y antes de desplegar, una revisión completa de
las dos mitades del producto —backend y dashboard— buscando lo que los tests no miran:
funcionalidad rota en datos reales, carreras, límites de seguridad y estados sin salida.

El punto de partida era sano: 209 tests en verde, `ruff` y `mypy --strict` limpios. Los 37
hallazgos de la revisión salieron de ejercitar la API levantada contra el corpus real
(3.583 licitaciones, 508 en plazo), no de leer código.

**Alcance decidido al arrancar**: esta subfase corrige los hallazgos del backend. La
reestructuración y el rediseño del dashboard —trece hallazgos propios, con su propio
criterio de "hecho"— se llevan a la 5.3, que por eso desplaza el despliegue a la 5.4, el
digest por email a la 5.5 y la revisión de fase a la 5.6.

### Los hallazgos, por gravedad

**Críticos**

- **C1 — El análisis de pliegos no funciona en el 62 % de las licitaciones en plazo.** El
  router de análisis declara `/tenders/{expediente}/analyze|analysis` con el convertidor
  por defecto, que corta en la primera barra, mientras la ficha usa `{expediente:path}`.
  Los expedientes reales de PLACSP llevan barras dentro: 2.282 de los 3.583 del corpus,
  315 de las 508 en plazo. Verificado contra la API levantada con `2026/SSV/000804`:
  `GET .../analysis` devuelve el 404 de la ficha ("Tender not found") y
  `POST .../analyze` devuelve 405. El dashboard traduce lo primero a "nadie ha pedido
  todavía el análisis" y lo segundo a "no se pudo encolar": el botón no funciona y nada
  explica por qué.
- **C2 — La API sólo funciona en Windows por un efecto colateral de `--reload`.** psycopg
  en modo asíncrono exige un event loop de tipo *selector*; el de Windows por defecto es
  `ProactorEventLoop`. Todos los puntos de entrada lo resuelven —`alembic/env.py`, las
  tres tareas Celery, `seed.py`, `conftest.py`— menos el de la API. Sin `--reload`, todo
  endpoint que toque Postgres devuelve 500 con `InterfaceError`. Pesa más de lo que
  parecía al encontrarlo: Compass se ejecuta en la máquina de quien lo usa, así que
  Windows no es sólo el entorno de desarrollo, es un entorno de destino — y la forma
  natural de levantar la API fuera de desarrollo es precisamente sin `--reload`.
- **C3 — `GET /matches` ejecuta el modelo de embeddings dentro del event loop.**
  `vector_matches` embebe la descripción del proveedor de forma síncrona en cada
  petición. Medido: 6,21 s la primera (carga de ~570 MB de pesos), 0,50 s las siguientes,
  y `/health` pasa de 0,21 s a 0,33 s con cuatro `/matches` en vuelo. Además duplica el
  modelo en memoria entre API y worker.

**Reclasificados: la superficie de red es local**

Compass se ejecuta en la máquina de quien lo usa, no como servicio alojado. Eso rebaja dos
hallazgos que en un despliegue público serían bloqueantes, y conviene dejar escrito por qué
se rebajan, no que desaparezcan sin más:

- **C4 → informativo — La API no tiene autenticación ni límite de peticiones.** El panel
  de análisis la llama desde el navegador y `POST /analyze` encola una llamada a un LLM
  contra una cuota gratuita de 50 peticiones diarias. Con todo en `localhost`, el único
  que puede agotarla es el propio usuario. Queda anotado como condición: el día que la API
  escuche fuera de `localhost`, esto vuelve a ser crítico y hay que resolverlo antes.
- **C5 → medio — Redis sin contraseña y Postgres con credenciales por defecto.**
  `docker-compose.yml` publica los puertos sin prefijo `127.0.0.1:`, así que quedan
  accesibles desde la red local, no sólo desde la máquina. En un portátil conectado a una
  wifi ajena eso sigue siendo un Redis sin autenticar al alcance de cualquiera — y Redis
  aquí guarda los *checkpoints* de ingesta, no sólo la cola. El arreglo es de tres líneas
  y no tiene contrapartida, así que se hace igual.

**Graves**

- **G1 — Un análisis puede quedarse en `in_progress` para siempre.** `analyze_tender`
  confirma ese estado antes de llamar al grafo; si el worker muere entre los dos
  `commit`, nada vuelve a tocar la fila. El lock de Redis caduca a los 900 s, la fila no.
  El panel, además, hace *polling* sin tope.
- **G2 — Un análisis cacheado se vuelve invisible si dos expedientes comparten el PDF.**
  `TenderAnalysis` se escribe por `pdf_hash` y se lee por `expediente`. En un acierto de
  caché con otro expediente, la tarea no escribe nada y `GET /analysis` devuelve 404 para
  siempre: el usuario pulsa, el POST responde 202 y la pantalla vuelve al botón.
- **G3 — `GET /matches` devuelve `total = len(items)`.** Con `limit=20` dice 20; con
  `limit=5`, 5. La portada imprime "{total} resultados del embudo", así que el dato que
  cuenta el argumento del producto es siempre el tamaño de página.
- **G4 — El PCAP se descarga entero en memoria, sin límite de tamaño, y dos veces.** Una
  para calcular el hash de caché y otra dentro del grafo. PLACSP publica pliegos con
  anexos escaneados de cientos de megas, y con `--pool=solo` un worker muerto por memoria
  se lleva también la ingesta diaria.
- **G5 — El dashboard no tiene ningún límite de error.** No existen `error.tsx`,
  `not-found.tsx` ni `loading.tsx`: la API caída, o el 404 previsto de "perfil sin
  sembrar", producen la pantalla de error genérica de Next.
- **G6 — Carrera entre dos expedientes con el mismo `pdf_hash`.** El lock es por
  expediente, así que ambos crean la misma clave primaria y el segundo `commit` revienta
  con `IntegrityError`. Hoy lo tapa `--pool=solo`; aparece al pasar a `prefork` en Linux.
- **G7 — El texto crudo de una excepción acaba en el navegador.** `str(exc)` del límite de
  error del grafo se guarda en `error_message` y se pinta tal cual.

**Medios**

`setInterval` con callback asíncrono en el *polling* (M1); el error del panel que no se
limpia tras un reintento con éxito (M2); enlaces a fichas sin codificar mientras el
cliente de API sí codifica, con 407 expedientes que contienen espacios (M3); un `assert`
como comprobación de dimensiones en `embed_texts`, que desaparece con `python -O` (M4);
"el análisis más reciente" ordenado sin desempate sobre un `created_at` con `now()`
congelado por transacción (M5); `next.config.ts` sin cabeceras de seguridad (M6);
`to_tsquery` con una descripción sin lexemas, que devuelve 500 (M7); el ZIP temporal de
~200 MB que el cargador histórico deja atrás si la descarga se corta (M8); el cliente HTTP
síncrono dentro de una corrutina en la ingesta diaria (M9); CLAUDE.md tres fases por
detrás del repositorio (M10); el modo *offline* de Alembic, que generaría SQL con la
contraseña enmascarada (M11); y la ausencia de `generateMetadata` en la ficha, que hace
que todo enlace compartido se previsualice igual (M12).

### Criterios de aceptación

1. `GET /tenders/{expediente}/analysis` y `POST /tenders/{expediente}/analyze` responden
   al endpoint correcto para un expediente con barras, espacios y acento — no el 404 de la
   ficha ni un 405. Verificado contra la API levantada con un expediente real del corpus.
2. Tests que fijan las cuatro rutas (`/tenders`, `/tenders/{exp}`, `.../analysis`,
   `.../analyze`) con un expediente con la forma real de PLACSP, no sólo con uno simple.
3. `uv run pytest`, `ruff check`, `ruff format --check` y `mypy` limpios, y CI en verde.

## Progreso

### C1 — Las rutas de análisis, contra expedientes reales

El router de análisis declaraba su prefijo como `/tenders/{expediente}`. El convertidor
por defecto de Starlette no admite barras, así que para cualquier expediente que llevara
una, ninguna de sus dos rutas casaba. La petición caía entonces en
`GET /tenders/{expediente:path}` —la ficha, registrada después— que respondía lo que
sabía responder: `Tender not found` para la lectura del análisis, y `405 Method Not
Allowed` para el `POST`, porque esa ruta no admite ese método.

Medido contra la API levantada y el corpus real antes de tocar nada, con `2026/SSV/000804`:

```
GET  /tenders/2026/SSV/000804/analysis  -> 404 {"detail":"Tender not found"}
POST /tenders/2026/SSV/000804/analyze   -> 405 {"detail":"Method Not Allowed"}
```

Y el alcance, consultado sobre la base de datos: **2.282 de 3.583 expedientes llevan
barra, 315 de las 508 en plazo**. O sea, el agente analista —la pieza cara y diferencial
del producto— estaba apagado en dos de cada tres licitaciones que el dashboard enseña.

El arreglo es declarar el prefijo como `/tenders/{expediente:path}`, igual que la ficha.
El convertidor `path` es ávido, pero sigue anclado por los sufijos literales `/analysis`
y `/analyze`, así que no se puede tragar el propio sufijo que lo delimita. El orden de
registro que fijó la 5.1 —análisis antes que `tenders`— sigue siendo necesario y no
cambia: sin él, la ficha volvería a contestar por las dos rutas.

Verificado después sobre el mismo expediente real:

```
GET  /tenders/2026/SSV/000804/analysis  -> 404 {"detail":"This tender has not been analyzed yet"}
POST /tenders/2026/SSV/000804/analyze   -> 202 {"detail":"Analysis queued for 2026/SSV/000804"}
```

**Por qué la suite no lo vio.** El test que fija el orden de los routers existía desde la
5.1, y es correcto — pero usaba `TEST-EP-DOES-NOT-EXIST`, sin barras, que es justo el
único caso que seguía funcionando. Lo mismo los cinco tests de los endpoints de análisis.
La lección no es que faltara un test, es que los datos de prueba no tenían la forma de los
datos reales: un identificador inventado sin barras nunca iba a ejercitar el convertidor.

Los tests nuevos usan una constante con la forma real de un expediente de PLACSP —barras,
espacio y acento a la vez, como `2026/S-ABT/0000025771 - Gestión de expedientes`— y
recorren con ella las dos rutas de análisis. El test de orden de routers pasa a comprobar
también el caso con barras. Los tres fallan contra el código anterior y pasan contra el
actual, comprobado revirtiendo el cambio.

### C2 — La API sólo arrancaba bien por un efecto colateral

La causa no era la que parecía. `uvicorn.Server.run()` no usa la *policy* global de
asyncio: pasa `config.get_loop_factory()` explícitamente a `asyncio.run`, y esa fábrica
(`uvicorn/loops/asyncio.py`) devuelve `ProactorEventLoop` en Windows **salvo cuando
uvicorn va a lanzar un subproceso**. Una fábrica explícita gana a cualquier *policy*, así
que fijar la policy —el arreglo que usan los otros cinco puntos de entrada— aquí no habría
servido de nada.

Esa excepción del subproceso es exactamente por qué `--reload` funcionaba: el recargador
lanza un subproceso, y esa rama sí devuelve `SelectorEventLoop`. La API servía tráfico
correctamente sólo por estar en modo desarrollo.

El arreglo es un punto de entrada propio, `python -m compass`, que construye el servidor y
elige el loop él mismo: `SelectorEventLoop` en Windows, y lo que uvicorn habría elegido en
cualquier otro sitio, para que una instalación Linux siga usando uvloop igual que antes.
`--reload` se delega a uvicorn sin tocar nada, porque esa rama ya era correcta. El comando
documentado en CLAUDE.md cambia en consecuencia.

Los tests fijan la elección con `sys.platform` parcheado en vez de saltarse fuera de
Windows: CI corre en Linux, que es justo donde una regresión aquí no se notaría.

### C3 — El modelo de embeddings, fuera del event loop

`vector_matches` llamaba a `embed_texts` de forma síncrona en cada petición: cargaba ~570
MB de pesos en la primera (6,21 s medidos) y gastaba ~0,3 s de CPU en cada una después,
todo dentro del hilo del event loop, que mientras tanto no atendía a nadie más — `/health`
pasaba de 0,21 s a 0,33 s con cuatro `/matches` en vuelo.

Dos cambios, y los dos importan por separado. El resultado se **cachea**: sólo existe un
perfil de proveedor (una fila *singleton*), así que la descripción embebida era
byte-idéntica en cada llamada. Y el encode se manda a un hilo con `asyncio.to_thread`, para
que cuando sí haya que calcularlo no congele el proceso entero. El test lo comprueba por
dónde corre: el hilo del encode no puede ser el del loop.

No se ha llegado a persistir el embedding del proveedor en una columna —la opción de fondo
del informe—, porque con la caché el modelo ya sólo se carga una vez por proceso y el coste
por petición desaparece. Queda anotado para la 5.4, donde la memoria del despliegue sí
decide.

### G3 — El número de la portada

`MatchListResponse(total=len(items))`: el total era el tamaño de página. Con `limit=20`
decía 20 y con `limit=5` decía 5, y la portada lo imprimía como "N resultados del embudo".

Ahora `total` es la salida real del embudo y `returned` el tamaño de la página, y la
respuesta lleva además las cuentas por etapa que `funnel_stage_counts` ya calculaba: corpus
entero → en plazo → CPV → importe → ámbito. Eso no es sólo corregir un número: es lo que
permite que la portada **cuente** la reducción en vez de afirmarla, y que un resultado
vacío diga en qué etapa se quedó en lugar de un "no hay nada".

El test que lo protege pide dos veces con límites distintos: el corpus no cambia entre las
dos llamadas, así que `total` tampoco puede. Es lo que distingue un recuento real del
tamaño de página, que a simple vista se parecen.

### G1, G2, G4, G6 y M5 — Todos salían de la misma clave

`TenderAnalysis` se escribía con clave primaria `pdf_hash` y se leía siempre por
`expediente`. De ahí salían cuatro problemas distintos:

- Dos licitaciones con el PCAP byte-idéntico compartían una sola fila. La segunda leía su
  análisis por expediente, no encontraba nada y respondía "nunca analizado" para siempre,
  mientras la tarea acertaba en la caché y no escribía nada. Bucle cerrado, sin error
  visible por ninguna parte (**G2**).
- Esas mismas dos, analizadas a la vez, insertaban la misma clave primaria y la segunda
  transacción moría con `IntegrityError`. Hoy lo tapa `--pool=solo`; con `prefork` en
  Linux, no (**G6**).
- "El análisis más reciente" ordenaba por `created_at`, cuyo `server_default` es `now()` —
  congelado durante toda una transacción, así que dos filas escritas juntas empataban
  (**M5**).

La clave pasa a ser `expediente`: una fila por licitación, reescrita en sitio. Lo que la
clave por hash servía —no repetir la llamada cara al LLM— no necesitaba ser la identidad de
la fila: `find_cached_extraction` busca el documento por un índice sobre `pdf_hash` y copia
la extracción ya validada sobre la fila de *esta* licitación. Mismo ahorro, sin dos
licitaciones compartiendo identidad. Y la lectura vuelve a ser un acceso por clave primaria,
con lo que el empate desaparece solo.

La migración va escrita a mano: `--autogenerate` ve una clave primaria cambiando de columna
como "tira la identidad de la tabla y construye otra", sin saber que antes hay que
deduplicar las filas. Comprobada de ida y vuelta, y `alembic check` no detecta diferencias
con los modelos.

Encima de eso, dos límites que faltaban:

- **G1**: una corrida cuyo worker muere entre el `commit` que marca `IN_PROGRESS` y el que
  escribe el resultado dejaba una fila que nadie iba a terminar nunca — el lock de Redis
  caduca solo, la fila no. La lectura la resuelve como fallida una vez pasado el plazo que
  ese lock protegía, y la constante es literalmente la misma para los dos, para que no
  puedan separarse.
- **G4**: el PCAP se descargaba dos veces por análisis, las dos bufereando la respuesta
  entera sin tope. Ahora se descarga una sola vez, en *streaming*, con un techo de 50 MB, y
  los bytes se le pasan al grafo por su contexto —no por el estado, que Langfuse traza y
  donde unos bytes de PDF no se pueden enmascarar ni sirven de nada. Un documento por
  encima del tope se registra como no analizable en vez de tumbar al worker, que con
  `--pool=solo` se llevaría por delante también la ingesta diaria.

### G7 — Lo que lee el usuario cuando algo falla

El límite de error del grafo guardaba `str(exc)` y el panel lo pintaba tal cual. Ahora cada
fallo se mapea a un mensaje que nombra la causa y dice si reintentar sirve de algo, y el
detalle técnico se queda en el log y en la traza de Langfuse, que es donde se lee de verdad.
El test recorre todos los fallos mapeados y comprueba que ninguno lleva una URL, un
*traceback* ni el nombre de una librería.

### C5, M7, M8, M9, M11 — Los bordes

**C5** baja de crítico a medio por ser una herramienta local, pero se arregla igual: los
puertos de Postgres y Redis se publican sólo en los interfaces de loopback. Docker escribe
sus propias reglas de cortafuegos, así que un puerto publicado a secas sigue siendo
alcanzable desde toda la red local aunque el cortafuegos del sistema parezca cerrado — con
credenciales de desarrollo en la base de datos y ninguna autenticación en Redis, que además
guarda los *checkpoints* de ingesta. Se mapean **los dos** loopback, no sólo el IPv4:
publicando únicamente `127.0.0.1`, `localhost` resuelve primero a `::1` en Windows y cada
conexión pagaba ~2 s de *timeout* antes de caer al IPv4 — medido en el momento, porque la
suite pasó de 12 s a más de dos minutos.

**M7**: una descripción sin lexemas significativos construía un `tsquery` vacío, y
`to_tsquery('')` es un error de sintaxis que se llevaba `GET /matches` entero. Los lexemas
se resuelven ahora en su propia consulta, y si no hay ninguno se salta la mitad léxica. La
primera versión metía un `nullif` dentro de la expresión anidada, y eso resultó convertir la
consulta de ranking de milisegundos en **130 segundos**: el planificador dejaba de tratar el
`tsquery` como una constante. Queda escrito en el propio módulo, porque es exactamente el
tipo de cambio que parece inocuo.

**M8**: el cargador histórico dejaba su ZIP temporal de ~200 MB si la descarga se cortaba a
mitad, porque el único código que lo borraba vivía en una función a la que nunca llegaba la
ruta. **M9**: el cliente HTTP síncrono dentro de una corrutina se queda —es correcto ahí,
porque esa tarea es dueña de su loop—, pero con un comentario que lo marca como deliberado
y lo contrasta con C3, que es el mismo patrón donde sí hace daño. **M11**: el modo *offline*
de Alembic construía su URL con `str(engine.url)`, que enmascara la contraseña, así que el
SQL que emitía llevaba una URL incapaz de conectar.

**M10**: CLAUDE.md decía "Fase 1 cerrada, siguiente Fase 2" con el repositorio en la 5.2, y
presentaba como decisión abierta el modelo de embeddings, cerrado desde la 2.4. Actualizado,
junto con el comando de arranque de la API que cambia por C2.

### Lo que queda para la 5.3

Los trece hallazgos de frontend (E1–E13) y los cuatro medios que viven en el dashboard: el
`setInterval` con *callback* asíncrono (M1), el error que no se limpia tras un reintento con
éxito (M2), los enlaces sin codificar frente a un cliente de API que sí codifica (M3), las
cabeceras de seguridad ausentes en `next.config.ts` (M6) y la falta de `generateMetadata` en
la ficha (M12). **G5** —que el dashboard no tiene ningún límite de error— entra ahí también,
por tocar los mismos ficheros.

### Estado al cerrar

236 tests en verde, `ruff check`, `ruff format --check` y `mypy --strict` limpios. Los tres
criterios de aceptación se cumplen, y el primero está verificado contra la API levantada y
el corpus real, no simulado.
