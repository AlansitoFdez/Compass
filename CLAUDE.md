# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Estado del proyecto

Compass tiene un backend FastAPI mínimo en `backend/` (subfase 1.1 completada): esqueleto de la app con patrón de routers agregados, un health check y un primer test real. Todavía falta toda la infraestructura (PostgreSQL+pgvector, Redis, Celery — subfases 1.2 y 1.9) y el primer endpoint de dominio (`GET /tenders`, subfase 1.10). El frontend Next.js no existe todavía (Fase 5).

Comandos reales, ejecutados desde `backend/`:

- `uv sync` — instala dependencias.
- `uv run uvicorn compass.main:app --reload` — servidor de desarrollo (`GET /health`, `GET /docs`).
- `uv run pytest` — tests.
- `uv run ruff check .` / `uv run ruff format .` — lint y formato.

## Qué es Compass

Un radar de **licitaciones públicas** españolas, no de subvenciones. Ingiere el feed ATOM/CODICE de PLACSP, filtra los ~800 anuncios diarios hasta el puñado relevante para un proveedor dado, y usa un agente LLM para leer el pliego (PCAP) de la licitación resultante y emitir un veredicto citado (APTO / APTO CON RESERVAS / NO APTO) contra el perfil del proveedor.

El razonamiento completo, el modelo de datos y las decisiones de diseño están en `docs/compass-radar-licitaciones.md` — léelo antes de tomar decisiones de arquitectura, no te quedes solo con este resumen.

Stack planeado: FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL + pgvector, LangGraph, Celery + Redis, Langfuse, RAGAS, Next.js.

## Arquitectura (planeada)

Cuatro capas, detalladas en el documento de diseño:

1. **Ingesta** — upsert por expediente (el feed republica cada licitación en cada modificación; las retiradas son un cambio de estado, nunca un borrado físico), paginación por cursor siguiendo el enlace `next` del ATOM, y un mapeo deliberadamente parcial de CODICE (~12-15 campos, no la especificación completa de ~250 páginas).
2. **Embudo de matching** — cascada de coste de barato a caro: (1) filtros SQL duros (CPV/importe/estado/provincia, elimina ~95%), (2) recuperación híbrida (`tsvector` léxico + pgvector semántico, fusionados con RRF), (3) análisis del pliego con LLM solo para el top-N que sobrevive.
3. **Agente analista de pliegos (LangGraph)** — chunking consciente de la estructura (no por tokens fijos), extracción estructurada con citas a cláusula/página, lógica de veredicto determinista en Python (el LLM extrae, el código decide — nunca dejar que el modelo calcule el veredicto él mismo), caché por documento vía hash del PDF.
4. **Transversales** — Celery/Redis para todo lo que no pueda vivir dentro de un request HTTP (ingesta diaria, embeddings, análisis de pliegos, digest por email); trazas de Langfuse con coste por análisis; evals con RAGAS contra un golden set anotado a mano como gate de regresión; defensas de prompt injection ya que el agente ingiere PDFs de terceros no confiables (el agente lector no tiene herramientas de escritura, separación estricta entre contenido no confiable y prompt de sistema, validación contra el esquema antes de persistir).

## Alcance de la v1

Explícitamente fuera de alcance — no añadir sin que el usuario lo pida primero, porque el scope creep aquí es un riesgo identificado en el documento de diseño:

- Subvenciones (BDNS) — solo contratos, un único eje.
- Plataformas autonómicas agregadas más allá de PLACSP.
- Multi-tenant con facturación, generación automática de ofertas, analítica histórica de competidores, OCR de pliegos escaneados.

## Convenciones del proyecto

- **Idioma del código:** inglés siempre — nombres de funciones, variables, clases, etc. La documentación (este archivo, `docs/`) va en español.
- **Variables de entorno:** nunca se lee ni se modifica el `.env` real con datos reales. El archivo de referencia es siempre `.env.example`; cualquier comparación o validación de variables se hace contra ese archivo, no contra el real.
- **Documentación continua por fases:** carpeta `docs/phases/`, con una subcarpeta por fase grande del roadmap (`phase1/`, `phase2/`...). Dentro de cada una:
  - `phaseX.md` — desglose completo de la fase: en qué subfases se divide, qué se toca y qué se construye en cada una. Se escribe/actualiza en la conversación de planificación de la fase, antes de empezar a construir.
  - `subphases/` — un `.md` por subfase con nombre `phaseX.Y.md` (ej. `docs/phases/phase1/subphases/phase1.1.md`), creado cuando esa subfase arranca. Antes de empezar cada subfase hay una conversación de planificación (qué se va a hacer, qué se va a tocar); el `.md` registra el plan acordado y, según avanza el trabajo, qué se hizo, qué se tocó y por qué.

## Trabajando en este repo

- Claude puede hacer commits, pero sin firma ni co-autoría de Claude (sin trailers tipo "Generated with Claude Code" o "Co-Authored-By: Claude") y sin hacer push a GitHub. El push a GitHub lo hace siempre el usuario.
