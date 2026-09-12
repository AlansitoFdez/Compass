# Subfase 5.5 — Arranque sin fricción

## Plan acordado

La 5.4 metió el backend entero en el compose. Queda lo que separa «funciona en mi máquina»
de «alguien se lo descarga y lo prueba en cinco minutos», que es el criterio con el que se
mide este proyecto: Compass se publica como una herramienta para descargar y probar.

Tres cosas, y ninguna añade funcionalidad al producto.

### El dashboard también en el compose

Hoy `docker compose up` levanta Postgres, Redis, la API, el worker y el planificador — y
para ver algo hace falta además tener Node instalado y arrancar `npm run dev`, que es un
servidor de desarrollo. Mientras eso siga así, «descárgalo y arráncalo» es mentira.

El detalle que lo complica: `NEXT_PUBLIC_API_URL` la resuelve **el navegador**, no la red
interna de Docker. No puede ser `http://api:8000` — ese nombre no existe fuera de la red de
compose. Tiene que ser `http://localhost:8000`, que es donde la API ya publica su puerto, y
va horneada en el *bundle* al construir la imagen, así que es un argumento de construcción
y no una variable de entorno de ejecución.

### La clave de OpenRouter, opcional

Mismo patrón que Langfuse en la 5.4. Hoy `Settings` la exige y el proceso no arranca sin
ella, lo cual es defendible —sin clave el agente no tiene a quién preguntar— pero tiene un
coste que en este proyecto pesa más: alguien que llega a curiosear se encuentra con que
tiene que crearse una cuenta antes de que la herramienta le enseñe nada.

Sin clave, todo lo que no es el agente funciona igual: la ingesta, el embudo, el ranking
híbrido, el dashboard entero. Que es, además, la mitad del proyecto que más código tiene.
Así que la API arranca, y el panel de análisis dice qué falta y dónde ponerlo en vez de
fallar con un error de validación al levantar.

Resuelve el asunto del `.env` de la mejor forma posible: no documentándolo mejor, sino
haciendo que no haga falta para empezar.

### El recorrido completo, verificado de una vez

Base vacía → formulario de perfil → carga histórica → matches → analizar un pliego →
veredicto citado. Cada pieza está probada por separado, con tests y a mano, y **ese
recorrido entero no lo ha hecho nadie de principio a fin**. Es literalmente la demo del
proyecto, y es donde salen los fallos que ninguna prueba aislada ve.

No se hace contra la base de desarrollo, que tiene 3.583 licitaciones y un perfil sembrado:
se hace contra una vacía, que es lo que se encuentra quien se lo descarga.

### Criterios de aceptación

1. Con el repositorio recién clonado y un `.env` copiado del ejemplo **sin ninguna clave**,
   `docker compose up` deja el dashboard servido en http://localhost:3000 y la API en el
   8000, sin Node instalado en la máquina.
2. Sin `OPENROUTER_API_KEY`, la API arranca, `/matches` responde y el panel de análisis
   explica qué falta; con la clave puesta, el análisis funciona.
3. Contra una base de datos vacía: el dashboard lleva al formulario, guardarlo dispara la
   carga, la portada enseña el corpus creciendo y acaba mostrando matches reales.
4. Un análisis completo desde el dashboard, con su veredicto citado, sobre una licitación
   del corpus recién cargado.
5. `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`, `npm run lint` y
   `npm run build` limpios, y CI en verde.

## Progreso

### El dashboard, servido por su propio contenedor

`output: "standalone"` traza los ficheros que el servidor necesita de verdad, así que la
imagen final no lleva `node_modules` ni herramientas de construcción: sólo el servidor y
los estáticos. Next deja fuera `.next/static` a propósito —espera que los sirva un CDN— y
aquí no hay ninguno, así que se copian a mano en la etapa final.

**Y aquí apareció el fallo que este contenedor tenía que enseñar.** `NEXT_PUBLIC_API_URL`
la resuelve el navegador, así que vale `http://localhost:8000`. Pero los Server Components
**también** llaman a la API, y lo hacen desde dentro del contenedor del dashboard — donde
`localhost:8000` es ese mismo contenedor, no la API. El resultado no fue un error visible:
la portada se quedaba servida en su esqueleto de carga, con un 200 y sin nada dentro.

