# Subfase 5.6 — Evals del texto libre

## Plan acordado

`analysis/scoring.py` puntúa nueve campos —los números, los booleanos y la lista de
certificaciones— comparándolos con la anotación a mano del golden set. Es una prueba
fuerte y no necesita ningún modelo de por medio. Pero deja fuera, a propósito, las **siete
descripciones en texto libre** que el modelo también escribe:

| Campo | Qué describe |
| --- | --- |
| `economic_solvency.description` | la solvencia económica tal como la exige el pliego |
| `technical_solvency.description` | la solvencia técnica |
| `guarantees.description` | garantía provisional y definitiva |
| `execution_deadline.description` | plazo de ejecución y prórrogas |
| `submission_deadline.description` | fecha límite de presentación |
| `subcontracting.description` | condiciones de subcontratación |
| `lots.description` | estructura de lotes, o su ausencia razonada |

Son la mitad de lo que el analista devuelve, son lo que una persona lee de verdad en la
ficha — y hoy **no las mide nadie**. No se pueden comparar cadena a cadena con una
anotación: dos resúmenes correctos del mismo párrafo no se parecen en nada como texto.

### Qué se mide, y qué no

Sólo **fidelidad** (`Faithfulness` de RAGAS): descomponer la descripción en afirmaciones
atómicas y comprobar, una a una, si el contexto las sostiene. Es exactamente la pregunta
que importa aquí — *¿esto está en el pliego o se lo ha inventado?* — y es la que ninguna
comprobación de Python puede responder, porque exige entender que «prórroga de dos años»
y «podrá prorrogarse por dos anualidades» dicen lo mismo.

Fuera quedan, por decisión:

- **Fidelidad de las citas.** Ya la comprueba `verification.verify_citation` en Python,
  literalmente: la cita aparece o no aparece en la página que dice. Un juez LLM opinando
  sobre eso es más caro, más lento y menos fiable que un `in` sobre una cadena.
- **`context_precision` / `context_recall`.** Miden un paso de recuperación, y el agente
  analista no recupera: se le da el pliego entero, página a página.

### El contexto de cada muestra: la página citada, no el pliego entero

Cada descripción viaja con su cita, y la cita dice en qué página está lo que la sostiene.
Así que el contexto de la muestra es **el texto de esa página, más la anterior y la
siguiente** — una ventana, porque una cláusula parte por el salto de página sin avisar.

Meter el pliego entero (entre 20 y 120 páginas) como contexto no sólo multiplicaría el
gasto: empeoraría la medida. Un juez al que se le da todo encuentra apoyo para casi
cualquier afirmación en algún rincón del documento, y la métrica se satura en 1,0 sin
distinguir nada.

Las descripciones **sin cita** no se puntúan: no hay contra qué medirlas. Se cuentan y se
informan aparte, nunca como un cero — un cero diría «se lo inventó» y lo que pasa es otra
cosa.

### De dónde salen las extracciones

De la base de datos, no de una corrida nueva: `tender_analyses` ya guarda cuatro
extracciones completas y pagadas. Re-extraer para evaluar gastaría cuota en la mitad
barata del problema. El script descarga el PCAP y le saca las páginas —eso es gratis, ni
un solo token— y evalúa la extracción que ya existe.

### La cuota manda en el diseño

El nivel gratuito de OpenRouter son **50 peticiones al día**, y RAGAS gasta llamadas de
juez por muestra. Así que, mismo criterio que `regression_eval` en la 4.4: **se ejecuta a
mano, nunca en CI, nunca dentro de `pytest`**, y con un `--limit` para acotar el gasto por
corrida. Cuántas llamadas cuesta cada muestra no se supone: se mide en la primera corrida y
se escribe aquí.

### Lo que se toca

- `backend/src/compass/analysis/freetext_eval.py` — nuevo, mismo patrón que
  `regression_eval.py`: script ejecutable, no importado por el producto.
- `backend/pyproject.toml` / `uv.lock` — `ragas` y `langchain-openai`, dependencia nueva
  avisada y aceptada al planificar la fase.
- `backend/tests/analysis/test_freetext_eval.py` — sobre las partes puras.
- Los comentarios que todavía nombran RAGAS como pendiente (`golden_set.py`, `models.py`,
  `verification.py`, `CLAUDE.md`) pasan a decir lo que de verdad mide cada cosa.

### Criterios de aceptación

1. `uv run python -m compass.analysis.freetext_eval --limit 1` corre de punta a punta
   contra un pliego real de la base y saca una puntuación de fidelidad por cada
   descripción con cita.
2. El número de llamadas al juez por muestra queda **medido** en una corrida real y
   escrito en este documento, junto con cuántos pliegos caben en los 50/día.
3. Las descripciones sin cita se informan en su propio recuento, nunca como 0,0.
4. El script no se ejecuta en CI ni en la suite; los tests cubren la construcción de
   muestras y la ventana de páginas, sin red.
5. Al menos una puntuación baja se revisa **a mano contra el pliego**, y este documento
   dice si la métrica acertaba o se equivocaba. Un eval que nadie ha calibrado no vale
   como eval.
6. `uv run pytest`, `ruff check`, `ruff format --check` y `mypy` limpios, y CI en verde.

## Progreso
