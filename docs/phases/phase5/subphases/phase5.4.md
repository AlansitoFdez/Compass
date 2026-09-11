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
