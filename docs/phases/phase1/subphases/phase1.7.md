# Subfase 1.7 — Persistencia idempotente

## Plan acordado

Del desglose de la Fase 1 (`docs/phases/phase1/phase1.md`): upsert por expediente, retiradas como cambio de estado (nunca borrado físico), tests de idempotencia (mismo expediente procesado dos veces = una fila, actualizada).

### Investigación: cómo marca PLACSP las retiradas

Existen **dos mecanismos distintos** en el feed real, no uno:

1. **Cambio de estado vía `ANUL`** (ya mapeado a `TenderStatus.CANCELLED` en la 1.6): una licitación anulada se republica como una `<entry>` normal, con todos sus datos intactos, solo que con `ContractFolderStatusCode = ANUL`. El upsert que se construye en esta subfase ya lo maneja correctamente sin nada especial.
2. **`<at:deleted-entry ref="...">`** (extensión estándar de ATOM, RFC 6721): usado cuando una licitación deja de ser públicamente accesible del todo (ej. archivada tras resolverse hace tiempo). Es un elemento XML **distinto** de `<entry>` — `atom_client.py` (1.5) no lo extrae actualmente. El `ref` apunta al `<id>` de ATOM, no directamente al expediente.

### Decisión tomada en la conversación de planificación

- **`<at:deleted-entry>` queda fuera de alcance de esta subfase**, documentado explícitamente como hueco conocido, no como olvido. Razón: manejarlo exigiría guardar una relación id-ATOM↔expediente que no existe todavía, para un caso (licitaciones archivadas, ya no públicamente visibles) menos relevante para un proveedor buscando a qué presentarse — y no se ha visto un ejemplo real en el feed en vivo para verificar la estructura exacta antes de construir sobre ella. 1.7 se centra en el upsert normal, que ya cubre "retirada = cambio de estado" vía `ANUL`.

### Diseño del upsert

- **`INSERT ... ON CONFLICT (expediente) DO UPDATE`** nativo de Postgres (vía `sqlalchemy.dialects.postgresql.insert().on_conflict_do_update()`), no un "comprobar si existe, luego decidir" manual — una sola sentencia atómica, sin ida y vuelta extra ni condición de carrera entre el check y el write.
- En la actualización se sobrescriben **todos** los campos de negocio (incluido poner a `NULL` un campo que estaba antes y ya no viene — ej. un `submission_deadline` que desaparece en una modificación), **excepto**:
  - `expediente` — es la clave de conflicto, no cambia.
  - `created_at` — se conserva el valor original de la primera inserción, nunca se toca en la actualización.
  - `updated_at` — se fuerza explícitamente a `func.now()` en el propio `SET` de la actualización (no se asume que el `onupdate=` del modelo se dispare solo dentro de una sentencia `ON CONFLICT DO UPDATE`; verificar esto empíricamente antes de darlo por hecho).
- Nuevo módulo `tenders/repository.py` (`upsert_tender(session, tender: TenderSchema) -> None`), separado de `models.py` (definición ORM) y `schemas.py` (validación) — mismo criterio de responsabilidad única de siempre.
- El filtro de vertical (1.4) **no** se aplica dentro de `upsert_tender()` — es una función genérica de persistencia, agnóstica de si la licitación es del vertical o no. La decisión de "esto no se persiste" se toma en la capa que orquesta el pipeline completo (1.9), no aquí.

## Progreso

### Paso 1 — `tenders/repository.py`: `upsert_tender()` (completado)

- `upsert_tender(session, tender)` — `postgresql.insert().on_conflict_do_update(index_elements=[Tender.expediente], set_=...)`. El `SET` se construye con `stmt.excluded.<campo>` (la fila que se habría insertado) para cada campo salvo `expediente`, sobrescritura completa — incluye poner a `NULL` un campo que ya no viene. `updated_at` forzado explícitamente a `func.now()` en el propio `SET`, sin depender de si el `onupdate=` del modelo se dispara solo dentro de un `ON CONFLICT`. `created_at` nunca se toca porque `TenderSchema` no lo incluye (es de la capa de persistencia, no del CODICE), así que nunca aparece en el `SET`.
- **Hallazgo real, verificado manualmente antes de los tests formales**: al insertar y luego "actualizar" el mismo expediente dentro de la misma sesión, una relectura mostraba datos **obsoletos** (el `title` viejo, `updated_at` sin cambiar) — no porque el upsert fallara, sino porque el **mapa de identidad** de SQLAlchemy tenía el objeto en caché y no sabía que una sentencia Core cruda (no un `session.add()`/ORM normal) había cambiado la fila por debajo. `session.expire_all()` lo confirma y arregla (fuerza a releer de la base de datos). Decisión: no meter `expire_all()` dentro de `upsert_tender()` (invalidaría toda la sesión, efecto colateral raro para una función llamada en bucle); se resuelve en el punto que necesita releer lo que acaba de escribir — los tests de idempotencia (paso 2).
- Verificado manualmente contra Postgres real: una sola fila tras dos upserts del mismo expediente, `created_at` estable, `updated_at` cambia, datos reflejan la versión más reciente (una vez resuelto el problema de caché de sesión).

### Paso 2 — Tests de idempotencia (completado)

- `tests/test_tender_repository.py` (3 tests, Postgres real): fila nueva tras el primer upsert, una sola fila tras procesar el mismo expediente dos veces con los mismos datos, y actualización de campos (incluida puesta a `NULL`) preservando `created_at` y cambiando `updated_at` tras una segunda pasada con datos distintos.
- **Bug real #1 — `now()` vs `clock_timestamp()`**: el test de actualización fallaba porque `second.updated_at` y `first.updated_at` salían idénticos. Verificado contra Postgres real (`psql` con `pg_sleep`) que `now()`/`CURRENT_TIMESTAMP` devuelve la hora de **inicio de la transacción**, constante durante toda ella — no la hora real de cada sentencia. `repository.py` corregido: `func.clock_timestamp()` en vez de `func.now()` para `updated_at` (semánticamente más correcto además: "cuándo se tocó esta fila de verdad", no "en qué transacción").
- **Bug real #2 — mapa de identidad de SQLAlchemy, un clásico**: tras el fix anterior, el test seguía fallando. Diagnosticado con un script aparte con una espera real (`asyncio.sleep(0.3)`) entre los dos upserts: los timestamps sí eran distintos en la base de datos, pero la comparación en Python seguía dando igual. Causa: la sesión reutiliza **el mismo objeto Python** para la misma fila (mismo `expediente`) en vez de crear uno nuevo en cada consulta — al releer la fila por segunda vez, muta el objeto ya existente por dentro, así que cualquier variable que apuntara a ese objeto "de antes" (`first`) en realidad ve los datos "de después" (porque `first` y `second` acaban siendo el mismo objeto). Arreglado capturando `first.created_at`/`first.updated_at` como variables sueltas (valores, no referencias al objeto) inmediatamente después de la primera lectura, antes de que la segunda consulta mutara el objeto.
- Suite completa: **33 tests pasan**.

### Paso 3 — Verificación final: Docker, ruff, pytest (pendiente)
