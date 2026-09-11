# Compass — dashboard

Frontend del radar de licitaciones. Dos pantallas:

- **`/`** — las licitaciones que encajan con el perfil del proveedor, tal y como las ordena
  el embudo (Reciprocal Rank Fusion sobre la búsqueda léxica y la vectorial), con el motivo
  de encaje: si la trajo el léxico, el vectorial, o los dos.
- **`/tenders/[expediente]`** — la ficha de una licitación y el análisis de su pliego bajo
  demanda: veredicto (APTO / APTO CON RESERVAS / NO APTO) con cada motivo citado a su
  cláusula y página, y los requisitos extraídos con su cita textual.

No habla con la base de datos: consume la API de `backend/` como lo haría cualquier otro
cliente.

## Arrancar

Necesita el backend levantado (ver el README de la raíz):

```bash
npm install
cp .env.example .env.local   # NEXT_PUBLIC_API_URL, http://localhost:8000 por defecto
npm run dev                  # http://localhost:3000
```

El análisis de un pliego además necesita el **worker de Celery** corriendo: la API solo
encola la tarea (responde `202`), y la pantalla va consultando el resultado cada 5 segundos
hasta que el worker termina. Sin worker, el análisis se queda en "en cola" para siempre.

## Decisiones

- **Server Components para leer, cliente solo para el análisis.** El listado y la ficha se
  renderizan en el servidor contra la API. El único componente de cliente es el panel de
  análisis, porque es el que dispara el `POST` y hace *polling* — y es también la razón de
  que el backend necesite CORS.
- **Tipos escritos a mano** en `src/lib/api.ts`, espejo de los esquemas Pydantic del
  backend. Generarlos del OpenAPI sería lo escalable; para dos pantallas añade un paso de
  compilación y un directorio de código generado a cambio de menos claridad que 80 líneas
  que además documentan la forma.
- **Nada cacheado** (`cache: "no-store"`, `dynamic = "force-dynamic"`): el dashboard existe
  para enseñar lo que el embudo y el agente dicen *ahora*, y el estado de un análisis cambia
  entre una petición y la siguiente.
