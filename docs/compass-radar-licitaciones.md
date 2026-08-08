---
proyecto: Compass
estado: Diseño
bloque_principal: "06 - Orquestación de Agentes IA"
stack: [FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, pgvector, LangGraph, Celery, Redis, Langfuse, RAGAS, Next.js]
tags: [proyecto, portfolio, ia, rag, agentes]
---

# 🧭 Compass — Radar de contratación pública

> Documento de diseño del proyecto. Nombre alternativo si se prefiere algo más literal: *Licita* o *Prospecta*.

---

## 1. Encuadre del problema

### 1.1. Qué es exactamente (y qué no)

Compass **no** es un buscador de ayudas ni subvenciones. Es un radar de **contratos públicos**.

La distinción importa porque cambia el discurso entero del proyecto:

| | Subvención / ayuda | Licitación pública |
|---|---|---|
| Dirección del dinero | La administración **te da** dinero | La administración **te compra** un servicio |
| Rol de la empresa | Solicitante | Proveedor / contratista |
| Qué haces | Solicitas, cumples requisitos, justificas gasto | Compites presentando una oferta, ejecutas y facturas |
| Ejemplo | Kit Digital | El ayuntamiento saca a concurso rehacer su sede electrónica |

**Frase de una línea (la que entiende un recruiter no técnico):**
> Compass ayuda a PYMEs y autónomos a encontrar contratos públicos a los que puedan optar de verdad, y a decidir rápido si merece la pena presentarse.

### 1.2. El encuadre malo vs. el bueno

**Encuadre malo:** "una herramienta para encontrar licitaciones". El buscador oficial ya existe, es público y es gratis. Con este encuadre, el proyecto es un scraper con buscador y no hay nada que contar.

**Encuadre bueno:** hay dos dolores distintos y ninguno se resuelve con un buscador.

1. **Ruido.** Se publican cientos de miles de anuncios al año. A un estudio de desarrollo de Sevilla le interesan quizá quince.
2. **Los metadatos no te dicen si puedes presentarte.** El feed te da CPV, importe, órgano y plazo. Pero *"¿cumplo la solvencia económica?"*, *"¿me exigen ISO 27001?"*, *"¿cuánto pesa el precio frente a la valoración técnica?"* está enterrado en el PCAP: un PDF de 60–80 páginas de cláusulas numeradas.

El segundo dolor es el que justifica que exista un agente. **Preparar una oferta cuesta días de trabajo de una persona.** Descubrir en el día tres que exigían una cifra de negocio que no alcanzas es tirar ese tiempo a la basura. Compass lee el pliego y te dice *antes de empezar* si estás fuera y por qué cláusula concreta.

### 1.3. Por qué este proyecto para portfolio

- **La demo se abre con datos reales de hoy.** Sin seeds, sin "usuario demo", sin capturas explicando lo que haría. Es rarísimo en un portfolio junior.
- **Absorbe el proyecto "Compass" original** (RAG avanzado + RAGAS) dándole un dominio real: chunking estratégico, re-ranking, hybrid search y evaluación dejan de ser una demo de técnica y pasan a ser necesarios.
- **Cubre los huecos del roadmap** que no demuestra ningún otro proyecto: ingesta periódica de datos externos sucios, procesamiento asíncrono con colas, observabilidad, evals y defensa ante prompt injection con contenido no confiable.
- **No repite el dominio "código"** de Nexus.

---

## 2. Fuentes de datos

### 2.1. PLACSP (fuente principal, v1)

Plataforma de Contratación del Sector Público — sindicación ATOM.

Características que condicionan el diseño:

- Se publican **diariamente** las actualizaciones producidas el día anterior.
- Cada fichero contiene un **máximo de 500 entradas**; las siguientes están en el fichero referenciado por el enlace `next` del ATOM.
- **Una misma licitación puede aparecer tantas veces como modificaciones haya sufrido.**
- Existen **históricos comprimidos**: por año desde 2012 y por meses del año en curso — permite arrancar con corpus sin esperar semanas de ingesta.
- Formato de contenido: **CODICE**, XML basado en UBL (OASIS). Especificación de ~250 páginas.
- Las entradas retiradas se marcan con un elemento de entrada eliminada, no desaparecen.

