# Subfase 1.5 — Cliente ATOM

## Plan acordado

Del desglose de la Fase 1 (`docs/phases/phase1/phase1.md`): fetch del feed PLACSP, paginación por cursor siguiendo `next`, persistencia del último punto procesado para reanudar tras un fallo. Tests.

### Investigación (verificada con una petición real, no asumida)

- **URL real del feed**: `https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom`. Confirmado con una petición real: ATOM válido (namespace `http://www.w3.org/2005/Atom`), datos reales de hoy (expediente S-02027-2026, RTVE, 717.120 €).
- Paginación: `<link rel="next" href="..."/>`, hasta 500 entradas por página. El `href` del `next` puede cambiar de dominio entre páginas (visto: de `contrataciondelsectorpublico.gob.es` a `contrataciondelestado.es`) — el cliente debe seguir la URL literal, nunca asumir un dominio fijo.
- Archivos históricos comprimidos (para la 1.8, no esta subfase): `.../sindicacion_643/licitacionesPerfilesContratanteCompleto3_AAAAMM.zip`.
- Fuente: [Portal de Datos Abiertos — Ministerio de Hacienda](https://www.hacienda.gob.es/es-ES/GobiernoAbierto/Datos%20Abiertos/Paginas/LicitacionesContratante.aspx)

### Decisiones tomadas en la conversación de planificación

- **Checkpoint del cursor en Redis**, no en una tabla Postgres nueva: ya es infraestructura existente, encaja como uso clásico de Redis (estado operativo pequeño y mutable), y no reabre la capa de modelo de datos (1.3) para algo que no es un dato de negocio. Si Redis perdiera el checkpoint, el peor caso es reprocesar una página ya vista — seguro gracias al upsert idempotente que se construirá en 1.7.
- **El checkpoint se actualiza después de procesar cada página con éxito, nunca antes**: así, ante un fallo a mitad de proceso, en el peor caso se reprocesa una página ya vista (inofensivo), pero nunca se salta una sin procesar.
- **`httpx2` pasa a dependencia de producción** (ya estaba en dev desde la 1.1 para `TestClient`): ahora lo usa la app de verdad en tiempo de ejecución.
- **Nuevo paquete `compass/ingestion/`**, distinto de `compass/tenders/`: esta subfase trata de "cómo traer los datos", no de la entidad `Tender` en sí. Mismo criterio de paquete-por-dominio que ya se aplicó separando `api/`/`core/` (1.1) y creando `tenders/` (1.3).
- **Parseo de la estructura ATOM con `xml.etree.ElementTree`** (librería estándar, sin dependencia nueva) — solo extrae `<entry>` (como XML crudo, sin parsear su contenido CODICE) y el `next`. El contenido de cada `<entry>` se parsea en la 1.6, no aquí.
- **Tests con HTTP mockeado** (fixture XML local), nunca contra el servidor real de PLACSP en la suite automática.

## Progreso

### Paso 1 — `httpx2` a dependencia de producción (completado)

- `uv remove --dev httpx2` + `uv add httpx2` → pasa de `[dependency-groups] dev` a `[project.dependencies]`. Necesario porque `uv sync --no-dev` (instalación de producción) se saltaría las dependencias de dev, y el cliente ATOM lo va a usar en tiempo de ejecución real.
- Verificado: `ruff check`/`format --check` sin avisos, `test_health.py` (que usa `TestClient`, apoyado en `httpx2` por debajo) sigue en verde.

### Paso 2 — `core/redis_client.py`: cliente Redis compartido (completado)

- **Decisión explicitada en esta conversación** (antes implícita): toda la tubería de ingesta (1.5-1.9) usa clientes **síncronos**, no async — corre dentro de tareas de Celery (procesos worker independientes, paralelismo por múltiples procesos), no dentro del event loop de FastAPI. A diferencia de `psycopg`/SQLAlchemy (donde la misma URL sirve para modo síncrono o async según qué función se llame), `redis-py` expone dos clases completamente separadas (`redis.Redis` vs `redis.asyncio.Redis`) — se elige una explícitamente, sin detección automática.
- `get_redis_client()` — mismo patrón `@lru_cache` que `get_settings()`: se construye una vez, se reutiliza la misma instancia después.
- `decode_responses=True` — Redis es "binary-safe" y por defecto `redis-py` devuelve `bytes`; como solo vamos a guardar texto plano (la URL del checkpoint), esto evita tener que decodificar a mano en cada lectura.
- Verificado: el cliente se construye sin conectar de verdad (`redis.Redis.from_url()` es perezoso), con los parámetros correctos leídos de `.env` (`host=localhost`, `port=6379`, `db=0`).

### Paso 3 — `ingestion/atom_client.py`: fetch de una página + parseo de `entry`/`next` (pendiente)

### Paso 4 — Checkpoint: leer/escribir el último punto procesado en Redis (pendiente)

### Paso 5 — Iterador principal: sigue `next` hasta agotar el feed, actualizando el checkpoint tras cada página (pendiente)

### Paso 6 — Tests con HTTP mockeado (pendiente)

### Paso 7 — Verificación final: Docker (Redis), ruff, pytest (pendiente)
