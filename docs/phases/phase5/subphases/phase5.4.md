# Subfase 5.4 — Empaquetado para ejecutar en local

## Plan acordado

Compass no es un servicio alojado: es una herramienta que un proveedor se descarga y
levanta en su propia máquina. Lo que falta, entonces, no es un servidor — es que ese
arranque sea de una pieza.

Hoy, alguien que clone el repositorio tiene que: rellenar un `.env` con cinco variables,
levantar Docker, aplicar migraciones, editar un fichero Python con sus datos de empresa,
ejecutarlo, lanzar un cargador histórico que tarda minutos, y abrir cuatro terminales.
Esta subfase reduce eso a dos pasos: poner su clave de OpenRouter en el `.env`, y
`docker compose up`.

### Lo que se decidió al planificarla

**El reloj nocturno no era el problema que parecía.** La duda al cerrar la 5.3 era qué
pasa con la ingesta de las 03:00 en una máquina que se apaga por la noche. Comprobado
contra el propio Celery antes de diseñar nada: el `is_due` de un `crontab` calcula
`rem = max(rem_secs, 0)` y marca `due = rem == 0`, así que si el momento ya pasó dispara
**en cuanto beat arranca**, da igual cuánto lleve apagada la máquina. Y dispara una sola
vez, no una por día perdido — que es lo correcto, porque la marca de agua sobre
`atom:updated` hace la ingesta incremental. Medido:

```
última ejecución hace 0d 2h  -> due=False
última ejecución hace 1d 2h  -> due=True
última ejecución hace 10d 2h -> due=True
```

`beat_cron_starting_deadline`, que suprimiría ese comportamiento, está a `None`.

**Pero hay una trampa, y es la que justifica media subfase.** Ese `last_run_at` vive en
`backend/celerybeat-schedule`, un fichero *shelve* relativo al directorio desde el que se
arranca beat. Si no está, cada entrada se inicializa con `last_run_at = now` y **no hay
nada que recuperar**: beat se esperaría a las 03:00 siguientes. O sea que meter beat en un
contenedor sin volumen para ese fichero rompe la recuperación en silencio, sin un solo
error. Necesita volumen.

**Las migraciones, en un servicio propio.** La idea de lanzarlas al crear los contenedores
es correcta, pero como comando de arranque la tendrían API, worker y beat a la vez, y los
tres levantan en paralelo. Alembic no toma ningún *lock* por su cuenta. Va en un servicio
de un solo uso del que los otros tres dependen con `service_completed_successfully`.

**El perfil, por formulario.** Hoy se siembra editando `providers/seed.py`, que contiene
los datos reales de una empresa concreta. Para alguien que se descarga la herramienta eso
no vale: sus CPV, su rango de importe, su facturación y sus certificaciones son *su*
perfil, y son justo lo que decide el embudo y el veredicto. Hace falta un endpoint de
proveedor — que la Fase 2 no construyó a propósito, "un CRUD que nadie necesita todavía"
— y una pantalla. `seed.py` pasa a ser un ejemplo, no la fuente de verdad.

Editar el perfil ya es seguro sin tocar nada más, y conviene dejarlo escrito: el veredicto
no se almacena nunca (se recalcula en cada lectura contra el perfil actual) y la caché del
embedding de la descripción está indexada por el propio texto, así que cambiarlo la
invalida sola.

**La clave de OpenRouter se queda en el `.env`, no en el formulario.** Una clave de API no
es un dato de perfil: el perfil vive en Postgres y se sirve por HTTP, así que una clave
metida por formulario acabaría en esa tabla en texto plano y viajando al navegador en cada
lectura. En el `.env` sólo la ve el proceso. Lo que sí hace el formulario es **avisar de
que falta**, en vez de que se descubra al fallar el primer análisis.

**El vertical sigue siendo CPV 72, y se dice.** «Cargar el histórico según el perfil»
junta dos filtros que son independientes: el vertical de ingesta (`vertical.py`, división
72 a fuego) decide qué se guarda siquiera, y los CPV del proveedor deciden qué aflora de
lo guardado. Alguien con CPV fuera de la división 72 tendría la base vacía por mucho que
rellene el formulario. Derivar el vertical del perfil obligaría a rebajar ~600 MB de
archivos mensuales cada vez que alguien añada una división; queda anotado como la
evolución natural, y por ahora el formulario declara el alcance en lugar de prometer algo
que la ingesta no puede dar.

