# Fase 5 — Frontend, email y despliegue

## Objetivo

Al cerrar la Fase 4, el producto está entero por dentro y es invisible por fuera: el
embudo reduce 3.583 licitaciones a 52, el agente lee un pliego y emite un veredicto
citado, y todo eso solo se puede ver con `curl` o desde `/docs`. La Fase 5 le pone cara
a lo construido y lo saca de la máquina de desarrollo.

De las tres piezas que el documento de diseño mete en esta fase (§8: "Frontend, email y
despliegue"), **la única imprescindible para que el proyecto se pueda enseñar es el
dashboard**. Las otras dos se deciden después, con el dashboard delante.

## Decisiones de arquitectura tomadas en la planificación

- **Next.js con App Router y TypeScript**, en `frontend/` dentro del mismo repositorio.
  El documento de diseño ya nombraba Next.js; el monorepo simple (backend + frontend
  hermanos) evita un segundo repo que habría que versionar y desplegar en paralelo para
  un proyecto de un solo autor.
- **Tailwind v4** para los estilos, avisado como dependencia nueva. Descartado shadcn/ui:
  genera muchos ficheros en el repo y el resultado se reconoce como plantilla, que es lo
  contrario de lo que este proyecto quiere demostrar.
- **El frontend no habla con la base de datos.** Consume la API que ya existe, igual que
  lo haría cualquier otro cliente. Ni ORM ni SQL en el lado de Next.js.

## Subfases

1. **5.1 — Dashboard básico**
   Las dos pantallas que cuentan el producto entero: el listado de matches del proveedor
   (con el porqué del encaje) y la ficha de una licitación, con el análisis del pliego
   bajo demanda y su veredicto citado. Incluye lo que falte en el backend para
   sostenerlas: la ficha de una licitación concreta y CORS.

2. **5.2 — Despliegue** *(alcance por decidir)*
   Sacar la aplicación de la máquina de desarrollo. Aquí es donde aterriza la implicación
   real del diseño: la ingesta diaria y el backfill de embeddings son tareas programadas,
   así que necesitan un proceso vivo a esa hora -- no el portátil de Alan. Decisión
   pendiente entre un VPS con el `docker compose` entero (beat incluido) y desacoplar el
   reloj a un cron externo que encole la tarea, dejando vivos solo API y worker.

3. **5.3 — Digest diario por email** *(candidato a quedar fuera de la v1)*
   Está en el alcance del MVP del documento de diseño y no existe nada de él: ni
   destinatario en `Provider`, ni proveedor de envío, ni marca de agua de "qué es nuevo
   desde el último envío". La maquinaria sí está (beat, embudo, perfil). Si no entra, se
   declara fuera explícitamente en el README, con el mismo criterio que las subvenciones
   y el OCR: fuera porque se decidió, no porque no dio tiempo.

4. **5.4 — Revisión completa de la fase**
   Mismo patrón que 1.11, 2.7, 3.9 y 4.7.

La Fase 6 del documento de diseño original ("CI y README narrativo") ya está hecha: el CI
entró en la 4.6 y el README lleva el relato con números reales desde la 2.7.