Son dos direcciones distintas para la misma API, y sólo una puede ir horneada en el bundle
del navegador. `client.ts` elige según dónde se ejecuta, y `COMPASS_INTERNAL_API_URL`
—deliberadamente sin el prefijo `NEXT_PUBLIC_`, para que no salga del servidor— apunta al
nombre del servicio en la red de compose.

### Un fallo de construcción que costaba cinco minutos por línea

En la 5.4 el `Dockerfile` copiaba `src` y después horneaba el modelo. Docker invalida toda
capa posterior a un `COPY` que cambia, así que **cualquier edición de una línea de código
volvía a descargar los ~570 MB de pesos**. Se nota en cuanto iteras: el primer rebuild de
esta subfase tardó lo mismo que el build inicial.

Ahora el horneado va antes, y se copia sólo el fichero que necesita —
`matching/embedding_model.py`, que no importa nada— ejecutándolo con `runpy.run_path` en
vez de importarlo, porque en ese punto el paquete todavía no está instalado. El nombre del
modelo sigue leyéndose del código, sin repetirlo en el `Dockerfile`.

### La clave de OpenRouter, opcional

Mismo patrón que Langfuse. `Settings` ya no la exige, así que la API arranca con un `.env`
vacío y todo lo que no es el agente funciona: ingesta, embudo, ranking, dashboard entero.

Tres piezas para que eso no se convierta en un misterio:

- `require_openrouter_key()` es **el único sitio** donde la opcionalidad termina, usado por
  la tarea de análisis y los dos scripts de evals. Su mensaje nombra la variable, dice que
  es gratuita y dice que el resto funciona sin ella.
- `POST /analyze` responde **503** en vez de encolar una corrida condenada a morir con un
  401 minutos después. 503 y no 500: no hay nada roto, simplemente esta instalación no está
  configurada para eso. Y la comprobación va la última, para que una licitación inexistente
  siga siendo un 404 — decirle a alguien que le falta la clave para una licitación que no
  existe le manda a arreglar lo que no es.
- `GET /capabilities` devuelve dos booleanos, nunca material de clave, para que el
  dashboard lo diga **antes** de que nadie pulse. La ficha lo lee en el servidor junto al
  análisis, así que el panel llega sabiéndolo y no parpadea un botón que luego desaparece.

### El recorrido completo, contra una base vacía

Hecho sin tocar la base de desarrollo: un proyecto de compose aparte
(`docker compose -p compass-e2e`), con sus propios volúmenes y los mismos puertos, que se
destruye entero al terminar. La base real, con sus 3.583 licitaciones y sus cuatro
análisis pagados, no se toca en ningún momento.

Lo que ocurrió, en orden:

1. `docker compose up` levanta seis servicios, `migrate` aplica las migraciones y sale.
2. Abrir `/` con la base vacía lleva al formulario, con el texto de primer arranque.
3. Guardar el perfil encola la carga. **6.477 upserts en 205 s**, que quedan en 2.958
   licitaciones distintas — el resto son republicaciones del mismo expediente.
4. La portada enseña el embudo real de esa instalación: **2.958 → 119 → 38 → 11**.

**Y el recorrido encontró lo que tenía que encontrar.** Entre los pasos 3 y 4 había un
hueco de hasta quince minutos: el corpus recién cargado no tiene embeddings, y el
recuperador vectorial ignora toda fila que no los tenga. Así que se veían llegar 6.477
licitaciones y la lista seguía siendo pobre —sólo léxica— hasta que el tic de beat pasara,
sin nada en pantalla que lo explicara. Dos tareas correctas por separado, con un agujero
entre ellas que ningún test aislado podía ver. La carga encadena ahora la tarea de
embeddings al terminar.

### El análisis, a medias por una razón externa

