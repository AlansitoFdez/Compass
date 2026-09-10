# Subfase 4.2 — Coste real en el README

## Plan acordado

Del desglose de la Fase 4 (`docs/phases/phase4/phase4.md`): consulta a Langfuse (API o dashboard) para agregar coste/tokens reales de las trazas acumuladas; la métrica "coste medio de analizar un pliego: 0,0X €" del documento de diseño, con datos reales detrás, no una única corrida.

### Criterios de aceptación

1. Un script repetible (mismo patrón que `extraction_eval.py`) consulta Langfuse y agrega coste/tokens/latencia reales sobre los análisis trazados hasta ahora.
2. El README refleja esos números reales, no una medición manual puntual.
3. `uv run pytest`, `ruff check --fix`, `ruff format`, `mypy` limpios.

## Progreso

### Paso 1 — Contratiempo real, sin relación con el código: trazas borradas por accidente

Antes de poder agregar nada, Alan borró sin querer las trazas de la 4.1 desde el propio dashboard de Langfuse. Sin consecuencia real (son datos de observabilidad, no producción): se sustituyeron dos veces disparando análisis reales nuevos contra tenders nunca antes analizados (`040-2026-0075`, `1583900M`), servidor `uvicorn --reload` y worker Celery reales.

### Paso 2 — La API correcta no es la que usé en la 4.1

Al investigar por qué `client.api.trace.get`/`client.api.trace.list` (usadas para verificar la 4.1) devolvían vacío después del borrado, el propio dashboard de Langfuse marcó ambos métodos como **deprecados** en su panel de "Migrate APIs", con la migración recomendada hacia `client.api.observations.get_many` -- justo el método que en la 4.1 parecía devolver una vista más pobre. Investigando el código fuente instalado (`langfuse/api/observations/client.py`), la razón salió a la luz: `get_many` acepta un parámetro `fields` con grupos explícitos (`core`, `basic`, `usage`, `model`, `metrics`...) y **si no se especifica, solo devuelve `core`+`basic`** -- ninguno de los dos incluye `usageDetails`/`costDetails`/`totalCost`. La 4.1 lo llamó sin `fields`, así que los campos de coste nunca estaban ausentes en el servidor: nunca se pidieron.

Con `fields="core,basic,usage,model,metrics"`, la misma llamada devuelve el modelo real, los tokens reales (`usageDetails: {"input": ..., "output": ..., "total": ...}`) y el coste real (`costDetails: {"total": ...}`) -- confirmado contra los dos análisis reales de este mismo paso.

### Paso 3 — `analysis/cost_report.py`

Script nuevo, mismo espíritu que `extraction_eval.py` (herramienta repetible, no parte del pipeline de análisis): `collect_cost_summaries()` consulta las generaciones `extract` (tokens, coste) y los *spans* raíz `analyze_pliego` (latencia end-to-end), y los combina en `AnalysisCostSummary` por traza. `_build_summary` (la única lógica con algo que probar) es una función pura sobre los campos ya extraídos -- no sobre los objetos pydantic del SDK directamente, para no necesitar un doble falso de su esquema exacto en los tests. `average()` calcula la media real, vacía (no división por cero) si todavía no hay ningún análisis trazado.

Tests: mapeo correcto de `usage_details`/`cost_details` reales, ceros (no una excepción) cuando faltan datos, media real sobre dos resúmenes conocidos, y el caso vacío.

### Paso 4 — Números reales, con dos análisis reales delante

`uv run python -m compass.analysis.cost_report` contra los dos análisis reales del Paso 1:

| Análisis | Tokens (entrada / salida) | Coste | Tiempo real |
|---|---|---|---|
| 1º | 41.724 (32.985 / 8.739) | 0,00 € | 194 s |
| 2º | 106.527 (93.834 / 12.693) | 0,00 € | 285 s |
| Media | 74.126 | 0,00 € | 240 s |

**Hallazgo real, no anticipado**: el volumen de tokens de entrada varía muchísimo entre pliegos (33.000 a 94.000) -- más del doble -- porque el prompt manda el PCAP completo, página a página, sin trocear. Un pliego largo o con formato denso paga varias veces más tokens de entrada que otro con menos páginas o más compacto, algo que no era visible en la 3.9 (que solo medía tiempo y coste, no tokens).

README actualizado: nueva sección "Fase 4 -- Coste real, medido con Langfuse" con esta tabla, y el estado del proyecto (cabecera) refleja que la Fase 4 está en curso, no sin empezar.

## Verificación final

- `uv run pytest`: **193 passed** (189 previos + 4 nuevos de `test_cost_report.py`).
- `uv run ruff check .` / `ruff format --check .`: sin avisos.
- `uv run mypy` (proyecto completo): sin avisos.
- Números del README verificados contra la salida real de `cost_report.py`, no copiados de memoria.

Subfase 4.2 completada. Los tres criterios de aceptación se cumplen.
