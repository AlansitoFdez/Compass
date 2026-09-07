# Subfase 2.3 — Recuperador léxico

## Plan acordado

Del desglose de la Fase 2 (`docs/phases/phase2/phase2.md`): la mitad léxica de la recuperación híbrida (Etapa 2) -- `tsvector` de Postgres sobre el objeto del contrato (`Tender.title`), rankeando por relevancia frente a la descripción libre del proveedor, en vez de filtrar como la Etapa 1.

### Investigación previa a escribir código

Antes de decidir cómo construir la consulta, se comprobó contra Postgres real cómo se comporta `tsvector`/`tsquery` con la descripción real ya sembrada del proveedor (2.1):

- `plainto_tsquery('spanish', description)` sobre el párrafo completo (~23 lexemas) produce una consulta que los exige **todos** (AND) -- verificado que da **0 coincidencias** contra los títulos reales del corpus. Una descripción de proveedor es un párrafo, no una frase de búsqueda corta; `plainto_tsquery` está pensado para lo segundo.
- La alternativa -- construir una consulta que exige **cualquiera** de los lexemas (OR), vía `to_tsquery(array_to_string(tsvector_to_array(to_tsvector(...)), ' | '))` -- da **1.526 coincidencias** sobre el corpus completo. Ninguno de los dos extremos es un filtro válido por sí solo: por eso esta etapa no filtra, **rankea** dentro de lo que ya sobrevivió a la Etapa 1 (2.2).
- **Verificado con datos reales, no solo con la teoría**: rankeando los 61 supervivientes reales de la Etapa 1 (perfil sembrado) por `ts_rank` con la consulta OR, el resultado #1 es *"Contrato de servicios de mantenimiento (...) para portales Drupal de la Universidad de Jaén"* -- coincide casi literalmente con la especialidad declarada del proveedor ("mantenemos portales institucionales (...) con Drupal").

### Criterios de aceptación

1. `uv run alembic upgrade head` aplica la migración de `title_tsv` sin drift.
2. `uv run pytest` cubre que un título relevante rankea por encima de uno no relacionado, que un título lexicalmente perfecto pero que no sobrevive la Etapa 1 no aparece, y que `limit` acota de verdad los resultados -- y sigue en verde junto con los tests existentes.
3. `uv run mypy` y `uv run ruff check`/`format --check` limpios.
4. Ejecutado de extremo a extremo contra Postgres real con el perfil de proveedor ya sembrado.

## Progreso

### Paso 1 — Columna generada `title_tsv` + índice GIN

- `tenders/models.py`: `title_tsv: Mapped[str]`, tipo `TSVECTOR`, `Computed("to_tsvector('spanish', title)", persisted=True)` -- generada y mantenida por Postgres en cada insert/update de `title`, nunca escrita desde Python, así que no hay riesgo de que quede desincronizada del texto del que se deriva. Índice GIN (`ix_tenders_title_tsv_gin`) para que `@@`/`ts_rank` no hagan `Seq Scan`.
- Migración `198bdf87e9a5_add_generated_tsvector_column_on_tender_.py`, generada y aplicada contra Postgres real.

### Paso 2 — `matching/lexical.py`

- `build_filters()` (2.2) deja de ser privado (`_build_filters` → `build_filters`): esta subfase lo reutiliza directamente para que el ranking léxico solo mire los mismos supervivientes que ya pasó la Etapa 1 -- el embudo es secuencial, ninguna etapa posterior mira un conjunto más amplio que el que ya recortó la anterior.
- `_or_tsquery(text)` -- construye la consulta OR descrita arriba: `to_tsvector` ya quita palabras vacías, ambigüedades de mayúsculas y aplica stemming, así que los lexemas resultantes son seguros de unir con `|` (ningún carácter especial de `tsquery` sobrevive a esa normalización).
- `lexical_matches(session, provider, limit)` -- combina los filtros duros de `build_filters` con `title_tsv @@ query` (solo lo que comparte al menos un lexema) y ordena por `ts_rank(title_tsv, query)` descendente.
- Verificado con `mypy`: `func.to_tsquery(...)` no está tipado con precisión aguas arriba y devuelve `Any` -- misma corrección que `_cpv_filter`'s `.overlap()` en la 2.2 (anotación explícita de la variable en el punto de construcción, no un `cast`).
- 3 tests en `tests/matching/test_lexical.py`: un título relevante rankea por encima de uno no relacionado; un título lexicalmente perfecto pero con estado distinto de "en plazo" no aparece (protege el orden secuencial del embudo); `limit` acota de verdad.
- Suite completa: **91 passed** (88 previos + 3 nuevos). `mypy` limpio en 57 archivos. `ruff check`/`format --check` limpios. `alembic check` sin drift.

### Paso 3 — Verificación de extremo a extremo

Ejecutado contra Postgres real, con el perfil de proveedor sembrado en la 2.1: `lexical_matches` devuelve el mismo primer resultado que la consulta psql de la investigación previa (rank `0.008685`, expediente `2026/15`, mantenimiento de portales Drupal) -- confirma que la función en producción se comporta igual que la consulta verificada a mano.

Subfase 2.3 completada. Los cuatro criterios de aceptación se cumplen.
