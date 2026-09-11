# Compass

[![CI](https://github.com/AlansitoFdez/Compass/actions/workflows/ci.yml/badge.svg)](https://github.com/AlansitoFdez/Compass/actions/workflows/ci.yml)

Radar de **licitaciones públicas** españolas para proveedores que compiten por contratos y no dan abasto revisando los cientos de anuncios que [PLACSP](https://contrataciondelestado.es) publica cada día.

Compass ingiere el feed ATOM/CODICE de PLACSP, filtra ese volumen hasta el puñado de licitaciones relevantes para un proveedor concreto, y usa un agente LLM para leer el pliego de las que sobreviven y emitir un veredicto citado — APTO / APTO CON RESERVAS / NO APTO — contra el perfil de ese proveedor.

No es un buscador de subvenciones ni de ayudas: es un radar de contratos que la administración compra, no de dinero que reparte.

## Estado del proyecto

- ✅ **Fase 1 — Ingesta y normalización.** El feed de PLACSP se ingiere de forma incremental (marca de agua sobre `atom:updated`, sin re-recorrer el feed en cada corrida), se parsea el CODICE, se filtra por el vertical de servicios informáticos (CPV división 72) y se persiste con upsert idempotente por `expediente` — una licitación republicada actualiza la misma fila, nunca crea una nueva ni se borra físicamente.
- ✅ **Fase 2 — Matching híbrido y perfil de proveedor.** Un embudo de tres etapas reduce el corpus completo al puñado que de verdad encaja con un proveedor: filtros duros en SQL, recuperación híbrida (léxica + vectorial) y fusión por Reciprocal Rank Fusion. Nada de esto pasa por un LLM todavía — es determinista y auditable.
- ✅ **Fase 3 — Agente analista de pliegos.** Un grafo LangGraph descarga el PCAP de una licitación bajo demanda, detecta si tiene capa de texto, extrae los campos que deciden el encaje (solvencia, certificaciones, criterios, garantías, plazos, lotes) contra un esquema Pydantic cerrado, verifica en Python que cada cita existe de verdad en el texto parseado, y calcula el veredicto — nunca el LLM — comparando la extracción contra el perfil del proveedor. Resultado cacheado por hash de documento; el segundo usuario que mire la misma licitación no vuelve a pagar el análisis.
- ✅ **Fase 4 — Trazas, coste y evals.** Cada análisis queda trazado en Langfuse con tokens y coste reales; el golden set llegó a 25 pliegos anotados a mano y se corre contra el grafo de producción como gate de regresión; el prompt está endurecido contra inyección (delimitadores que el propio documento no puede cerrar); y cada push pasa por CI con lint, tipos y la suite contra Postgres y Redis reales.

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

### Fase 3 — Análisis de pliegos, coste y tiempo reales

Medido con tres análisis end-to-end reales (`POST /tenders/{expediente}/analyze` contra un pliego real del golden set de la 3.4, worker Celery real, modelo `nvidia/nemotron-3-super-120b-a12b:free` real) — no simulados.

| Corrida | Tiempo real | Coste |
|---|---|---|
| 1ª | 101 s | 0,00 € |
| 2ª | 75 s | 0,00 € |
| 3ª | 260 s | 0,00 € |

**Coste real: 0,00 € por análisis**, en las tres corridas — el nivel gratuito de OpenRouter elegido en la 3.4 se sostiene en producción, no solo en la medición inicial contra el golden set.

**El tiempo varía mucho de una corrida a otra** (75-260 s) porque el modelo es de razonamiento: la mayor parte del tiempo se va en una traza interna antes de emitir el resultado, y esa traza no tiene una duración fija. La 3.9 confirmó que el timeout que protege contra un cuelgue real (300 s) da margen de sobra sobre lo observado, sin cortar una corrida legítima.

### Fase 4 — Coste real, medido con Langfuse

Desde la 4.1, cada análisis queda trazado en [Langfuse](https://langfuse.com) con tokens y coste reales por llamada -- ya no una medición manual puntual como en la 3.9, sino observabilidad real que crece sola con cada análisis que se dispara. Números sobre las **64 trazas reales acumuladas** hasta hoy (`uv run python -m compass.analysis.cost_report`):

| Medida | Valor real |
|---|---|
| Análisis con extracción completada | **34** de 64 trazas |
| Tokens por análisis | 29.988 – 118.486 (**media 58.689**: 47.931 entrada / 10.758 salida) |
| Coste | **0,00 €** en el 100% |
| Tiempo real de extremo a extremo | 36 – 338 s (media 161 s) |

**El volumen de entrada varía mucho más de lo esperado** (30.000 a 118.000 tokens según el pliego): el prompt manda el texto completo del PCAP, página a página, sin trocear -- un pliego largo o con formato denso puede doblar o triplicar el de otro con el mismo número de páginas. **Coste real: 0,00 €** en el 100% de los análisis trazados, confirmando en producción -- ahora con tokens reales delante, no solo la cifra final -- lo que la 3.4 ya había medido contra el golden set: el nivel gratuito de OpenRouter se sostiene.

**Las otras 30 trazas quedan fuera de esa media, a propósito**: son llamadas que nunca devolvieron -- el tope de 300 s o los `429` del cupo diario gratuito, casi todas de las corridas del golden set de la 4.4. Promediar sus ceros respondería a "cuánto cuesta un intento", no a "cuánto cuesta analizar un pliego". La 4.7 encontró que el informe sí las estaba promediando, y que además contaba cada reintento como un análisis aparte.

## Stack

Python 3.13 (tipado estricto, `mypy --strict`) · FastAPI async sobre Uvicorn · PostgreSQL 17 + pgvector, vía SQLAlchemy async y Alembic · Celery sobre Redis para la ingesta diaria, el backfill de embeddings y el análisis de pliegos bajo demanda · `ibm-granite/granite-embedding-278m-multilingual` para los embeddings semánticos, corrido en local · LangGraph para el agente analista de pliegos, con `nvidia/nemotron-3-super-120b-a12b:free` (vía OpenRouter) como modelo de extracción · Next.js 16 con React 19 y Tailwind v4 para el dashboard · pytest, ruff.

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

Y el dashboard, desde `frontend/` (necesita la API levantada, y el worker para analizar pliegos):

```bash
npm install
cp .env.example .env.local
npm run dev   # http://localhost:3000
```

`uv run pytest` corre la suite completa contra Postgres y Redis reales (necesita la infraestructura de arriba levantada).

## CI

Cada push a `main` y cada pull request pasan por [GitHub Actions](.github/workflows/ci.yml): `ruff check`, `ruff format --check`, `mypy --strict` y la suite de tests contra un Postgres con pgvector y un Redis reales, levantados como *service containers* con las mismas imágenes que `docker-compose.yml`.

**Tres tests no corren ahí**, marcados con `@pytest.mark.real_corpus` y deseleccionados con `-m "not real_corpus"`: comparan el golden set y el embudo contra el corpus real de PLACSP persistido en local, y contra un corpus sintético no probarían nada. El eval de regresión del golden set (`uv run python -m compass.analysis.regression_eval`) queda fuera de CI por el mismo motivo — lee de esa misma base — y porque una corrida consume 25 de las 50 peticiones diarias del nivel gratuito de OpenRouter.
