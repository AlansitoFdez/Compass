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

### Paso 1 — `tenders/vertical.py`: constante, normalización y funciones de matching (pendiente)

### Paso 2 — Tests (pendiente)

### Paso 3 — Verificación final: ruff + pytest (pendiente)
