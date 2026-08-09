# Fase 1 — Ingesta y normalización (sin IA)

## Objetivo

Ingesta y normalización de licitaciones de PLACSP, sin ningún componente de IA, con datos reales cargados. Al terminar la fase existe algo que se abre y enseña datos reales — no una demo con seeds ni un "usuario de prueba".

## Decisiones de arquitectura tomadas en la planificación

- **Vertical acotado desde la ingesta:** el filtro de CPV "servicios informáticos" se aplica en la propia ingesta (histórica y diaria), no solo como filtro de matching en fases posteriores. El volumen de la base de datos queda acotado desde el origen.
- **Celery + Redis desde esta fase:** se monta ya la infraestructura de colas, aunque de momento solo tenga una tarea (ingesta diaria vía beat). Las fases siguientes le añaden tareas nuevas (embeddings, análisis de pliegos, digest) sin rehacer nada.
- **Gestor de dependencias Python:** uv.
- **Cómo se ven los datos sin frontend todavía:** un endpoint FastAPI mínimo (`GET /tenders`), probable vía Swagger UI. El frontend Next.js no llega hasta la Fase 5.
- **Tests sobre la marcha:** cada subfase que toca lógica con comportamiento verificable incluye sus tests en el momento de construirla, no al final. La subfase de cierre (1.11) no es donde se escriben los tests por primera vez, sino una revisión exhaustiva de todo lo construido.

## Subfases

1. **1.1 — Scaffolding del backend**
   Estructura de carpetas, `uv init`, esqueleto FastAPI (health check), ruff (lint + format), pytest, `.env.example` inicial.

2. **1.2 — Infraestructura local**
   `docker-compose.yml` con PostgreSQL + pgvector y Redis. Verificación de que todo levanta y conecta.

3. **1.3 — Modelo de datos**
   Modelo SQLAlchemy + schema Pydantic para los 12-15 campos CODICE del expediente (ver sección 3.3 del documento de diseño). Primera migración con Alembic. Tests.

4. **1.4 — Filtro de vertical**
   Lista de códigos CPV de "servicios informáticos" y utilidad de filtrado reutilizable, usada tanto por la ingesta diaria como por la carga histórica. Tests.

5. **1.5 — Cliente ATOM**
   Fetch del feed PLACSP, paginación por cursor siguiendo el enlace `next`, persistencia del último punto procesado para poder reanudar tras un fallo. Tests.

6. **1.6 — Parser CODICE**
   Mapeo del XML CODICE a los 12-15 campos del modelo Pydantic. Tests con fixtures reales del feed.

7. **1.7 — Persistencia idempotente**
   Upsert por expediente, retiradas como cambio de estado (nunca borrado físico). Tests de idempotencia (mismo expediente procesado dos veces = una fila, actualizada).

8. **1.8 — Carga histórica inicial**
   Script que descarga y procesa los históricos comprimidos de PLACSP (por año desde 2012, por mes del año en curso), acotados al vertical, para arrancar con corpus real sin esperar semanas de ingesta diaria. Tests.

9. **1.9 — Celery + Redis**
   App de Celery, tarea de ingesta diaria programada vía Celery beat, logging básico de cada corrida. Tests.

10. **1.10 — Endpoint FastAPI mínimo**
    `GET /tenders` con filtros básicos (CPV, estado, importe, provincia), paginado, probado vía Swagger UI. Tests.

11. **1.11 — Revisión completa de la fase**
    Repaso exhaustivo de todo lo construido en 1.1-1.10 buscando errores que se hayan podido escapar durante el desarrollo incremental. Tests adicionales o ajustados donde haga falta. Métricas reales de cierre (licitaciones cargadas, duración de la ingesta) para el README.

## Cómo se documenta cada subfase

Antes de empezar cada subfase (1.1 a 1.11) hay una conversación de planificación sobre qué se va a hacer y qué se va a tocar. El resultado se registra en `docs/phases/phase1/subphases/phase1.X.md`, creado cuando esa subfase arranca, con el plan acordado y — según avanza el trabajo — qué se hizo, qué se tocó y por qué.