### 2.2. Fuentes de fase 2 (fuera de v1)

- **BDNS** — Base de Datos Nacional de Subvenciones.
- **API REST de la Junta de Andalucía** para subvenciones concedidas: OpenAPI propio, descarga en JSON/CSV, actualización diaria, licencia CC BY 4.0.
- Plataformas autonómicas agregadas y feeds propios (ej. Comunidad de Madrid, también ATOM + CODICE).
- TED, a escala europea.

> ⚠️ Mezclar contratos y subvenciones en la v1 multiplica el modelo de datos y difumina el relato. Un solo eje en la primera versión.

---

## 3. Capa 1 — Ingesta

Tres decisiones de ingeniería que salen directamente de cómo es la fuente. Las tres son excelente material de entrevista.

### 3.1. Idempotencia

Como el feed republica la misma licitación en cada modificación:

- La escritura es **upsert por identificador de expediente**, nunca insert.
- Las retiradas son **cambio de estado**, nunca borrado físico.
- Conservas historial de versiones si quieres poder mostrar "el plazo se amplió el día X".

> Frase para el README: *"Diseñé la ingesta asumiendo entrega repetida, porque la fuente republica cada entidad en cada modificación."*

### 3.2. Paginación con cursor

Sigues el enlace `next` hasta agotar el feed, persistiendo el último punto procesado para poder reanudar tras un fallo. Nada exótico, pero es un patrón real de ingesta.

### 3.3. Mapeo parcial y deliberado de CODICE

**No mapees el esquema completo.** Es una trampa de semanas.

Define un modelo Pydantic con los 12–15 campos que de verdad necesitas y descarta el resto:

- Número de expediente
- Órgano de contratación
- Objeto del contrato
- Códigos CPV
- Importe (con y sin IVA), valor estimado
- Tipo de contrato (servicios / suministros / obras)
- Procedimiento (abierto, simplificado, negociado…)
- Estado (anuncio previo, en plazo, pendiente de adjudicación, adjudicada, resuelta)
- Fecha y hora límite de presentación
- Lugar de ejecución (provincia / municipio)
- URLs de los pliegos (PCAP, PPT)
- URL de la licitación en la plataforma
- Fecha de publicación y de última actualización

**El alcance acotado es la decisión, no una carencia.** Dilo así en el README.

---

## 4. Capa 2 — El embudo de matching

La pieza más interesante del proyecto: es un problema de **coste**, y se resuelve con **arquitectura**, no con un prompt mejor.

No puedes pasar ~800 anuncios diarios por un LLM. Cascada de barato a caro:

### Etapa 1 — Filtros duros (SQL, sin IA)

CPV dentro del conjunto que interesa al proveedor, importe dentro de rango, estado "en plazo", provincia o ámbito. Determinista, milisegundos, **elimina ~95%**.

### Etapa 2 — Recuperación híbrida

El proveedor describe en texto libre qué hace:
> *"Desarrollamos aplicaciones web a medida y mantenemos portales institucionales."*

Se cruza contra el objeto del contrato combinando dos recuperadores:

- **Léxico** — `tsvector` de PostgreSQL. Captura términos exactos y raros: "Drupal", "sede electrónica", "ENS", "SIGEM".
- **Vectorial** — pgvector. Captura intención y sinónimos.
- **Fusión** — Reciprocal Rank Fusion (RRF) sobre ambos rankings.

> **Por qué híbrido y no solo vectorial:** la búsqueda vectorial falla justo con los términos raros y muy específicos, que en este dominio son precisamente los que deciden el encaje. Este es el punto donde haces RAG avanzado *de verdad* en lugar de leer sobre él.

### Etapa 3 — Análisis del pliego con LLM

Solo para el top-N que sobrevive. Caro, lento, asíncrono, y **bajo demanda o presupuestado**, nunca sobre todo el volumen.

> 📊 **Documenta el embudo con números reales** en el README: cuántos anuncios entran, cuántos sobreviven a cada etapa, cuántos llegan al LLM. Es la diferencia entre *"usé un LLM"* y *"diseñé un sistema con un LLM dentro"*.

---

## 5. Capa 3 — El agente analista de pliegos

Aquí entra LangGraph, con un patrón **distinto** al Router + Ensemble de Nexus, para no repetir narrativa.

