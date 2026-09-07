# Fase 2 — Matching híbrido y perfil de proveedor

## Objetivo

El embudo antes que el agente: de las ~800 licitaciones diarias que PLACSP publica (ya acotadas al vertical de servicios informáticos desde la Fase 1) al puñado que de verdad encaja con un proveedor concreto, sin pasar nada por un LLM todavía. Al terminar la fase existe un perfil de proveedor real, un embudo de tres etapas (filtros duros → recuperación híbrida léxica+vectorial → fusión RRF) y un endpoint que devuelve los matches con su motivo de encaje.

## Decisiones de arquitectura tomadas en la planificación

- **Un único proveedor, sin multi-tenant.** El documento de diseño marca el multi-tenant como fuera de v1. El perfil de proveedor es una fila fija en la base de datos, no una tabla con una fila por usuario.
- **La decisión de embeddings (proveedor, dimensiones) se toma con datos, no antes.** Se pospone hasta tener un golden set pequeño y poder medir recall real sobre licitaciones reales, en vez de fijarla a ciegas al arrancar la fase. El corpus actual (miles de filas, no millones) hace que re-embeber sea barato — céntimos y minutos, no una migración cara — así que la decisión es barata de revertir y no bloquea el arranque.
- **pgvector indexa hasta 2000 dimensiones con el tipo `vector` normal (4000 con `halfvec`).** Cualquier modelo candidato para la Etapa 2 vectorial tiene que caber ahí; es el criterio real que acota la elección, más que el coste.

## Subfases

1. **2.1 — Perfil de proveedor**
   Dominio `providers/`: modelo, schema, repositorio, migración. Perfil real cargado (no un seed ficticio).

2. **2.2 — Etapa 1 del embudo: filtros duros**
   CPV, importe, estado, provincia en SQL — instrumentado para poder medir cuántas licitaciones sobreviven a este escalón.

3. **2.3 — Recuperador léxico**
   `tsvector` sobre el objeto del contrato (columna generada, configuración `spanish`, índice GIN).

4. **2.4 — Golden set y decisión de embeddings**
   Conjunto pequeño anotado a mano sobre licitaciones reales, usado para medir recall@k de 2-3 candidatos a modelo de embeddings antes de elegir. El mismo artefacto sirve de base para el golden set de RAGAS en la Fase 4.

5. **2.5 — Recuperador vectorial**
   Columna `Vector(n)` con la dimensión decidida en la 2.4, tarea Celery de generación de embeddings, backfill del corpus existente.

6. **2.6 — Fusión y endpoint de matches**
   Reciprocal Rank Fusion sobre los dos rankings, endpoint que devuelve los matches con su explicación de por qué encajan.

7. **2.7 — Revisión de la fase**
   Repaso exhaustivo (mismo patrón que la 1.11), números reales del embudo para el README.
