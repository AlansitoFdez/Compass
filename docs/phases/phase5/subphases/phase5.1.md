# Subfase 5.1 — Dashboard básico

## Plan acordado

Del desglose de la Fase 5 (`docs/phases/phase5/phase5.md`): las dos pantallas que cuentan
el producto entero -- el listado de matches del proveedor y la ficha de una licitación con
el análisis del pliego bajo demanda --, más lo que falte en el backend para sostenerlas.

**Alcance decidido al arrancar**: dos pantallas, no una ni tres. Solo el listado enseñaría
el embudo pero no el agente ni el veredicto citado, que es la pieza cara y diferencial. Una
tercera pantalla con el corpus completo (`GET /tenders`) no añadiría nada que el README no
cuente ya mejor con números.

### Lo que hay que añadir en el backend

La ficha necesita una licitación concreta, y ese endpoint **no existe**: hoy hay
`GET /tenders` (listado paginado), `GET /matches`, y el par de análisis. Sin
`GET /tenders/{expediente}` la ficha solo funcionaría llegando desde el listado, y se
rompería al recargar o al compartir el enlace.

Y hace falta CORS: el panel de análisis dispara el `POST` y hace *polling* desde el
navegador, así que el origen del frontend tiene que estar permitido explícitamente.

### Cómo se muestra el análisis

`POST /analyze` devuelve `202` y no hay *result backend* en Celery (decisión de la 3.8), así
que la única forma de observar el resultado es **consultar `GET /analysis` periódicamente**.
La pantalla refleja eso tal cual: sin análisis → botón; `pending`/`in_progress` → espera con
*polling*; `completed` → veredicto con sus motivos y citas; `failed`/`not_analyzable` → el
motivo, no una página en blanco.

### Criterios de aceptación

1. `npm run build` y `npm run lint` limpios en `frontend/`.
2. Backend: `GET /tenders/{expediente}` devuelve la licitación (200) o 404 si no existe, y
   el navegador puede llamar a la API desde el origen del frontend (CORS). Con tests.
3. Con la API real levantada, `/` lista los matches reales del proveedor sembrado, cada uno
   con su score RRF y de qué recuperador vino, y enlaza a su ficha.
4. En la ficha de una licitación con `pcap_url`, el botón dispara el análisis y la pantalla
   pasa sola de "en curso" a veredicto citado -- verificado con una corrida real contra el
   worker, no simulada.
5. `uv run pytest`, `ruff check --fix`, `ruff format`, `mypy` limpios, y CI en verde.

## Progreso

### Lo que hubo que añadir en el backend

**`GET /tenders/{expediente}`** (`api/routes/tenders.py`), con un detalle que no es cosmético:
el parámetro va declarado como `{expediente:path}`, el único de toda la API. Los expedientes
reales de PLACSP llevan barras dentro -- `SER/2026/0000006435`, `300/2026/01246`, ambos en el
golden set --, y el convertidor por defecto corta en la primera, así que esas licitaciones
darían 404 en su propia ficha. Test específico con un expediente con barras, no solo con uno
simple.

