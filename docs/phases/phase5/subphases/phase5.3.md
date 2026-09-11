# Subfase 5.3 — Reestructuración y rediseño del dashboard

## Plan acordado

La 5.2 dejó el backend corregido y el dashboard intacto. Esta subfase se ocupa de los
trece hallazgos de frontend de la revisión (E1–E13), del que no tiene límite de error
(G5) y de los cinco medios que viven en `frontend/` (M1, M2, M3, M6, M12).

El punto de partida no es malo: la paleta por roles de `globals.css` está bien montada y
se mantiene. Lo que falta es todo lo demás — jerarquía, estados, accesibilidad y una
organización que se parezca a la del backend.

**Restricción**: cero dependencias nuevas. Todo con lo que ya hay (Next 16, React 19,
Tailwind v4). Sin librería de componentes, sin librería de iconos, sin framework de
animación.

### Lo que hay que rehacer

**Estructura (E1, E2, E3)**

`src/components/` es una carpeta plana con dos ficheros, mientras `MatchCard`,
`MatchOrigin` y `Deadline` viven declarados dentro de `page.tsx` — que así mezcla
obtención de datos, composición de pantalla y presentación. El backend está organizado
por dominio y CLAUDE.md lo fija como regla; el frontend va a leerse igual:

```
src/
  app/            rutas: page, layout, loading, error, not-found
  components/
    ui/           primitivas sin conocimiento de dominio
    matches/      el listado y su "motivo de encaje"
    tenders/      la ficha
    analysis/     el panel, el veredicto y la extracción
  hooks/          useAnalysisPolling
  lib/
    api/          types · client · endpoints
    format.ts
```

`AnalysisPanel` son 250 líneas con cinco responsabilidades (ciclo de *polling*, arranque,
errores, veredicto, extracción). El ciclo de vida sale a un hook, que es además donde
aterrizan M1 y el tope de *polling*.

**Diseño (E4, E5, E6, E8, E9, E10, E11, E12, E13)**

- El importe y el plazo deciden si abres una licitación; hoy pesan lo mismo que el score
  RRF, que es diagnóstico interno. Suben de jerarquía, y el plazo se codifica por urgencia
  en vez de obligar a leer un número.
- El veredicto es la pieza diferencial del producto y aparece como una caja más. Pasa a
  abrir la ficha, con color semántico propio y la fidelidad de citas como medidor.
- Cinco minutos de análisis comunicados con un punto que parpadea. Se sustituye por las
  cuatro fases reales del grafo y el tiempo transcurrido.
- No hay escala tipográfica, ni radios, ni elevación, ni colores semánticos de veredicto:
  el ámbar y el rojo se escriben a mano fuera del sistema. Se extienden los *tokens* que
  ya existen, en los dos temas.
- La cabecera desaprovecha el único sitio donde cabe el argumento del producto. Con las
  cuentas por etapa que la 5.2 añadió a `GET /matches`, puede enseñar la reducción real.
- El estado vacío puede decir en qué etapa se quedó el embudo en lugar de "no hay nada".
- Ordenación por plazo / importe / RRF en cliente, sin tocar el backend.

**Robustez y accesibilidad (G5, E7, M1, M2, M3, M6, M12)**

- `error.tsx`, `not-found.tsx` y `loading.tsx` en ambas rutas: hoy cualquier fallo de la
  API —incluido el 404 previsto de "perfil sin sembrar"— es la pantalla de error genérica
  de Next.
- El "motivo de encaje" vive en un atributo `title`, invisible para teclado y lector de
  pantalla. El estado que cambia solo no tiene `aria-live`. Las fechas son texto plano.
  No hay estilo de `:focus-visible`. Y `text-muted` sobre `surface-muted` queda en ~4,3:1,
  por debajo del 4,5:1 que exige AA.
- `setInterval` con *callback* asíncrono se solapa si una respuesta tarda más que el
  intervalo; el error del panel no se limpia tras un reintento con éxito; los enlaces a
  fichas no codifican el expediente mientras el cliente de API sí lo hace (407 expedientes
  del corpus llevan espacios); `next.config.ts` está vacío; y la ficha no tiene
  `generateMetadata`, así que todo enlace compartido se previsualiza igual.

