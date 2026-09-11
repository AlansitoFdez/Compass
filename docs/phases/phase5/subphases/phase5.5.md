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
