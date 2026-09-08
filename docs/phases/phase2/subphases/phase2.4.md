# Subfase 2.4 — Golden set y decisión de embeddings

## Plan acordado

Del desglose de la Fase 2 (`docs/phases/phase2/phase2.md`): un golden set pequeño anotado a mano sobre licitaciones reales, usado para medir recall@k de 2-3 candidatos a modelo de embeddings antes de elegir. El mismo artefacto sirve de base para el golden set de RAGAS en la Fase 4.

### Decisión de alcance tomada al planificar

- **Candidatos gratuitos primero, no de pago.** Sin claves de OpenAI/Voyage disponibles y con coste real de por medio, se descartó Groq (su único modelo de embeddings, `nomic-embed-text-v1.5`, es estrictamente inglés -- verificado contra su propia ficha técnica, colapsa con español) y se optó por dos modelos multilingües gratuitos, descargados del Hub de Hugging Face y corridos en local vía `sentence-transformers` (nueva dependencia, avisada antes de añadirla): `ibm-granite/granite-embedding-278m-multilingual` y `intfloat/multilingual-e5-base`. Ambos con salida de 768 dimensiones -- comparación directa, sin truncar nada.
- **Modelo baja al disco, no a Docker.** El backend corre nativo (`uv run`), no en contenedor -- los pesos se cachean en `~/.cache/huggingface/hub`. Empaquetar el modelo en una imagen Docker es trabajo de despliegue (Fase 5), anotado en memoria para entonces.
- **Golden set sobre la población completa de la Etapa 1, no una muestra pequeña.** Los 61 supervivientes reales de la Etapa 1 (perfil sembrado en 2.1/2.2), no una selección arbitraria de 15-20 -- da una medición de recall@k mucho más robusta.

### Criterios de aceptación

1. Golden set anotado y verificado por test contra la población real de la Etapa 1 (categorías disjuntas, unión = supervivientes reales).
2. Recall@k medido con números reales para los dos candidatos gratuitos y para el ranking léxico de la 2.3, no estimado.
3. Modelo y dimensión decididos con el número delante, documentados aquí.
4. `uv run mypy` y `uv run ruff check`/`format --check` limpios sobre todo el código nuevo.

## Progreso

### Paso 1 — Golden set: anotación y criterio

Se repasaron los 61 títulos reales uno a uno contra la especialidad declarada del perfil (*"desarrollamos aplicaciones web a medida y mantenemos portales institucionales... Drupal, WordPress... accesibilidad, sede electrónica... ENS"*).

**Criterio de anotación, hecho explícito**: un expediente cuenta como relevante solo si lleva una señal concreta -- la palabra "web"/"portal" en el título, una de las tecnologías nombradas (Drupal, WordPress, o su familia cercana como CiviCRM/OpenCms), accesibilidad explícita, o sede electrónica/tramitación electrónica explícita. "Desarrollo"/"aplicación"/"plataforma" en sentido genérico no basta por sí solo -- es exactamente el tipo de ruido que ya produjo el OR léxico de la 2.3 (1.526 coincidencias sobre el corpus completo), y este golden set existe para medir si el modelo semántico distingue mejor que eso.

**15 relevantes** (con esa señal explícita): mantenimiento de portales Drupal, plugins WordPress, CiviCRM, OpenCms+PHP, hosting/mantenimiento web, visor web GIS, accesibilidad, sede electrónica/tramitación, etc.

**5 excluidos del todo** (ambiguos incluso bajo ese criterio, ni relevante ni no-relevante): una app móvil (disciplina distinta a "aplicaciones web"), mantenimiento de una suite financiera de un fabricante concreto (sicalwin), una PoC de migración con agentes de IA, y dos implantaciones de plataformas SaaS genéricas (RRHH/tributos) -- una anotación incierta es peor que ninguna para un conjunto que mide precisión.

**41 no relevantes**: el resto -- telecomunicaciones, hardware, RPA, IA genérica, ciberseguridad, software financiero/sanitario específico de un fabricante, eventos, redes sociales, etc.

- `matching/golden_set.py`: `RELEVANT_EXPEDIENTES`, `NOT_RELEVANT_EXPEDIENTES`, `EXCLUDED_EXPEDIENTES` como `frozenset[str]`, con el criterio documentado en el docstring del módulo -- reutilizable tal cual para el golden set de RAGAS en la Fase 4.
- `tests/matching/test_golden_set.py`: las tres categorías son disjuntas entre sí, y su unión coincide exactamente con los supervivientes reales de la Etapa 1 ahora mismo -- protege el golden set de quedarse obsoleto en silencio si el corpus o el perfil cambian. **Verificado**: pasa contra Postgres real, confirma que la transcripción de los 61 expedientes (recuperados a un fichero UTF-8, no impresos en la consola de Windows -- que corrompía los acentos, `Gesti�n` en vez de `Gestión`) es exacta y completa.

### Paso 2 — Script de comparación y medición real

- `matching/embedding_eval.py`: `recall_at_k()` (función pura, testeada aparte) + `rank_by_semantic_similarity()` (codifica proveedor y títulos en un único batch por modelo, rankea por similitud coseno con `sentence_transformers.util.cos_sim`) + un `_main()` invocable con `uv run python -m compass.matching.embedding_eval`, mismo patrón que `historical_loader.py`/`seed.py`.
- No es código del funnel en producción -- es la herramienta de decisión de esta subfase, documentada y conservada para poder repetir el experimento si el golden set o el perfil cambian.

**Resultado real, contra los 56 tenders del golden set (15 relevantes) y el perfil sembrado**:

| | recall@5 | recall@10 | recall@15 |
|---|---|---|---|
| Léxico (2.3, `ts_rank`) | 0.20 | 0.40 | 0.47 |
| `granite-embedding-278m-multilingual` | **0.33** | **0.47** | **0.67** |
| `multilingual-e5-base` | 0.20 | 0.40 | 0.60 |

`granite-embedding-278m-multilingual` gana en los tres cortes. Su top-5 son 5 de 5 relevantes (Hipatia, bolsa de empleo, portales Drupal de Jaén, hosting web, mantenimiento de administración electrónica); `multilingual-e5-base` cuela 2 falsos positivos en su propio top-5 (una plataforma corporativa de IA, una consultoría de protección de datos) pese a un recall@15 razonable.

**La premisa del diseño híbrido, confirmada con números, no solo con la teoría del documento de diseño**: el semántico (0.67 en recall@15) supera con margen claro al léxico solo (0.47) -- justo la razón de que la Etapa 2 combine ambos en vez de quedarse con uno.

### Paso 3 — Decisión

**Modelo elegido: `ibm-granite/granite-embedding-278m-multilingual`, 768 dimensiones.** Gratuito, corre en local, mejor recall@k que el otro candidato gratuito y que el léxico solo, sobre el golden set real.

**Sobre los candidatos de pago (OpenAI, Voyage)**: quedan fuera de esta comparación por falta de clave -- no por descarte técnico. 768 dimensiones cabe holgado bajo el límite de 2000 de un índice HNSW/IVFFlat de pgvector con el tipo `vector` normal (visto en la primera conversación de la fase), así que la decisión de dimensión no bloquea nada. Si más adelante hay clave disponible, se pueden añadir a este mismo experimento sin tirar nada de lo hecho -- el script y el golden set ya están listos para ello.

**768 dimensiones fija la columna `Vector(768)` de pgvector**, que construye la 2.5.

Subfase 2.4 completada. Los cuatro criterios de aceptación se cumplen.