**Contrato con el backend**

`GET /matches` cambió en la 5.2: `total` es ahora la salida real del embudo, hay un
`returned` con el tamaño de página y un objeto `funnel` con las cuentas por etapa. Los
tipos escritos a mano en `lib/api` hay que ponerlos al día — y son justo la clase de
desincronización que no tiene red, así que queda anotado.

### Criterios de aceptación

1. `npm run lint` y `npm run build` limpios en `frontend/`.
2. Con la API parada, `/` muestra una pantalla de error propia con opción de reintentar —
   no la pantalla genérica de Next. Con la API levantada, la portada enseña la reducción
   del embudo con números reales.
3. La ficha de una licitación con análisis completado abre con el veredicto, y su título
   de pestaña nombra la licitación, no el producto.
4. Un análisis en curso muestra fase y tiempo transcurrido, y deja de consultar por su
   cuenta pasado el tope, ofreciendo reintentar.
5. Ninguna dependencia nueva en `package.json`.

## Progreso

### Estructura

`components/` pasa a espejar la división del backend —`ui/`, `matches/`, `tenders/`,
`analysis/`— que es lo que CLAUDE.md ya exigía de `src/`. `MatchCard`, `MatchOrigin` y
`Deadline` salen de dentro de `page.tsx`, que mezclaba obtención de datos, composición y
presentación en un solo fichero.

`AnalysisPanel` se parte: el ciclo de vida se va a `hooks/useAnalysisPolling`, y el
veredicto, la extracción, el progreso y la cita son cada uno su componente. Lo que queda
en el panel es decidir *cuál* enseñar, que es la parte que de verdad le corresponde.

`lib/api.ts` se parte en `types` / `client` / `endpoints`. Los tipos siguen escritos a
mano contra los esquemas Pydantic, y esta subfase es la prueba de por qué eso tiene un
coste: la 5.2 cambió `MatchListResponse` —`total` dejó de significar "cuántos vinieron" y
apareció `funnel`— y nada lo habría detectado aquí. Queda escrito en el propio fichero:
generar desde `/openapi.json` es lo que hay que hacer el día que aparezca una tercera
pantalla.

### Jerarquía

El importe y el plazo deciden si un proveedor abre una licitación; compartían una rejilla
de cuatro columnas con el score RRF, que es diagnóstico interno. Ahora abren la tarjeta con
tamaño propio, el score baja a metadato, y el plazo se colorea por urgencia en vez de pedir
que alguien interprete un número.

El veredicto —el producto entero— abre la ficha, con su color semántico propio y la
fidelidad de citas como medidor en vez de una línea de texto gris. Se renderiza desde el
mismo componente cliente que el panel y no desde la página: llega por el mismo *polling*,
y el servidor sólo conoce el estado del primer render, no el de tres minutos después.

La cabecera enseña la reducción con las cuentas por etapa que la 5.2 añadió: **3.583 →
508 → 131 → 61**. Ese dato no aparecía en ninguna parte, y es el argumento del producto.
El estado vacío dice ahora en qué etapa se vació, que es lo único accionable.

### Robustez y accesibilidad

`error.tsx`, `not-found.tsx` y `loading.tsx` existen por primera vez. El fallo más probable
de todos —la API sin levantar, rutinario en algo que corre en la máquina de quien lo usa—
producía la pantalla de error genérica de Next. El cliente distingue ahora "no se pudo
conectar" de "la API dijo que no", porque son dos mensajes distintos para quien lo lee.

El *polling* se reprograma a sí mismo en vez de correr sobre un intervalo que apila
peticiones si una tarda más de cinco segundos, y se rinde a los quince minutos ofreciendo
reintentar en lugar de perseguir para siempre una corrida que nadie va a terminar. El botón
aparece también en ese estado: antes sólo salía para "nunca analizado" y "falló".

