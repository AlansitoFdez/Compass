# Subfase 3.7 — Veredicto determinista

## Plan acordado

Del desglose de la Fase 3 (`docs/phases/phase3/phase3.md`): función Python pura que compara la extracción (3.4) contra el perfil del proveedor (Fase 2) y produce `APTO` / `APTO CON RESERVAS` / `NO APTO` con motivo citado. Sin LLM ni sesión de base de datos en el camino -- es la materialización directa de "el LLM extrae, el código decide".

### Lo que `Provider` realmente tiene para contrastar

El documento de diseño (`docs/compass-radar-licitaciones.md`, §5.3) menciona facturación por ejercicio, años de actividad, certificaciones y trabajos previos similares como el perfil ideal contra el que contrastar. El modelo `Provider` real (`providers/models.py`, cerrado en Fase 2) solo persiste `annual_revenue`, `certifications`, `min_budget`/`max_budget` (ya consumidos por el embudo de la Fase 2) y `locations` -- no hay campo de años de actividad ni de importe acumulado de trabajos previos. Esa diferencia, no un ajuste del diseño, es lo que fija qué puede bloquear un veredicto y qué solo puede quedar en reserva.

### Decisiones tomadas en la conversación de planificación

- **Solo dos campos bloquean** (`NO_APTO`), porque son los únicos donde `Provider` tiene el dato real para contrastar:
  - `economic_solvency.minimum_annual_turnover_eur` > `provider.annual_revenue` declarado.
  - Una certificación exigida ausente de `provider.certifications`.
- **Certificación ausente bloquea, no solo reserva** -- decisión explícita de Alan en la conversación de planificación, simétrica con el ejemplo de facturación del propio documento de diseño. Riesgo aceptado: el matching de texto entre cómo el pliego nombra una certificación y cómo la declara el proveedor no es semántico.
- **Dos motivos de reserva** (`APTO_CON_RESERVAS`), nunca bloqueantes, porque no hay con qué contrastarlos de verdad:
  - `technical_solvency.minimum_amount_eur` exigido -- `Provider` no registra importe de trabajos previos, así que esto es siempre "no verificable" cuando el pliego lo exige.
  - `economic_solvency.minimum_annual_turnover_eur` exigido pero `provider.annual_revenue` es `None` -- ambos lados existen (extracción y perfil) pero falta el número necesario para comparar.
- **Criterios de adjudicación, garantías, plazos, subcontratación y lotes no gatean el veredicto.** El perfil no tiene ningún campo con el que contrastarlos -- quedan disponibles en `extraction` para que la ficha los muestre como información, no como parte del cálculo.
- **Agregación**: cualquier motivo bloqueante → `NO_APTO`; si no, cualquier motivo de reserva → `APTO_CON_RESERVAS`; si no hay ninguno → `APTO`.

### Criterios de aceptación

1. Perfil que cumple todo (facturación suficiente, certificación presente aunque con nombre distinto) → `APTO`, sin razones.
2. Pliego sin exigencias de solvencia ni certificaciones → `APTO`, sin razones.
3. Turnover exigido > `annual_revenue` declarado → `NO_APTO`, con cita.
4. Certificación exigida ausente → `NO_APTO`, con cita.
5. Solvencia técnica exigida (importe) sin otros bloqueos → `APTO_CON_RESERVAS`.
6. Turnover exigido con `annual_revenue = None` → `APTO_CON_RESERVAS`.
7. Un motivo bloqueante y uno de reserva a la vez → `NO_APTO`, y ambos aparecen en `reasons` (la reserva no se descarta).
8. Tests, `ruff`, `mypy` limpios.

## Progreso

### Paso 1 — Enum, schemas y la función

`analysis/enums.py`: `Verdict(StrEnum)` (`APTO`/`APTO_CON_RESERVAS`/`NO_APTO`), documentado como nunca puesto por el LLM. `analysis/schemas.py`: `VerdictReason` (`detail` en español + `Citation | None`) y `VerdictResult` (`verdict` + `reasons: list[VerdictReason]`).

`analysis/verdict.py` (nuevo): `compute_verdict(extraction, provider) -> VerdictResult`. Sin imports de red, BD ni LangGraph -- solo `PliegoExtraction`, `Provider` y los tipos propios.

### Paso 2 — Matching de certificaciones: por qué substring no bastaba

La primera versión comparaba certificaciones por subcadena en ambos sentidos sobre texto normalizado (minúsculas, sin acentos). El primer test que ejercitaba el caso real del documento de diseño -- pliego pidiendo `"ISO 27001"`, perfil declarando `"ISO/IEC 27001:2013"` -- falló: ninguna de las dos cadenas es subcadena de la otra una vez que `"IEC"` se interpone entre `"ISO"` y `"27001"`.

Se cambió a comparación por **conjunto de tokens alfanuméricos** (`re.findall(r"[a-z0-9]+", ...)` sobre texto normalizado): `"ISO 27001"` → `{"iso", "27001"}`, `"ISO/IEC 27001:2013"` → `{"iso", "iec", "27001", "2013"}`. Como `{"iso", "27001"}` es subconjunto del segundo, ahora sí coincide -- comprobado en ambos sentidos (el lado más corto, cualquiera que sea, tiene que estar cubierto por el más largo). Sigue siendo deliberadamente permisivo: bloquear por una certificación ausente es una decisión con coste real para el proveedor (ver más arriba), así que un falso negativo del matching (bloquear a alguien que sí tiene la certificación, solo que mal escrita) es el error que más se quería evitar.

### Paso 3 — Formato de cifras: el segundo fallo real de los tests

El primer test contra el ejemplo exacto del documento de diseño (`"exigen cifra de negocio de 300.000 € [...] tu perfil declara 180.000 €"`) también falló: `f"{300000:,.2f}"` da `"300,000.00"` -- formato inglés, coma de millar y punto decimal -- no el formato español del propio ejemplo. Se añadió `_format_eur`, que agrupa con punto (`f"{amount:,.0f}".replace(",", ".")`) porque este texto es copy de producto en español, no una cifra de log.

### Paso 4 — Tests

`tests/analysis/test_verdict.py`, 8 casos, sin sesión de BD ni fixture de PDF -- lógica pura sobre `PliegoExtraction`/`Provider` construidos a mano, mismo patrón que `test_verification.py`. Cubre los 8 criterios de aceptación uno a uno, incluyendo el caso de agregación (bloqueo + reserva simultáneos → `NO_APTO` sin perder la reserva) y el de tolerancia de nombres de certificación que motivó el Paso 2.

Suite completa: **170 passed** (162 previos + 8 nuevos). `ruff check`/`format --check`/`mypy` (proyecto completo, sin argumentos) sin avisos.

Subfase 3.7 completada. Los ocho criterios de aceptación se cumplen.