`POST /tenders/2026/20/analyze` —un expediente **con barra**, que es lo que la 5.2
arregló— devuelve 202 y la tarea corre. El grafo descarga el pliego, detecta su capa de
texto y llama al modelo. Ahí se acaba: OpenRouter devuelve **429** porque el nivel gratuito
son 50 peticiones al día y ya estaban gastadas. Reintentado pasado el minuto, mismo
resultado: es el tope diario, no el de ritmo.

Así que el criterio 4 queda sin verificar hoy, por una razón que no es del código. Lo que
sí quedó verificado, y no es poco, es todo el recorrido hasta la llamada al modelo y la
vuelta entera del error: el usuario lee **"Se ha agotado la cuota de peticiones del modelo
(nivel gratuito de OpenRouter, 50 al día). Vuelve a intentarlo mañana."**

Eso es, de paso, la validación en producción del arreglo de esta misma sesión: antes, ese
429 de `openrouter.ai` se traducía como *"el servidor de PLACSP devolvió un error"*, porque
el mapeo casaba por tipo de excepción y las dos llamadas HTTP de un análisis lanzan la
misma.

### Lo que CI enseñó y una máquina de desarrollo no podía

Los dos tests de `/capabilities` pasaban en local y fallaban en CI.
`Settings(_env_file=None, ...)` desactiva la lectura del fichero `.env` **pero no las
variables de entorno**, y el trabajo de CI exporta `OPENROUTER_API_KEY` como marcador. O
sea que el objeto llamado `_NO_KEYS` llegaba allí con clave, y los dos tests afirmaban
exactamente lo contrario de lo que dicen.

Las fixtures pasan ahora todos los campos opcionales explícitamente, `None` incluido: los
argumentos de construcción tienen la precedencia más alta, así que dejan de depender de lo
que haya exportado alrededor. Comprobado ejecutando la suite con la variable puesta, que es
la condición que separaba CI de una máquina de desarrollo.

### Estado al cerrar

258 tests en verde, `ruff`, `ruff format --check` y `mypy --strict` limpios; `npm run lint`
y `npm run build` limpios.

Criterios 1, 2, 3 y 5, cumplidos y verificados levantando la pila de verdad. El **4 queda
pendiente** hasta que la cuota diaria de OpenRouter se renueve — el camino está verificado
de punta a punta salvo el eslabón de una extracción con éxito, que la Fase 3 y los evals de
la 4.4 ya cubren contra el golden set.

### El criterio 4, cerrado al día siguiente

La cuota se renueva a las **00:00 UTC** —02:00 en Madrid—, y lo dice la propia respuesta de
OpenRouter: junto al 429 viaja `X-RateLimit-Limit: 50`, `X-RateLimit-Remaining: 0` y un
`X-RateLimit-Reset` en milisegundos que apuntaba exactamente a esa medianoche. No es «vuelve
mañana» a ojo: es una hora concreta.

Pasada esa hora, el mismo expediente de la víspera, `INN 26 002` —el primer match del
proveedor—, analizado desde el dashboard: estado `in_progress` mientras el grafo descarga
las 98 páginas y llama al modelo, y a los ~100 segundos **veredicto NO APTO con sus dos
razones citadas**, la extracción completa campo a campo con su cláusula y su página, y la
fidelidad de citas en 56%. Capturado de la pantalla, no del `curl`.

Con eso, los cinco criterios de la 5.5 están cumplidos.

**Y el análisis trajo un hallazgo que no es de esta subfase.** Una de las dos razones del
NO APTO es la certificación `ISO/IEC 20000`, que en ese pliego **no es un requisito: es un
criterio de adjudicación que da 6 puntos** («s'atorgaran 6 punts en el cas de disposar
qualsevol dels següents certificats»). El modelo la metió en `certifications`, que el
cálculo del veredicto trata como exigencia, y el resultado es un **falso NO APTO**: se
descarta una licitación a la que el proveedor sí podía presentarse. El esquema le dice al
modelo que no incluya papeleo administrativo, pero no le dice que distinga *exigido* de
*puntuado*. Anotado para la revisión de fase (5.8); es el tipo de error más caro que este
producto puede cometer, porque se manifiesta como silencio.
