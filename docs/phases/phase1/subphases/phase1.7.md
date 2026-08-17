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

### Paso 1 — `tenders/repository.py`: `upsert_tender()` (pendiente)

### Paso 2 — Tests de idempotencia (pendiente)

### Paso 3 — Verificación final: Docker, ruff, pytest (pendiente)