El motivo de encaje deja de vivir en un atributo `title` —invisible para teclado— y pasa a
ser texto. El estado que cambia solo se anuncia con `aria-live`. Las fechas son `<time>`.
El foco tiene un estilo único declarado una vez. Y `--muted` se oscurece de `#6b6b63` a
`#5d5d55`: sobre `--surface-muted` medía ~4,3:1, por debajo del 4,5:1 que AA exige para
texto pequeño, y era justo el par de todas las etiquetas.

Un detalle que salió del propio Next: el *prop* de recuperación de `error.tsx` es `retry`,
no `reset`. Cambió en Next 16, y está documentado en `node_modules/next/dist/docs/`.

### Lo que no lleva

**Tests.** El frontend no tiene ninguno, y montarlos exigiría una dependencia nueva
(Vitest o Playwright), que no se añade sin avisar. Queda anotado como deuda explícita: la
comprobación real de esta subfase han sido `npm run build` —que también es la puerta de
tipos— y una corrida contra la API levantada con el corpus real.

**CSP.** `next.config.ts` lleva `X-Content-Type-Options`, `Referrer-Policy` y
`X-Frame-Options`, pero no una *Content-Security-Policy*: un `connect-src` con sentido hay
que construirlo desde `NEXT_PUBLIC_API_URL`, y eso es una decisión de la 5.4.

### Estado al cerrar

`npm run lint` y `npm run build` limpios. Verificado contra la API real: la portada pinta
3.583 → 508 → 131 → 61 con los números del corpus, los enlaces a expedientes con barras
funcionan, y el título de pestaña de una ficha nombra la licitación en vez del producto.

### Repaso final, mirando la aplicación en marcha

Levantada la aplicación entera y capturada la pantalla —no sólo comprobado el HTML—
aparecieron tres cosas que ninguna comprobación automática iba a dar:

**El embudo llamaba "en plazo" a licitaciones cerradas, y eran la mayoría.** En la portada
se veía la contradicción dentro de la misma tarjeta: "En plazo de presentación" arriba y
"Plazo cerrado" justo debajo. La Etapa 1 filtraba sólo por el código de estado de PLACSP,
que no se actualiza de forma fiable al vencer el plazo: **429 de las 508 que el estado
daba por abiertas (el 84%) tenían la fecha ya pasada**. La etapa exige ahora las dos
condiciones, y el embudo pasa de `3.583 → 508 → 131 → 61` a `3.583 → 76 → 27 → 6`.

Seis resultados hacen la pantalla más vacía, pero son los que de verdad se pueden
presentar, y la premisa del diseño híbrido aguanta igual de bien: **3 de los 6 los trajo
sólo el recuperador vectorial**. Los números del README se han rehecho con esta corrida.

Un efecto colateral que merece quedar escrito: el golden set de la 2.3 se anotó a mano
contra los supervivientes de Etapa 1 de entonces, y su test comprobaba igualdad exacta con
los de hoy. Esa igualdad no podía sostenerse — una licitación abandona esa población sola,
en cuanto vence su plazo. El test pasa a comprobar la contención en la dirección que
importa para medir recall@k: que no se rankee nada sin etiquetar. Perseguir la igualdad en
el otro sentido habría significado reanotar en silencio las etiquetas hechas a mano.

**Un fallo propio de la 5.2.** Un análisis hace dos llamadas HTTP —el PCAP a PLACSP y la
extracción a OpenRouter— y ambas lanzan `HTTPStatusError`, así que el mapeo por tipo
traducía un 429 del modelo como "el servidor de PLACSP devolvió un error". Encontrado
mirando una fila real. Ahora se distingue por el host, y el 429 tiene su propio mensaje:
es el fallo más probable de toda la cadena, porque el nivel gratuito son 50 peticiones al
día.

**Dos detalles de pantalla.** El embudo escribía `3583` porque `es-ES` no agrupa cuatro
dígitos por defecto, mientras toda la documentación del proyecto escribe `3.583`. Y la
explicación del motivo de encaje se repetía idéntica en las veinte tarjetas —casi todas
son léxico+vectorial—, así que pasa a ser una leyenda única encima del listado, donde el
caso "solo vectorial" puede llevarse la frase que de verdad merece.
