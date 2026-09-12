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

### Paso 1 — Verificar Docker disponible (completado)

- `docker --version` → Docker 28.5.1. `docker compose version` → v2.40.0-desktop.1 (plugin integrado, no el binario standalone `docker-compose`).
- Docker Desktop no estaba arrancado en el primer intento (`docker info` falló al conectar con `dockerDesktopLinuxEngine`); una vez arrancado por el usuario, `docker info` responde correctamente.

### Paso 2 — `docker-compose.yml` (completado)

- `docker-compose.yml` en la raíz con dos servicios: `db` (`pgvector/pgvector:0.8.6-pg17`, credenciales `compass`/`compass`/`compass`, puerto `5432`, volumen nombrado `compass_db_data`) y `redis` (`redis:8-alpine`, puerto `6379`, sin volumen).
- Healthchecks: `pg_isready -U compass` en `db`, `redis-cli ping` en `redis`.
- Validado con `docker compose config` (sin levantar contenedores) — sintaxis correcta, nombres de red/volumen resueltos con el prefijo `compass_` del proyecto.

### Paso 3 — `DATABASE_URL`/`REDIS_URL` en `.env.example` y `core/config.py` (completado)

- `backend/.env.example`: añadidas `DATABASE_URL=postgresql://compass:compass@localhost:5432/compass` y `REDIS_URL=redis://localhost:6379/0`, apuntando a los servicios de `docker-compose.yml`.
- `core/config.py`: `database_url: str` y `redis_url: str` en `Settings`, **sin valor por defecto** — a diferencia de `app_env`/`log_level`, si faltan la app no arranca (fail fast).
- **Efecto observado**: al no tener el usuario todavía un `backend/.env` real con estos dos campos, `uv run pytest` empezó a fallar incluso en `test_health.py` (que no toca la base de datos), porque `Settings` se valida como bloque único al crear la app. Comportamiento esperado y correcto — confirma que el fail-fast funciona.
- El `backend/.env` local se creó a mano, fuera del control de versiones, con los mismos valores no sensibles de `.env.example`. Verificado: `uv run pytest -v` vuelve a pasar.

### Paso 4 — Dependencias: `psycopg[binary]`, `redis` (completado)

- `uv add "psycopg[binary]" redis` → psycopg 3.3.4 (con el extra binario, sin necesidad de cabeceras de desarrollo de Postgres en la máquina), redis-py 8.1.0. Dependencias de producción, no de dev.

### Paso 5 — Test de conectividad real (completado)

- `tests/test_infra_connectivity.py`: `test_postgres_is_reachable` (`psycopg.connect` + `SELECT 1`) y `test_redis_is_reachable` (`redis.from_url` + `.ping()`). No pasa por la app FastAPI, conecta directo a los servicios de `docker-compose.yml`.
- `ruff check`/`format --check` en verde (una línea de docstring superaba `line-length = 100`, acortada).
- Ejecución real contra los contenedores levantados: pendiente para el paso 6 (verificación final).

### Paso 6 — Verificación final: levantar Docker, correr tests, parar Docker (completado)

- `docker compose up -d --wait`: ambos servicios `(healthy)`.
- `uv run ruff check .` / `ruff format --check .` → sin avisos.
- **Bug real encontrado**: `test_postgres_is_reachable` falló con `password authentication failed for user "compass"`, a pesar de que el log del contenedor mostraba una inicialización nueva (`PostgreSQL init process complete`) con las credenciales correctas. Diagnóstico:
  1. Descartado volumen reciclado de otro proyecto (`docker volume ls` solo mostraba `compass_compass_db_data`, recién creado).
  2. Descartado problema de parseo de `.env`: el mismo fallo se reproducía con un DSN literal hardcodeado (`uv run python -c "psycopg.connect('postgresql://compass:compass@localhost:5432/compass')..."`), sin pasar por `Settings`.
  3. El propio log del contenedor (`docker compose logs db`) no mostraba ningún intento de autenticación fallido — señal de que la conexión ni siquiera llegaba a nuestro Postgres.
  4. `netstat -ano | findstr :5432` reveló **dos procesos** escuchando en el puerto 5432 del host: `com.docker.backend.exe` (el proxy de Docker Desktop) y **`postgres.exe`** (un PostgreSQL nativo de Windows corriendo como servicio, ajeno a este proyecto). Las conexiones a `localhost:5432` estaban cayendo en el Postgres nativo, que no tiene el rol `compass`.
  - **Fix**: cambiado el puerto publicado del contenedor de `5432:5432` a `5433:5432` en `docker-compose.yml` (el puerto interno del contenedor sigue siendo 5432, solo cambia el mapeo al host). Actualizado `DATABASE_URL` en `.env.example` a puerto `5433`, con un comentario explicando por qué no es el puerto por defecto. El usuario actualizó su `.env` real igual. Decisión tomada con el usuario: cambiar el puerto de nuestro lado en vez de tocar el servicio nativo de Windows (que podría estar en uso por otra cosa) — la opción no invasiva.
- Tras el fix: `docker compose up -d --wait` recreó `db` con el nuevo puerto, `uv run pytest -v` → **3 passed** (health check + conectividad real a Postgres y Redis).
- `docker compose down`: contenedores parados y eliminados, volumen `compass_compass_db_data` persiste (sin `-v`).

Subfase 1.2 completada.