### 5.1. Chunking consciente de la estructura

Un pliego **no es prosa continua**: son cláusulas numeradas con título. Trocear cada 500 tokens destroza esa estructura y parte cláusulas de solvencia por la mitad.

**Estrategia:** chunkear por cláusula, conservando número y título como metadatos del chunk.

Esto por sí solo dispara la calidad, y es un hallazgo que puedes documentar con métricas antes/después. Material de README de primera.

### 5.2. Extracción estructurada con citas

No se le pide *"resúmeme el pliego"*. Se le pide un **esquema Pydantic cerrado**, campo a campo:

- Solvencia económica y financiera exigida
- Solvencia técnica o profesional
- Certificaciones requeridas (ISO 9001, 27001, ENS…)
- Criterios de adjudicación con sus porcentajes (precio vs. técnica)
- Garantía provisional y definitiva
- Plazo de ejecución
- Fecha y hora límite de presentación
- Admisión de subcontratación
- Lotes y si se puede optar a lotes sueltos

**Cada campo lleva la cláusula y la página de origen.** La cita no es decorativa: es lo que hace el output verificable y lo que permite medir alucinación en la capa de evals.

### 5.3. Veredicto contrastado

Con el perfil del proveedor (facturación por ejercicio, años de actividad, certificaciones, trabajos previos similares), el sistema emite:

`APTO` / `APTO CON RESERVAS` / `NO APTO`

Con motivo concreto y citado:
> *"No apto: exigen cifra de negocio de 300.000 € en alguno de los tres últimos ejercicios (cláusula 12.2) y tu perfil declara 180.000 €."*

> 🎯 **Reparto de responsabilidades — el punto clave del diseño:**
> **el LLM extrae, el código decide.** El veredicto es determinista una vez extraídos los datos; la comparación la hace Python, no el modelo. Esto es exactamente lo que se pregunta en entrevistas de diseño de sistemas con IA.

### 5.4. Caché por documento

Hash del PDF → análisis guardado. Si dos usuarios miran la misma licitación, el segundo es gratis. Ahorro de coste y ventaja de producto en la misma decisión.

---

## 6. Capa 4 — Transversales (donde cierras huecos del roadmap)

### 6.1. Procesamiento asíncrono con colas

Ingesta diaria y análisis de pliegos tardan minutos. Ninguna puede vivir dentro de un request HTTP.

- **Celery + Redis** — más retorno en CV, es el nombre que aparece en ofertas.
- **ARQ** — menos fricción con el async de FastAPI.

**Recomendación:** Celery, por retorno en CV, aun sabiendo que ARQ encaja técnicamente mejor con FastAPI. Y documenta que lo sabes.

Tareas en cola: ingesta diaria, generación de embeddings, análisis de pliegos, envío del digest por email.

### 6.2. Observabilidad — Langfuse

Trazas por análisis, con tokens y coste desglosado.

> 🎯 **La métrica estrella del README:** *"Coste medio de analizar un pliego: 0,0X €."*
> Casi ningún perfil junior mide el coste de sus agentes. Ese número, dicho en entrevista, te sitúa por encima de la media al instante.

### 6.3. Evaluación — RAGAS

- **Golden set anotado a mano:** 25–30 pliegos con las respuestas correctas (solvencia real, certificaciones reales).
- **Métricas:** fidelidad (¿lo extraído está de verdad en el documento?), precisión de contexto, recall de contexto.
- **Convertido en test de regresión:** cuando cambies el chunking, el modelo o el prompt, sabes si mejoraste o te engañaste a ti mismo.

> Este es el punto exacto donde el proyecto deja de ser una demo.

### 6.4. Seguridad — Prompt injection

El agente ingiere **PDFs de terceros**. Que un organismo público no vaya a atacarte no elimina el vector: el patrón *"el agente ingiere contenido no confiable"* es idéntico al de cualquier sistema real.

Mitigaciones:
- Separación estricta entre contenido no confiable y prompt de sistema (delimitadores, roles distintos).
- **El agente lector no tiene ninguna herramienta de escritura.** Principio de menor privilegio.
- Validación del output contra el esquema Pydantic **antes** de persistir.
- No loguear contenido sensible en las trazas de observabilidad.

