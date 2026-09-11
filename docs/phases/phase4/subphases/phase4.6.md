# Subfase 4.6 — CI con GitHub Actions

## Plan acordado

Del desglose de la Fase 4 (`docs/phases/phase4/phase4.md`): job principal (`pytest` +
`ruff` + `mypy` en cada push, con Postgres/Redis como *service containers*) que bloquea
el merge; job de evals (RAGAS de la 4.4) separado, visible pero no bloqueante.

**Desviación del plan de fase, decidida al arrancar la subfase**: el job de evals no
entra en CI. La 4.4 ya dejó anotado que había que decidirlo aquí ("un job de evals que
lance las 25 del golden set en cada push se comería la mitad del cupo diario"), y la
medición previa a escribir nada añadió un impedimento más duro que el cupo:
`regression_eval.py` lee los `pcap_url` de las 25 entradas **desde la base de datos**
(`_fetch_pcap_urls`), y la base de un runner de GitHub solo tiene migraciones — no el
corpus real de PLACSP. El eval se queda como comando local bajo demanda; el workflow
documenta por qué no está ahí. Las alternativas consideradas y descartadas: duplicar los
25 `pcap_url` dentro del golden set (datos del corpus copiados fuera de la base, que
envejecen solos) y meter el workflow igualmente aunque en CI no encuentre ningún PCAP
(cumple la letra del plan, no su intención).

### Lo que se mide antes de escribir el workflow

La suite corre hoy contra la base real de Alan, con el corpus de PLACSP y el perfil de
proveedor sembrados. Antes de asumir cuántos tests sobreviven a una base vacía, se mide:
base nueva (`compass_ci`) en el mismo Postgres, `alembic upgrade head`, misma suite.

### Criterios de aceptación

1. `.github/workflows/ci.yml` corre en cada push a `main` y en cada pull request:
   `ruff check`, `ruff format --check`, `mypy` y `pytest` contra Postgres (imagen
   pgvector) y Redis como *service containers*, con las migraciones aplicadas y el
   perfil de proveedor sembrado.
2. Los tests que dependen del corpus real llevan `@pytest.mark.real_corpus` y quedan
   deseleccionados en CI; `uv run pytest -m "not real_corpus"` pasa entero contra una
   base recién migrada y sembrada, y `uv run pytest` sin filtro sigue pasando entero en
   local.
3. El marcador está registrado en `pyproject.toml` y `--strict-markers` está activo: un
   marcador mal escrito falla en vez de ignorarse en silencio.
4. `uv run pytest`, `ruff check --fix`, `ruff format`, `mypy` limpios.
5. El workflow aparece en verde en GitHub Actions después del push — evidencia real de
   una corrida, no un YAML que parece correcto.

## Progreso

### Qué depende de verdad del corpus real: 3 tests de 198

Medido, no supuesto. Base nueva `compass_ci` en el mismo contenedor de Postgres (crear
una base no toca la real; `docker compose down -v` no entra aquí), `alembic upgrade
head`, y la suite completa apuntando ahí con `DATABASE_URL` por variable de entorno —
que en pydantic-settings tiene prioridad sobre el `.env`, así que el desvío no exige
tocar ningún fichero:

| Base | Resultado |
|---|---|
| Real (corpus + proveedor sembrado) | **198 passed** |
| `compass_ci` recién migrada, vacía | 194 passed, **4 failed** |
| `compass_ci` + `python -m compass.providers.seed` | 195 passed, **3 failed** |

El cuarto fallo desaparece solo con sembrar el proveedor, y eso **sí** es reproducible en
CI: `providers/seed.py` lleva el perfil real escrito en el propio repo, no en la base. Es
un paso del workflow, no un test a excluir.

Los tres que quedan dependen del corpus de PLACSP persistido en la máquina de Alan, que
un runner no tiene y que no tiene sentido fabricar:

- `test_golden_set_covers_exactly_the_real_etapa1_survivors` (2.6) — compara el golden
  set de matching contra los supervivientes reales de Etapa 1. Su razón de existir es
  detectar que el corpus real cambió; contra un corpus sintético no protege nada.
- `test_golden_set_expedientes_still_exist_with_a_pcap_url` (4.3) — comprueba que los 25
  expedientes anotados siguen existiendo con su PCAP descargable. Mismo caso.
- `test_get_matches_returns_envelope_shape_ranked_by_rrf_score` (2.6) — necesita el
  proveedor sembrado *y* un corpus embebido real para que el embudo devuelva algo. La
  lógica de fusión en sí ya está cubierta por `test_fusion.py`, que se siembra sus
  propias filas y por eso sí corre en CI.

Los tres llevan ahora `@pytest.mark.real_corpus`, registrado en `pyproject.toml` junto
con `--strict-markers` en `addopts`: sin eso, un `@pytest.mark.real_corpuss` mal escrito
se ignoraría en silencio y el test volvería a CI sin que nadie se entere. Excluir un test
del CI es justo el tipo de decisión que no puede depender de acertar al teclear.

**El 195/198 es el dato honesto de esta subfase**: CI no corre la suite entera, y decir
"los tests pasan en verde" sin esta nota sería falso. Lo que CI garantiza es todo lo que
no necesita datos que solo existen en una máquina.

### El workflow

`.github/workflows/ci.yml`, un solo job (`quality`) sobre `ubuntu-latest`, disparado en
push a `main` y en cada pull request:

- **Servicios**: `pgvector/pgvector:0.8.6-pg17` y `redis:8-alpine` — las mismas imágenes
  exactas de `docker-compose.yml`, para que CI y local no diverjan en la versión del
  motor. En el runner se publican en los puertos por defecto (5432/6379); el 5433 de
  local existe solo para no chocar con un PostgreSQL nativo de Windows, un problema que
  un contenedor de Linux no tiene.
- **Entorno**: `DATABASE_URL` y `REDIS_URL` apuntando a esos servicios, y valores ficticios
  para `OPENROUTER_API_KEY` y las claves de Langfuse — `Settings` las exige (sin ellas el
  proceso no arranca), pero ningún test los usa de verdad: las llamadas a OpenRouter están
  mockeadas desde la 3.x y `conftest.py` desactiva el envío de trazas de Langfuse. **Ningún
  secreto de GitHub hace falta para este job**, que es la comprobación de que de verdad no
  se llama a nada de pago.
- **Pasos**: `uv sync --locked --all-groups` (el `--locked` falla si `uv.lock` no está al
  día con `pyproject.toml`, así que un lock olvidado es un fallo de CI, no una
  reinstalación silenciosa) → `ruff check` → `ruff format --check` → `mypy` → migraciones
  → siembra del proveedor → `pytest -m "not real_corpus"`.
- **Orden deliberado**: lint y tipos antes que los tests. Son segundos contra minutos, y
  fallan por cosas que no hace falta una base de datos para ver.
- **Caché del modelo de embeddings**: `~/.cache/huggingface`, cacheado con clave derivada
  del hash de `embeddings.py` — el fichero que nombra el modelo, así que cambiarlo invalida
  la caché sola. Sin esto, cada corrida se descargaría ~570 MB de Hugging Face para los
  tests de `test_vector.py`/`test_fusion.py`, que usan el modelo real a propósito (2.5).
- **Versiones ancladas**: `uv` a la misma versión que generó el lock, y las acciones a una
  referencia que existe de verdad (ver más abajo: `setup-uv` no publica tag móvil de major).

### El hallazgo caro: en Linux, `torch` trae 2,6 GB de CUDA que nadie usa

Antes de escribir el workflow se midió qué instalaría de verdad `uv sync` en un runner,
leyendo `uv.lock` en vez de suponerlo. El resultado cambió la subfase:

| Plataforma | Instalación |
|---|---|
| Windows (local) | el wheel de `torch` de PyPI ya es CPU-only |
| Linux (CI), antes | **~3,3 GB**, de los cuales ~2,6 GB en wheels de NVIDIA (`nvidia-cudnn` 651 MB, `nvidia-cublas` 543 MB, `triton` 226 MB...) |
| Linux (CI), después | **~320 MB** (187 MB el propio `torch+cpu`) |

`sentence-transformers` arrastra `torch`, y el wheel de PyPI para Linux lleva la pila CUDA
entera detrás — inútil en un runner sin GPU, y lo bastante grande como para que cada
corrida se fuera en descargas y como para reventar la caché de uv de GitHub (10 GB por
repo). La solución es el índice CPU de PyTorch, pero tiene un detalle que costó un intento:
**`[tool.uv.sources]` solo se aplica a dependencias directas**. Con `torch` como transitiva,
`uv lock` no cambió ni una línea. Por eso `torch` pasa a estar declarada en
`[project.dependencies]`: no añade nada al entorno — ya estaba instalada — pero es el único
sitio desde el que se puede elegir la variante del wheel. El `marker = "sys_platform ==
'linux'"` deja Windows exactamente como estaba (`uv sync --locked` en local no reinstaló
nada más que el propio paquete `compass`).

### Tres corridas hasta el verde

La primera y la segunda fallaron en `Set up job`, antes de ejecutar un solo paso:
`Unable to resolve action astral-sh/setup-uv@v10`. **`astral-sh/setup-uv` no publica tag
móvil de major** — solo versiones exactas (`v10.1.0`), al revés que `actions/checkout` (`v7`)
y `actions/cache` (`v6`), que sí los publican. Comprobado con `git ls-remote --tags` sobre
los tres repos, no adivinado. Anclado a `v10.1.0`.

Corrida verde (`bb5273d`), **136 s en total**:

| Paso | Tiempo | Resultado |
|---|---|---|
| Levantar contenedores (Postgres + Redis) | 29 s | healthy |
| `uv sync --locked --all-groups` | 9 s | `torch==2.14.0+cpu` (187 MiB) |
| `ruff check` + `ruff format --check` | 1 s | `All checks passed!` |
| `mypy` | 42 s | sin errores |
| Migraciones + siembra del proveedor | 2 s | ok |
| `pytest -m "not real_corpus"` | 31 s | **195 passed, 3 deselected in 17,22 s** |

El `torch==2.14.0+cpu` del log es la confirmación de que el índice CPU se aplicó de verdad
en el runner, no solo en el lock. La caché de Hugging Face falló en esta corrida (`Cache not
found`, era la primera) y se guardó al terminar: a partir de la siguiente, el modelo no se
vuelve a descargar.

### Cierre

Los cinco criterios de aceptación se cumplen, con la corrida verde como evidencia del
quinto. Lo que CI **no** cubre queda escrito, no implícito: tres tests que dependen del
corpus real, y el eval de regresión de la 4.4, que se queda como comando local por la misma
razón más el cupo diario de OpenRouter.
