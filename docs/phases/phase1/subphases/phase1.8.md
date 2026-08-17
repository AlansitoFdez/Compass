# Subfase 1.8 — Carga histórica inicial

## Plan acordado

Del desglose de la Fase 1 (`docs/phases/phase1/phase1.md`): script que descarga y procesa los históricos comprimidos de PLACSP acotados al vertical, para arrancar con corpus real sin esperar semanas de ingesta diaria. Tests.

### Investigación (descargando un ZIP real, no asumida)

- **URLs verificadas**: mensual `.../sindicacion_643/licitacionesPerfilesContratanteCompleto3_AAAAMM.zip` (ya la teníamos de la 1.5); anual `..._AAAA.zip` (verificado con 2025 y 2012, ambos existen — pero **el año en curso no tiene bundle anual todavía**, solo mensuales, porque sigue en marcha).
- **Estructura interna**: cada ZIP mensual contiene ~120 ficheros `.atom` sueltos (varios por día), **mismo formato exacto** que el feed en vivo. Verificado descargando julio de 2026 de verdad (191 MB comprimidos) y parseando un fichero interno con `parse_atom_page()` (1.5) sin ningún cambio — 497 entradas extraídas correctamente a la primera.
- **Volumen real**: ~191 MB comprimidos por mes, del orden de ~60.000 licitaciones en bruto (todo el territorio, todos los CPV — el filtro de vertical se aplica después de parsear cada una, no antes de descargar).

### Decisión tomada en la conversación de planificación

- **Cargar los últimos 3 meses** (mes en curso + 2 anteriores), vía ZIPs mensuales — no desde 2012. Razón: cargar 13+ años sería muchos GB y horas de proceso, y además de bajo valor real (una licitación de hace años ya está cerrada; lo que le importa a un proveedor es corpus reciente). El objetivo declarado del propio documento de diseño ("arrancar con corpus sin esperar semanas") apunta a "reciente y suficiente para una buena demo", no a exhaustividad histórica.

### Diseño

- **Reutilización máxima de lo ya construido**: `parse_atom_page()` (1.5) para leer cada `.atom` dentro del ZIP, `parse_codice_entry()` (1.6) para cada `<entry>`, `matches_it_vertical()` (1.4) para filtrar, `upsert_tender()` (1.7) para persistir. Esta subfase es principalmente **orquestación**, no lógica nueva de parseo.
- **Descarga a fichero temporal**, no en memoria: un ZIP de ~200 MB en memoria por cada mes procesado es descuidado para un worker con recursos acotados; se descarga a un fichero temporal (`tempfile`) y se procesa desde ahí.
- **Nuevo módulo `ingestion/historical_loader.py`**: construcción de URLs, cálculo de qué (año, mes) corresponden a "los últimos N meses", descarga, iteración de entradas del ZIP, y la orquestación completa (parsear → filtrar por vertical → upsert).
- **Script de entrada** vía `if __name__ == "__main__":` en el propio módulo (invocable con `uv run python -m compass.ingestion.historical_loader`), no una carpeta `scripts/` nueva — no hay más scripts todavía que justifiquen esa estructura.
- **Tests con un ZIP sintético construido en memoria** (no el ZIP real de 191 MB — ni de lejos algo para commitear ni para descargar en cada `pytest`), reutilizando el mismo patrón de HTTP mockeado de la 1.5 para la descarga.

## Progreso

### Paso 1 — URL builder + cálculo de "últimos N meses" (pendiente)

### Paso 2 — Descarga a fichero temporal + iteración de entradas del ZIP (pendiente)

### Paso 3 — Orquestación: parsear → filtrar vertical → upsert (pendiente)

### Paso 4 — Tests con ZIP sintético (pendiente)

### Paso 5 — Verificación final (pendiente, incluye decidir alcance de una corrida real contra PLACSP)