Un párrafo corto en el README demostrando que piensas en esto vale mucho.

### 6.5. CI — GitHub Actions

- Job principal: pytest + linting + tipos en cada push.
- Job separado de **evals**: no bloquea el merge, pero deja el resultado visible.

---

## 7. Alcance del MVP

### 7.1. Dentro

- **Un vertical acotado**: CPV de servicios informáticos, o ámbito Andalucía. Volumen manejable y dominio que entiendes.
- Ingesta diaria automatizada + carga histórica inicial.
- Perfil de proveedor (descripción, CPV, rango de importe, facturación, certificaciones).
- Matching híbrido con explicación de por qué encaja.
- Análisis de pliego bajo demanda desde la ficha de la licitación.
- Digest diario por email.
- Dashboard en Next.js.

### 7.2. Fuera de la v1 (y dicho explícitamente en el README)

- Subvenciones (BDNS).
- Plataformas autonómicas agregadas.
- Multi-tenant con facturación.
- Generación automática de la oferta.
- Analítica histórica de adjudicaciones y de competidores.
- OCR de pliegos escaneados.

> Declarar el alcance con intención es señal de criterio. Que se note que no lo hiciste **porque lo decidiste**, no porque no te dio tiempo.

---

## 8. Fases de desarrollo

| Fase | Contenido | Por qué en este orden |
|---|---|---|
| 1 | Ingesta y normalización, **sin nada de IA**, con datos reales cargados | Al terminarla ya tienes algo que se abre y enseña datos reales |
| 2 | Matching híbrido + perfil de proveedor | El embudo antes que el agente |
| 3 | Agente de pliegos con extracción citada | La pieza cara, ya con el volumen filtrado |
| 4 | Evals y observabilidad | Sin esto no sabes si la fase 3 funciona |
| 5 | Frontend, email y despliegue | |
| 6 | CI y README narrativo | |

---

## 9. Riesgos identificados

| Riesgo | Mitigación |
|---|---|
| El parseo de CODICE es aburrido y no luce | Mapeo parcial deliberado, 12–15 campos |
| Pliegos escaneados sin capa de texto | Detectarlos y marcarlos como no analizables en v1. Nada de OCR |
| Tentación de ampliar fuentes | Subvenciones y plataformas autonómicas **fuera** de v1. Es lo que mata el proyecto |
| Coste de tokens | Embudo de 3 etapas + caché por documento + presupuesto por usuario |
| Volumen de datos | Verticalizar desde el día uno |

---

## 10. El gancho — cómo se presenta

### 10.1. Por audiencia

- **Lead técnico / futuro compañero:** engancha por los problemas reales de dentro — idempotencia, embudo de coste, rediseño del chunking, coste medido, golden set. Son cinco conversaciones técnicas que salen solas.
- **CTO / perfil de negocio:** entiende el problema en diez segundos porque es un problema de dinero.
- **Recruiter no técnico:** no leerá el README. Captará una frase — la del punto 1.1.

### 10.2. Requisitos innegociables de la demo

> El gancho no está en la idea, está en la ejecución de la demo. Un cron caído el martes y una tabla vacía se cargan el proyecto entero.

- **Modo demo sin registro**, con perfil de empresa de ejemplo precargado.
- **Datos reales de esta semana visibles en menos de 3 segundos.**
- **Al menos un pliego pre-analizado y cacheado**, para que el momento estrella (análisis con citas a cláusulas) sea instantáneo y no dependa de una llamada en vivo.
- **README con narrativa**, no lista de tecnologías: qué problema, qué decidiste, qué probaste que no funcionó, qué mides.

### 10.3. Caducidad del gancho

Hoy (agosto 2026) un proyecto con evals y coste medido sigue siendo diferenciador porque poca gente junior lo hace. **Dentro de año y medio será el mínimo.** Razón de más para que salga bien y pronto, de cara a la temporada de contratación de septiembre.

---

## 11. Enlaces internos

- [[Palco - Plataforma de ticketing con aforo numerado]]
- [[Nexus]]
- [[Bloque 6 - Orquestación de Agentes IA]]
- [[Bloque 5 - Bases de Datos]]
- [[Bloque 8 - Testing]]
- [[Bloque 9 - Seguridad]]