Eso abrió un problema de enrutado que había que resolver antes de que mordiera:
`{expediente:path}` **también casa con `/tenders/{expediente}/analysis`**, porque las barras
entran en el patrón. Con el router de `tenders` registrado antes que el de `analysis` -- que
era el orden que había --, cada lectura de un análisis la habría contestado la ficha con un
"Tender not found". Invertido el orden en `api/router.py`, con un test que lo fija: el 404 que
devuelve `/tenders/X/analysis` tiene que ser el del endpoint de análisis ("has not been
analyzed yet"), no el de la ficha.

**CORS** (`main.py`), con los orígenes en `Settings.cors_origins` y documentados en
`.env.example`. Una lista configurable, nunca `["*"]`: el comodín es exactamente el tipo de
valor por defecto que sobrevive hasta producción, y esta API tiene un endpoint que encola
trabajo (`POST /analyze`). Dos tests: el origen configurado recibe la cabecera, uno
desconocido no.

### El frontend

`create-next-app` con Next.js 16, React 19, TypeScript y Tailwind v4, en `frontend/`.

- **Server Components para leer, cliente solo para el análisis.** El listado y la ficha se
  renderizan en el servidor; el único componente de cliente es `AnalysisPanel`, que es el que
  dispara el `POST` y hace *polling*. Esa es, de hecho, la única razón por la que hace falta
  CORS: todo lo demás lo pide el servidor de Next, no el navegador.
- **El *polling* no es una elección de diseño del frontend, es una consecuencia del backend.**
  `POST /analyze` responde `202` y Celery no tiene *result backend* (3.8), así que consultar
  `GET /analysis` es la única forma de observar el resultado. Intervalo de 5 s: una corrida
  real tarda entre 36 y 338 s (medido en la 4.7), así que algo más apretado solo añade ruido.
- **Ruta *catch-all*** (`/tenders/[...expediente]`) por el mismo motivo que el `:path` del
  backend: un segmento simple nunca casaría con un expediente que lleva barras.
- **Nada cacheado** (`cache: "no-store"` y `force-dynamic`): el dashboard enseña lo que el
  embudo y el agente dicen ahora, y el estado de un análisis cambia entre dos peticiones.
- **Tipos escritos a mano** en `lib/api.ts`, espejo de los esquemas Pydantic. Generarlos del
  OpenAPI sería lo escalable; para dos pantallas añade un paso de compilación y un directorio
  de código generado a cambio de menos claridad que 80 líneas que documentan la forma.

### Verificación contra datos reales, no contra mocks

API real (`uvicorn`), worker real (`--pool=solo`), corpus real y el dashboard servido de verdad:

- **Listado**: `/` devuelve 200 y renderiza los 20 matches reales del proveedor sembrado, con
  su score RRF y su motivo de encaje. El primero es el mantenimiento de portales Drupal de la
  Universidad de Jaén, encontrado por los dos recuperadores.
- **Ficha con análisis ya hecho** (`1276564F`, uno de los cuatro análisis reales que había en
  la base): renderiza en servidor el veredicto **NO APTO** con sus dos motivos, cada uno con
  su cita -- cláusula 20, página 15 --, la fidelidad de citas (67%) y los requisitos extraídos
  con su cita textual.
- **Ciclo completo en vivo** sobre `INN 26 002`: `POST` → `202` → `in_progress` → `failed`,
  observado por la misma vía que usa el panel. Falló con un `429`: el cupo diario gratuito de
  OpenRouter ya estaba agotado (ver 4.7). No es un fallo del dashboard -- es el camino de error
  real, y la pantalla lo muestra como debe: el mensaje del error y un botón de "Reintentar".

**Lo que no se ha verificado de forma automatizada**: que el `setInterval` del navegador
refresque la pantalla sola. Los tres estados (en cola, fallido, completado) sí están
verificados renderizados con datos reales, y el bucle es un `useEffect` estándar, pero no hay
prueba de navegador aquí; queda comprobado a ojo al abrirlo.

### Hallazgo real, no corregido aquí: el ruido de `certifications` ahora se ve

La ficha de `1276564F` muestra, entre los motivos del NO APTO, uno que dice literalmente
*"Exigen la certificación 'citation' y tu perfil no la declara"*. No es un fallo del
frontend: es el riesgo residual que la **3.9 documentó y decidió no parchear** -- el modelo
gratuito cuela a veces una declaración administrativa, o una fuga de un nombre de campo
interno, dentro de `certifications`, y `compute_verdict` no tiene forma de distinguirlo de
una certificación real sin una heurística frágil (la misma que el proyecto ya rechazó una vez
en la 3.7).

Lo que cambia es que **antes ese ruido vivía en un JSON y ahora está en la pantalla**, en el
sitio más visible del producto. Sigue sin arreglarse en esta subfase, que es de frontend; queda
señalado como lo primero que mirar en la revisión pendiente.

### CI

Segundo job en `.github/workflows/ci.yml` (`npm ci` → `lint` → `build`), independiente del de
Python: el dashboard lee la API en tiempo de petición, nunca al construir, así que compilarlo
no necesita ni base de datos ni API viva. Sin él, la mitad del repositorio pasaría a ser
TypeScript sin que el CI lo mirara -- justo el hueco que la 4.6 existía para cerrar.

### Verificación final

- `npm run build` y `npm run lint` limpios (las dos rutas salen como dinámicas, que es lo
  buscado).
- `uv run pytest`: **209 passed** (203 previos + 6 nuevos). `ruff check`/`format --check`/
  `mypy` sin avisos.

Subfase 5.1 completada. Los cinco criterios de aceptación se cumplen, con la salvedad
explícita del refresco automático en navegador, verificado a ojo y no automatizado.