**La carga inicial, encolada y con progreso real.** El `historical_loader` tarda minutos
(tres ZIP de ~200 MB parseados entrada a entrada), así que en un *entrypoint* silencioso
el primer arranque parecería colgado. Se encola como tarea desde el formulario, y el
progreso se lee de `funnel.total` — el número de licitaciones en la base, que sube solo
según carga. Progreso honesto sin maquinaria nueva.

### Lo que se construye

1. `GET`/`PUT /provider`, con su repositorio ya existente detrás.
2. `POST /ingestion/backfill`, que encola la carga histórica con lock, como las demás.
3. Pantalla de perfil en el dashboard, a la que lleva el estado vacío que ya existe.
4. `Dockerfile` del backend con el modelo de embeddings horneado, y los servicios
   `migrate`, `api`, `worker` y `beat` en el `docker-compose.yml`, con volumen para el
   *schedule* de beat.

### Criterios de aceptación

1. Partiendo de una base de datos vacía y un `.env` con sólo `OPENROUTER_API_KEY`,
   `docker compose up` deja la API respondiendo y las migraciones aplicadas, sin ningún
   comando manual.
2. `GET /provider` devuelve 404 sin perfil y el perfil tras un `PUT`; `PUT` valida y
   rechaza un perfil incompleto.
3. En el dashboard, sin perfil sembrado la portada lleva al formulario; al guardarlo,
   vuelve a los matches calculados con esos datos.
4. La carga histórica se dispara desde la pantalla y su avance se ve sin recargar a mano.
5. `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`, `npm run lint` y
   `npm run build` limpios, y CI en verde.

## Progreso

### El perfil deja de ser un fichero Python

`GET`/`PUT /provider` sobre el repositorio que ya existía desde la Fase 2. `PUT` y no
`PATCH`, y la razón está en un test: mandar la lista de certificaciones vacía tiene que
**borrarlas**, porque "no tengo ninguna" y "no las he mencionado" son hechos distintos y esa
diferencia decide veredictos — un pliego que exige ISO 27001 bloquea a quien no la declara.
Un `PATCH` colapsaría los dos casos.

La pantalla explica, campo a campo, **qué decide cada uno**: cuáles son filtros duros
(CPV, importe, ámbito) y cuáles sólo entran en el veredicto (facturación,
certificaciones). No es adorno: una descripción escrita como un eslogan y otra escrita
como una descripción del trabajo producen rankings muy distintos, y no hay forma de que
quien rellena el formulario lo sepa si no se dice ahí. También declara el límite que no
puede saltarse — Compass v1 sólo ingiere la división CPV 72, así que unos códigos de otra
división no encontrarán nada por mucho que se guarden.

Un detalle que no hizo falta construir: editar el perfil no invalida nada. El veredicto no
se almacena (se recalcula en cada lectura) y la caché del embedding de la descripción está
indexada por el propio texto, así que cambiarlo la falla por construcción. Queda escrito en
el endpoint, antes de que a alguien le dé por añadir una caché ahí.

`seed.py` se queda como ejemplo, con un test que comprueba que sigue validando contra el
mismo esquema que postea el formulario: ya no es la fuente de verdad, pero sí es el ejemplo
que alguien copia.

### El arranque en frío, visible

`POST /ingestion/backfill` encola la carga histórica con su propio lock, igual que las
otras dos tareas. El formulario la dispara **sólo si el corpus está vacío** — con
licitaciones ya ingeridas, rebajar tres archivos mensuales costaría minutos para insertar
filas que ya están.

El progreso no necesitó endpoint: `funnel.total` ya es el número de licitaciones en la base,
así que la portada lo consulta cada cinco segundos y el número sube solo. Es además el mismo
número que enseña el resumen del embudo cuando termina, así que no hay dos formas distintas
de contar lo mismo.

### La imagen, y por qué son dos etapas

El `Dockerfile` hornea el modelo de embeddings en tiempo de construcción, decidido ya en la
Fase 2. Sin eso, `sentence-transformers` se descarga ~570 MB de Hugging Face dentro de la
primera petición que haga un usuario — en una máquina que puede estar sin internet, y
repitiéndolo cada vez que se recree el contenedor. Con `HF_HUB_OFFLINE=1` en la etapa final,
además, la librería deja de salir a comprobar actualizaciones de un fichero que ya tiene.

