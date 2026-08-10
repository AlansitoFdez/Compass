# Subfase 1.2 — Infraestructura local

## Plan acordado

Del desglose de la Fase 1 (`docs/phases/phase1/phase1.md`): `docker-compose.yml` con PostgreSQL+pgvector y Redis, configuración de conexión, verificación de que todo levanta y conecta.

Decisiones tomadas en la conversación de planificación:

- **Imagen Postgres+pgvector**: `pgvector/pgvector:0.8.6-pg17`. Razón: mismo criterio que la versión de Python — un ciclo completo de madurez del ecosistema frente a `pg18` (muy reciente), y además es la versión por defecto del propio Dockerfile de pgvector. Verificado por búsqueda (no era territorio conocido): [pgvector/pgvector - Docker Image](https://hub.docker.com/r/pgvector/pgvector).
- **Imagen Redis**: `redis:8-alpine`. Verificado: [redis - Official Image](https://hub.docker.com/_/redis).
- **`docker-compose.yml` en la raíz del repo**, no en `backend/`: es infraestructura compartida — cuando llegue el frontend Next.js (Fase 5) seguirá viviendo ahí.
- **Healthchecks** en ambos servicios (`pg_isready`, `redis-cli ping`) para que `docker compose up` no dé por arriba un contenedor que aún no acepta conexiones.
- **Credenciales de desarrollo hardcodeadas en `docker-compose.yml`** (ej. `compass`/`compass`): no son secretos reales, son de un contenedor local desechable — un `.env` aparte solo añadiría indirección sin beneficio de seguridad. `backend/.env.example` solo necesita la `DATABASE_URL`/`REDIS_URL` resultante.
- **Sin SQLAlchemy todavía**: 1.2 añade drivers crudos (`psycopg[binary]` para Postgres, `redis` para Redis) con una comprobación mínima de conectividad. SQLAlchemy, el engine y los modelos llegan en 1.3, que es donde de verdad se van a usar.
- **Verificación vía test de pytest real** (no un script suelto), siguiendo el patrón "tests sobre la marcha" del proyecto: un test de integración que abre conexión real a Postgres y Redis. Requiere que `docker compose` esté arriba al correr pytest — asumible en desarrollo local, sin CI todavía (Fase 6).

## Progreso

### Paso 1 — Verificar Docker disponible (pendiente)

### Paso 2 — `docker-compose.yml` (pendiente)

### Paso 3 — `DATABASE_URL`/`REDIS_URL` en `.env.example` y `core/config.py` (pendiente)

### Paso 4 — Dependencias: `psycopg[binary]`, `redis` (pendiente)

### Paso 5 — Test de conectividad real (pendiente)

### Paso 6 — Verificación final: levantar Docker, correr tests, parar Docker (pendiente)
