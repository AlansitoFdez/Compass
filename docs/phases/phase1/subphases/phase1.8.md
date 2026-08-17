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

### Paso 1 — URL builder + cálculo de "últimos N meses" (completado)

- `monthly_archive_url(year, month)` — `f"...{year:04d}{month:02d}.zip"`, formato `AAAAMM` verificado en la investigación.
- `recent_months(count, today=None)` — `today` como parámetro opcional inyectable (no `date.today()` escondido dentro), para que los tests puedan fijar una fecha concreta y determinista en vez de depender de cuándo se ejecuten. Devuelve tuplas `(año, mes)` de más antiguo a más reciente, manejando el cruce de año (retroceder desde enero cae en diciembre del año anterior).
- Verificado manualmente: `recent_months(3, today=date(2026, 8, 17))` → `[(2026,6), (2026,7), (2026,8)]`; con `today=date(2026, 1, 15)` → `[(2025,11), (2025,12), (2026,1)]` (cruce de año correcto).

### Paso 2 — Descarga a fichero temporal + iteración de entradas del ZIP (completado)

- `download_archive(url, client)` — `client.stream("GET", url)` + `response.iter_bytes()` escritos a un `tempfile.NamedTemporaryFile(delete=False)`: nunca carga los ~200 MB enteros en memoria de golpe, y `delete=False` porque el fichero tiene que sobrevivir al `with` para poder abrirlo luego con `zipfile`.
- `iter_entries_from_zip(zip_path)` — reutiliza `parse_atom_page()` (1.5) para cada fichero `.atom` dentro del ZIP; ignora cualquier fichero que no termine en `.atom` (defensivo).
- `iter_entries_from_url(url, client)` — une descarga + lectura en un `try/finally` que borra el fichero temporal pase lo que pase, incluso si algo falla a mitad de la lectura del ZIP.
- Verificado con un ZIP sintético construido en memoria (2 ficheros `.atom` + 1 `.txt` que debe ignorarse): 3 entradas encontradas correctamente, el `.txt` ignorado. La descarga real de un mes completo se deja para la verificación final (paso 5), para no repetir una descarga de 191 MB varias veces en la misma sesión.

### Paso 3 — Orquestación: parsear → filtrar vertical → upsert (completado)

- `load_month(year, month, client, session)` — descarga, itera entradas, parsea con `parse_codice_entry()` (1.6), filtra con `matches_it_vertical()` (1.4), persiste con `upsert_tender()` (1.7) solo si coincide. Devuelve cuántas se guardaron. **No hace `commit()`** — deja el control de la transacción a quien la llama, para que sea testeable con el patrón habitual de rollback.
- `_main()` + bloque `if __name__ == "__main__":` — el script en sí, invocable con `uv run python -m compass.ingestion.historical_loader`. Recorre `recent_months(3)` y hace `commit()` **después de cada mes completo** — ni tan fino como cada fila (overhead innecesario) ni tan grueso como solo al final (perdería todo el progreso si falla tarde en la corrida).
- Import de `async_session_factory` diferido dentro de `_main()`, no a nivel de módulo: las funciones de librería (`load_month`, `recent_months`...) no necesitan saber cómo se construye una sesión real, la reciben como parámetro — solo el script en sí la necesita.
- Verificado manualmente (HTTP mockeado + Postgres real, sin descarga real todavía): un ZIP simulado conteniendo la entrada real del fixture (1.6) — que está fuera de nuestro vertical, CPV de las divisiones 30/39/48 — resultó correctamente en **0 persistidas**. Prueba que toda la cadena funciona de extremo a extremo para el caso "se filtra".

### Paso 4 — Tests con ZIP sintético (pendiente)

### Paso 5 — Verificación final (pendiente, incluye decidir alcance de una corrida real contra PLACSP)
