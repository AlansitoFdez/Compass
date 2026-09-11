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

2. **5.2 — Revisión completa de la aplicación y corrección de los hallazgos**
   Revisión de las dos mitades del producto contra el corpus real, antes de desplegar:
   37 hallazgos, de los que esta subfase corrige los del backend. El primero apagaba el
   agente analista en dos de cada tres licitaciones (las rutas de análisis no casaban con
   los expedientes que llevan barras). Se hace ahora y no en la revisión de fase porque
   varios condicionan lo que se despliega y cómo.

3. **5.3 — Reestructuración y rediseño del dashboard**
   Los trece hallazgos de frontend de la revisión: organización por dominio como en el
   backend, límites de error y estados de carga, y el rediseño que pone el veredicto y el
   plazo donde deciden. Separado de la 5.2 porque tiene su propio criterio de "hecho".

4. **5.4 — Empaquetado para ejecutar en local** ✅
   El backend entero —API, worker y planificador— en el `docker compose` que ya existía
   para Postgres y Redis, con las migraciones en un servicio propio de un solo uso y el
   modelo de embeddings horneado en la imagen. Y el perfil del proveedor, que se sembraba
   editando un fichero Python, pasa a ser un formulario.

5. **5.5 — Arranque sin fricción**
   Lo que separa "funciona en mi máquina" de "alguien se lo descarga y lo prueba": el
   dashboard también en el compose (hoy además de Docker hace falta Node y un servidor de
   desarrollo), la clave de OpenRouter como opcional para que se pueda arrancar con cero
   configuración, y el recorrido completo verificado de una vez contra una base vacía —
   perfil, carga, matches, análisis, veredicto. Cada pieza está probada por separado y ese
   recorrido entero no lo ha hecho nadie todavía.

6. **5.6 — Evals del texto libre con RAGAS**
   `analysis/scoring.py` puntúa los nueve campos objetivamente comprobables y deja fuera,
   a propósito, las descripciones en texto libre: no se pueden comparar mecánicamente. Son
   la mitad de lo que el modelo escribe y hoy no las mide nadie. Ahí es donde RAGAS aporta
   algo que este proyecto no tiene, en lugar de duplicar la verificación de citas, que ya
   se hace en Python y de forma más fuerte que con un juez LLM.

7. **5.7 — README**
   El actual está organizado por cómo se construyó el proyecto —fases, tablas de estado—
   y no por lo que necesita quien llega: qué es, verlo, arrancarlo, cómo funciona, y por
   qué se decidió así. Va después de la 5.5 a propósito: las capturas y el "arrancar en
   dos comandos" tienen que reflejar lo que el lector hará de verdad. El relato por
   subfases no se borra, se queda en `docs/phases/` y se enlaza.

8. **5.8 — Revisión completa de la fase**
   Mismo patrón que 1.11, 2.7, 3.9 y 4.7.

## Fuera de la v1: el digest diario por email

Estaba en el alcance del MVP del documento de diseño, y se queda fuera **por decisión, no
por falta de tiempo** — mismo criterio que las subvenciones y el OCR.

Dos razones, y la segunda es la que cierra el asunto. La primera es de producto: si el
usuario entra al dashboard y ve el estado, un correo diario no le cuenta nada que la
pantalla no cuente mejor y antes. La segunda es técnica y es propia de que Compass viva en
la máquina de quien lo usa — **un digest a las 03:00 sale de un proceso que tiene que estar
vivo a esa hora**, y ese ordenador está apagado. El correo llegaría cuando el usuario
encendiera el portátil, que es exactamente el momento en que va a abrir el dashboard de
todas formas. El canal no aporta nada.

La Fase 6 del documento de diseño original ("CI y README narrativo") ya está hecha: el CI
entró en la 4.6 y el README lleva el relato con números reales desde la 2.7.
