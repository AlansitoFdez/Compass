# Compass

Radar de **licitaciones públicas** españolas para proveedores que compiten por contratos y no dan abasto revisando los cientos de anuncios que [PLACSP](https://contrataciondelestado.es) publica cada día.

Compass ingiere el feed ATOM/CODICE de PLACSP, filtra ese volumen hasta el puñado de licitaciones relevantes para un proveedor concreto, y (en una fase posterior) usa un agente LLM para leer el pliego de las que sobreviven y emitir un veredicto citado — APTO / APTO CON RESERVAS / NO APTO — contra el perfil de ese proveedor.

No es un buscador de subvenciones ni de ayudas: es un radar de contratos que la administración compra, no de dinero que reparte.

## Estado del proyecto

- ✅ **Fase 1 — Ingesta y normalización.** El feed de PLACSP se ingiere de forma incremental (marca de agua sobre `atom:updated`, sin re-recorrer el feed en cada corrida), se parsea el CODICE, se filtra por el vertical de servicios informáticos (CPV división 72) y se persiste con upsert idempotente por `expediente` — una licitación republicada actualiza la misma fila, nunca crea una nueva ni se borra físicamente.
- ✅ **Fase 2 — Matching híbrido y perfil de proveedor.** Un embudo de tres etapas reduce el corpus completo al puñado que de verdad encaja con un proveedor: filtros duros en SQL, recuperación híbrida (léxica + vectorial) y fusión por Reciprocal Rank Fusion. Nada de esto pasa por un LLM todavía — es determinista y auditable.
- ⏳ **Fase 3 — Agente analista de pliegos**, con LangGraph, sobre el puñado que sobrevive al embudo. Sin empezar.

El detalle completo de cada subfase, con la evidencia y el razonamiento detrás de cada decisión, vive en `docs/phases/`.

## El embudo, con números reales

Medido contra el corpus real (persistido desde PLACSP) y el perfil de proveedor sembrado (desarrollo y mantenimiento de portales web institucionales, con Drupal/WordPress, para el sector público).

### Fase 1 — Ingesta

| Etapa | Resultado |
|---|---|
| PLACSP publica, todas las categorías | del orden de 800 anuncios/día (estimación de diseño, no medida aquí) |
| Filtrado al vertical de servicios informáticos (CPV división 72) | **3.583** licitaciones persistidas |

### Fase 2 — Matching, para el proveedor sembrado

| Etapa | Sobreviven |
|---|---|
| Corpus completo (Fase 1) | 3.583 |
| Etapa 1 — en plazo de presentación | 508 |
| Etapa 1 — + CPV del proveedor | 131 |
| Etapa 1 — + rango de presupuesto | 61 |
| Etapa 1 — + ámbito geográfico | 61 |
| Etapa 2 — recuperación léxica (`tsvector`, al menos un término compartido) | 28 |
| Etapa 2 — recuperación vectorial (embebidas, listas para rankear) | 61 |
| Fusión RRF — únicas tras combinar ambos rankings | **52** |
| — de las cuales, encontradas por ambos recuperadores | 26 |
| — solo por el léxico | 2 |
| — solo por el vectorial | 24 |

**La premisa del diseño híbrido, confirmada con números reales**: 24 de las 52 licitaciones finales (46%) las trajo *solo* el recuperador vectorial — se habrían perdido con una búsqueda puramente léxica. Y el léxico sigue aportando 2 que el vectorial no vio. Ninguno de los dos por sí solo cubre lo que cubren juntos.

## Stack

Python 3.13 (tipado estricto, `mypy --strict`) · FastAPI async sobre Uvicorn · PostgreSQL 17 + pgvector, vía SQLAlchemy async y Alembic · Celery sobre Redis para la ingesta diaria y el backfill de embeddings · `ibm-granite/granite-embedding-278m-multilingual` para los embeddings semánticos, corrido en local · pytest, ruff.

## Arrancar en local

Requiere Docker y [uv](https://docs.astral.sh/uv/).

```bash
# Infraestructura (Postgres en :5433, Redis en :6379)
docker compose up -d

# Desde backend/, con un .env configurado
cd backend
uv run alembic upgrade head
uv run uvicorn compass.main:app --reload   # API en http://localhost:8000/docs

# En otras dos terminales, para la ingesta diaria y el backfill de embeddings
uv run celery -A compass.core.celery_app worker --pool=solo --loglevel=info
uv run celery -A compass.core.celery_app beat --loglevel=info

# Carga inicial de datos (últimos 3 meses del vertical)
uv run python -m compass.ingestion.historical_loader
```

`uv run pytest` corre la suite completa contra Postgres y Redis reales (necesita la infraestructura de arriba levantada).