El nombre del modelo se lee del propio módulo en el `RUN` que lo descarga, no se repite en
el Dockerfile: cambiar `matching/embeddings.py` cambia lo que se hornea, sin nada que
mantener sincronizado a mano.

### Los cuatro servicios

`migrate` corre `alembic upgrade head` y termina; los otros tres dependen de él con
`service_completed_successfully`. Esa es la pieza que evita que API, worker y beat lancen
tres migraciones a la vez al levantar en paralelo — Alembic no toma ningún lock por su
cuenta.

`beat` monta un volumen y arranca con `--schedule=/app/state/celerybeat-schedule`. Sin eso,
cada reinicio inicializa los `last_run_at` a "ahora" y **la ingesta perdida mientras la
máquina estaba apagada no se recupera nunca**: beat se esperaría al siguiente 03:00. Con el
volumen, dispara la ingesta atrasada segundos después de arrancar, que es justo lo que hace
que una herramienta que vive en un portátil siga estando al día.

El worker corre con el pool `prefork` por defecto, no con `--pool=solo`: ese apaño existe
por Windows, y dentro del contenedor esto es Linux, donde `fork()` funciona.

Los puertos de la API se publican sólo en los dos loopback, igual que Postgres y Redis desde
la 5.2, y por el mismo motivo: no tiene autenticación y no hay razón para que nadie más en
la red la alcance.

### Lo que el propio build enseñó

La primera construcción de la imagen **falló**, y el error no tenía nada que ver con
Docker: una `ValidationError` de Pydantic. El paso que hornea el modelo lee su nombre del
código en vez de repetirlo en el `Dockerfile`, y ese nombre vivía en
`matching/embeddings.py` — que importa la ORM, que importa `core.db`, que construye el
engine desde `Settings` al importarse. O sea que **preguntar "¿qué modelo es?" exigía el
entorno entero configurado**, y en tiempo de construcción no hay ninguno.

El arreglo no es el `Dockerfile`: `EMBEDDING_MODEL_NAME` y `EMBEDDING_DIMENSIONS` pasan a
un módulo sin un solo import. Estaban repartidos entre `matching/embeddings.py` (el
nombre) y `tenders/models.py` (la dimensión), y juntarlos es además lo correcto por sí
mismo — la dimensión no es un hecho de la tabla `tenders`, es un hecho del modelo, y la
tabla sólo tiene que estar de acuerdo con él.

### Verificación

Con la pila levantada de cero:

```
migrate   Exited (0)     alembic upgrade head, y termina
api       Up             /health 200, /matches 200
worker    Up             celery@… ready (pool prefork)
beat      Up             beat: Starting…
```

`GET /matches` desde el contenedor devolvió el embudo real —3.583 → 76 → 27 → 6— lo que
prueba de paso que **el modelo horneado funciona sin red**: con `HF_HUB_OFFLINE=1`, si no
estuviera en la imagen esa petición habría fallado en vez de responder. Y
`/app/state/celerybeat-schedule` existe dentro del volumen, que es la condición de la que
depende recuperar una ingesta perdida.

Un número que conviene tener presente: la imagen pesa **5,36 GB**. La mayor parte es
`torch` (la variante CPU que `pyproject.toml` ya elige en Linux) más los ~570 MB del
modelo. Es mucho para descargar, pero es el precio de que la primera petición del usuario
sea instantánea y de que la herramienta funcione sin conexión a Hugging Face. Reducirlo
tiene salidas conocidas —`onnxruntime` en vez de `torch`— y ninguna barata; queda anotado.

### Lo que no lleva

**Un arranque sin `.env`.** `docker compose` falla nombrando el fichero que falta, que es
mejor error que arrancar y morir después en la validación de `Settings`, pero sigue siendo
un paso manual antes del primero. El README lo pone como línea uno.

**El dashboard fuera de Docker.** El frontend se sigue levantando con `npm run dev`. Meterlo
en el compose es un `Dockerfile` más y una variable de entorno distinta
(`NEXT_PUBLIC_API_URL` se resuelve en el navegador, no en la red de Docker), y no hacía
falta para el objetivo de esta subfase.

### Estado al cerrar

251 tests en verde, `ruff`, `ruff format --check` y `mypy --strict` limpios; `npm run lint`
y `npm run build` limpios. Los cinco criterios de aceptación se cumplen, y el primero está
verificado levantando la pila de verdad, no razonando sobre el YAML.
