# Subfase 5.7 — README

## Plan acordado

El README actual está organizado por **cómo se construyó el proyecto**: una lista de fases
con su estado, tablas por fase, y el relato del embudo intercalado con el de la
observabilidad. Eso sirve para auditar, y para eso ya está `docs/phases/`. No sirve para lo
único que este README tiene que conseguir: que alguien que llega de un enlace entienda en
treinta segundos qué es esto y en dos comandos lo tenga corriendo.

Además dice cosas que ya no son verdad. Promete que `OPENROUTER_API_KEY` es obligatoria
(la 5.5 la hizo opcional), manda instalar Node y arrancar `npm run dev` (la 5.5 metió el
dashboard en el compose), y sus números del embudo son de antes de la última corrida.

### Estructura, en el orden en que alguien la necesita

1. **Qué es**, en tres líneas, y **una captura del dashboard**. Hoy no hay ni una imagen en
   todo el repositorio, y es lo que más cambia la primera impresión de quien llega.
2. **Arrancar**: dos comandos, arriba del todo, antes de cualquier explicación.
3. **Cómo funciona**: el recorrido ingesta → embudo → agente → veredicto.
4. **Las decisiones que importan**, con los números reales detrás: por qué el veredicto no
   lo emite el modelo, por qué las citas se verifican en Python, por qué híbrido y no sólo
   vectorial, y cuánto cuesta de verdad un análisis.
5. **Stack** y **qué queda fuera a propósito**.

El relato por subfases no se borra: se queda en `docs/phases/` y se enlaza como «el
razonamiento completo». Un README limpio con cuarenta documentos de decisiones detrás dice
más que un README que intenta ser las dos cosas.

### Las capturas

Con Edge en modo *headless*, que ya está en la máquina: ninguna dependencia nueva, ningún
Playwright. Van a `docs/images/` y se enlazan con ruta relativa, para que GitHub las sirva
sin depender de nada externo.

### Criterios de aceptación

1. Lo primero que se ve es qué es Compass y una captura real del dashboard; el primer
   bloque de comandos es el de arrancar, y son **dos**, sin Node ni `npm install`.
2. Todo número del README está **remedido hoy**, con el comando que lo produce nombrado al
   lado.
3. Las imágenes están versionadas en el repositorio y se ven con ruta relativa.
4. No queda ninguna afirmación que contradiga `.env.example`, `docker-compose.yml` o el
   comportamiento real de la aplicación — la clave opcional incluida.
5. Desaparece la lista de fases con su estado; el relato queda enlazado, no incrustado.
6. Todo enlace interno apunta a un fichero que existe.

## Progreso

### Lo que el README dice ahora, y lo que dejó de decir

Estructura nueva, en el orden en que alguien la necesita: qué es y una captura → arrancar
en dos comandos → cómo funciona en cuatro pasos → las decisiones que importan con sus
números → stack, lo que queda fuera, y el enlace al razonamiento completo.

Desaparece la lista de fases con su estado. Era el índice de `docs/phases/` duplicado peor,
y obligaba a quien llegaba a leer cuatro párrafos de historia del proyecto antes de saber
qué hacía la herramienta.

Y desaparecen tres afirmaciones que ya eran falsas: que `OPENROUTER_API_KEY` es
obligatoria, que hace falta Node y `npm run dev` para ver el dashboard, y los números del
embudo de antes de la última corrida. Las tres las arregló la 5.5 sin que el README se
enterara — que es exactamente lo que pasa cuando el README cuenta la construcción en vez
del producto.

### Los números, remedidos hoy

| Dato | Valor | De dónde sale |
| --- | --- | --- |
| Corpus persistido | 3.583 | `select count(*) from tenders` |
| Embudo | 3.583 → 71 → 25 → 6 | `GET /matches`, campo `funnel` |
| Traídas sólo por el vectorial | 3 de 6 | `GET /matches`, `lexical_rank` nulo |
| Análisis trazados | 35 | `python -m compass.analysis.cost_report` |
| Tokens por análisis | 31.729 – 118.486 (media 60.399) | ídem |
| Coste | 0,00 € en el 100% | ídem |
| Tiempo | 36 – 338 s (media 159 s) | ídem |
| Tests | 268 | `uv run pytest` |

Los del embudo bajaron desde los del README anterior (76 → 71, 27 → 25) por la razón más
aburrida y más sana: han pasado días y algunos plazos han vencido. La etapa 1 exige fecha
viva desde la 5.3, así que el número se mueve solo.

### La captura obligó a elegir qué veredicto se enseña

La primera candidata era `INN 26 002`, el análisis de esta misma noche y el primer match
del proveedor. Al mirarla con calma, el NO APTO que enseña es **falso**: lo motiva una
`ISO/IEC 20000` que ese pliego no exige, sólo puntúa con 6 puntos como criterio de
adjudicación.

Analizada una segunda licitación para sustituirla —`2026/20`, Universidad de Jaén— salió el
mismo fallo con otra cara: el modelo metió en `certifications` los certificados de estar al
corriente de obligaciones tributarias y con la Seguridad Social, que son papeleo que
presenta cualquier licitador. Repasados los seis análisis que hay en la base, **cuatro
llevan basura en ese campo**, y en uno de ellos una de las «certificaciones exigidas» es
literalmente la cadena `citation`.

O sea que no es un caso raro: es un fallo reproducible en la salida más visible del
producto. La captura del README acabó siendo `040-2026-0075` —un APTO CON RESERVAS con su
razón citada y sus cifras correctas—, que es honesto y además cuenta mejor el producto que
un NO APTO. Y el fallo entra en el README en un apartado de **limitaciones conocidas**, en
vez de esconderse: la tesis de este proyecto es que el veredicto es auditable, y ocultar un
modo de fallo conocido sería exactamente lo contrario.

Queda como lo primero de la 5.8.

### Estado al cerrar

Criterios 1 a 6, cumplidos. Las imágenes están versionadas en `docs/images/` y se enlazan
con ruta relativa; los enlaces internos comprobados uno a uno.
