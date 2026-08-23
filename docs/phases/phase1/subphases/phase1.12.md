# Subfase 1.12 — Documentación en el código

## Plan acordado

Durante la Fase 1 el foco estuvo en que la ingesta funcionara, y la documentación en línea se fue quedando atrás: hay módulos enteros sin docstring de módulo, funciones públicas sin documentar y comentarios escritos en español, contra la convención del proyecto. `CLAUDE.md` exige docstrings en convención Google sin exenciones y todo el código en inglés; el código de la Fase 1 no cumple ninguna de las dos cosas del todo.

Esta subfase salda esa deuda. No es una subfase de comportamiento: al terminar, el programa hace exactamente lo mismo que antes. Lo que cambia es que se puede leer.

### El estado de partida, medido

Auditoría automática de los 48 archivos `.py` de `src/`, `tests/` y `alembic/` (recorrido con `ast` para los docstrings y `tokenize` para los comentarios; el español se detecta por caracteres acentuados o por densidad de palabras funcionales):

| Hallazgo | Cantidad |
|---|---|
| Docstrings ausentes | **139** en 37 archivos |
| Docstrings en español | 5 |
| Líneas de comentario en español | 57 |

Los peores archivos por docstrings ausentes: `test_historical_loader.py` (13), `test_tender_repository.py` (11), `test_daily_ingestion_task.py` (10), `checkpoint.py` y `codice_parser.py` (7 cada uno). Sin docstring de módulo: `alembic/env.py`, `main.py`, `conftest.py`, `test_health.py`.

Los comentarios en español se concentran donde está el razonamiento más denso — `repository.py` (12 líneas), `tasks.py` (11), `feed_reader.py` (6): justo los que explican decisiones y no mecánica, que son los que más caro sale perder.

### Cómo se trabaja

Recorrido **en orden de flujo de datos, no alfabético**: cada módulo se documenta sabiendo ya qué hacen los que tiene por debajo, que es lo que permite que su docstring explique su papel en el sistema y no solo su mecánica.

1. `core/` — config, motor de BD, Redis, Celery.
2. `tenders/` — el dominio: `enums` → `models` → `schemas` → `vertical` → `repository`.
3. `ingestion/` — `atom_client` → `feed_reader` → `checkpoint` → `codice_codes` → `codice_parser` → `daily_ingestion` → `tasks` → `historical_loader`.
4. `api/` + `main.py`.
5. `alembic/`.
6. `tests/` — cada test junto al módulo que protege.

Un paquete por paso, con commit y entrada de log por paso.

Dos decisiones tomadas al planificar:

- **Los docstrings los escribe Claude**, excepción explícita a la regla de `CLAUDE.md` de que el código lo escribe Alan: aquí no hay lógica que decidir, es documentar lo que el código ya hace. Alan los revisa uno a uno antes de cerrar cada paso.
- **Los helpers anidados dentro de los tests llevan docstring** (los `handler` de los transportes mock, `fake_run_daily_ingestion`, `_on_commit`): ~15 de los 139. Se cumple "sin exenciones" literalmente, en vez de abrir un agujero en la regla.

### Criterios de aceptación

1. Una auditoría de `src/`, `tests/` y `alembic/` —recorriendo los módulos con `ast` para los docstrings y con `tokenize` para los comentarios— no encuentra **ningún docstring ausente, ninguno en español y ningún comentario en español**. Se ejecuta al cerrar cada paso y al final de la subfase; no se versiona ningún script para ello.
2. `uv run pytest` sigue en **73 passed**: ningún cambio de comportamiento.
3. `uv run ruff check .`, `uv run ruff format --check .` y `uv run mypy` salen limpios.
4. Ningún docstring se limita a reformular el nombre de la función. En los tests, cada uno dice **qué comportamiento protege**.

## Progreso
