# Subfase 1.4 — Filtro de vertical

## Plan acordado

Del desglose de la Fase 1 (`docs/phases/phase1/phase1.md`): lista de códigos CPV de "servicios informáticos" y utilidad de filtrado reutilizable, usada tanto por la ingesta diaria (1.5+) como por la carga histórica (1.8). Tests.

### Investigación (verificada, no asumida)

CPV (Common Procurement Vocabulary) es la clasificación estándar de la UE para contratación pública. Estructura jerárquica: División (2 dígitos) → Grupo (3) → Clase (4) → Categoría (5) → Subcategoría (8 dígitos), con un dígito de control opcional tras un guión (ej. `72212730-0`).

**División 72 = "Servicios de tecnologías de la información: consultoría, desarrollo de software, Internet y apoyo"**, con subgrupos `72100000` (consultoría de hardware) a `72900000` (backup y conversión de catálogos), pasando por `72200000` (programación y consultoría de software), `72600000` (soporte y consultoría), etc.

Fuentes: [CPV Codes for IT Services — Jorpex](https://jorpex.com/guides/cpv-codes-for-it-services/), [CPV Code 72 - IT Services — Patterno Akademie](https://www.patterno.de/en/resources/akademie/cpv/72-it-dienstleistungen)

### Decisiones tomadas en la conversación de planificación

- **Toda la División 72**, no una lista curada de subgrupos: cualquier código que empiece por `72`. Más simple, más cobertura; si resulta demasiado amplio al ver datos reales (1.8), se acota después con un cambio pequeño — más barato que descubrir que faltaba algo relevante.
- **Solo División 72, sin División 48** (paquetes de software / licencias): el documento de diseño y `phase1.md` dicen literalmente "servicios informáticos" (`contract_type = servicios`). La División 48 es suministro (`contract_type = suministros`), un eje distinto que no se pidió acotar — ampliarlo ahora sería scope creep no solicitado.
- **Matching por prefijo de string** sobre el código normalizado (sin el dígito de control), no comparación numérica de rango — más directo dado que los CPV llegan como strings de longitud fija.

## Progreso

### Paso 1 — `tenders/vertical.py`: constante, normalización y funciones de matching (completado)

- `IT_SERVICES_CPV_DIVISION = "72"` — constante nombrada en vez de un `"72"` mágico repetido por el código.
- `normalize_cpv_code()` — quita el dígito de control opcional (`"72212730-0"` → `"72212730"`) vía `.split("-")[0].strip()`. Funciona igual con o sin dígito de control, sin necesidad de un `if` aparte.
- `is_it_services_cpv()` — normaliza y comprueba `.startswith("72")` para un único código.
- `matches_it_vertical()` — `any(is_it_services_cpv(code) for code in cpv_codes)` sobre la lista completa de CPV de una licitación; `any()` sobre una lista vacía da `False` de forma natural (licitación sin CPV no coincide).
- Verificado con `ruff check`/`format --check` — sin avisos.

### Paso 2 — Tests (completado)

- `tests/test_tender_vertical.py`: 7 tests, uno por cada caso listado en el plan (normalización con/sin dígito de control, código suelto que coincide/no coincide, lista con alguno/ninguno que coincide, lista vacía).
- Estilo: `assert not x` en vez de `assert x is False` para las funciones que devuelven `bool` — más idiomático, y la regla `SIM` de ruff ya activada marcaría la comparación explícita como redundante.
- Cada función testeada por separado (incluida `normalize_cpv_code`, aunque las otras dos la usan por dentro): si algo falla, el nombre del test que falla ya dice qué pieza fue, sin tener que investigar.
- Ejecutados en aislamiento (`pytest tests/test_tender_vertical.py`, no la suite completa) porque Docker no estaba levantado en ese momento y estos tests no lo necesitan — la ejecución de la suite completa junto con los tests que sí requieren Postgres/Redis se deja para el paso 3 (verificación final).

### Paso 3 — Verificación final: ruff + pytest (pendiente)
