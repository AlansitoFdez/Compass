# Subfase 1.6 — Parser CODICE

## Plan acordado

Del desglose de la Fase 1 (`docs/phases/phase1/phase1.md`): mapeo del XML CODICE a los 12-15 campos del modelo Pydantic (`TenderSchema`, 1.3). Tests con fixtures reales del feed.

### Investigación (contra un `<entry>` real del feed, no asumida)

Se descargó un `<entry>` real completo (52.729 caracteres) del feed en vivo y se inspeccionó campo a campo. Namespaces XML involucrados:

| Prefijo | URI |
|---|---|
| `atom` | `http://www.w3.org/2005/Atom` |
| `cac-place-ext` | `urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2` |
| `cbc` | `urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2` |
| `cbc-place-ext` | `urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2` |
| `cac` | `urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2` |

### Mapeo de campos verificado

| Campo `TenderSchema` | Ruta XML (desde `cac-place-ext:ContractFolderStatus`) |
|---|---|
| `expediente` | `cbc:ContractFolderID` |
| `contracting_body` | `cac-place-ext:LocatedContractingParty/cac:Party/cac:PartyName/cbc:Name` |
| `title` | `cac:ProcurementProject/cbc:Name` |
| `cpv_codes` | `cac:ProcurementProject/cac:RequiredCommodityClassification/cbc:ItemClassificationCode` (varios) |
| `budget_with_vat` | `cac:ProcurementProject/cac:BudgetAmount/cbc:TotalAmount` |
| `budget_without_vat` | `cac:ProcurementProject/cac:BudgetAmount/cbc:TaxExclusiveAmount` |
| `estimated_value` | `cac:ProcurementProject/cac:BudgetAmount/cbc:EstimatedOverallContractAmount` |
| `contract_type` | `cac:ProcurementProject/cbc:TypeCode` (código → enum, tabla abajo) |
| `procedure_type` | `cac:TenderingProcess/cbc:ProcedureCode` (código → etiqueta, tabla abajo) |
| `status` | `cbc-place-ext:ContractFolderStatusCode` (código → enum, tabla abajo) |
| `submission_deadline` | `cac:TenderingProcess/cac:TenderSubmissionDeadlinePeriod/cbc:EndDate` + `cbc:EndTime` (combinar) |
| `location` | `cac:ProcurementProject/cac:RealizedLocation/cbc:CountrySubentity` |
| `pcap_url` | `cac:LegalDocumentReference/cac:Attachment/cac:ExternalReference/cbc:URI` |
| `ppt_url` | `cac:TechnicalDocumentReference/cac:Attachment/cac:ExternalReference/cbc:URI` |
| `platform_url` | `atom:link/@href` (a nivel del `<entry>`, no dentro de `ContractFolderStatus`) |
| `published_at` | `atom:updated` (mismo valor que `updated_at_source`, ver decisión) |
| `updated_at_source` | `atom:updated` |

**Importante — solo el `ProcurementProject` de nivel superior**: una licitación puede tener además varios `ProcurementProjectLot` (lotes), cada uno con su propio presupuesto y CPV. Se ignoran deliberadamente los desgloses por lote — mismo criterio de mapeo parcial que ya rige el resto del proyecto.

### Tablas de códigos oficiales verificadas

Fuentes: [ContractCode-2.08.gc](https://contrataciondelestado.es/codice/cl/2.08/ContractCode-2.08.gc), [SyndicationContractFolderStatusCode-2.04.gc](https://contrataciondelestado.es/codice/cl/2.04/SyndicationContractFolderStatusCode-2.04.gc), [SyndicationTenderingProcessCode-2.07.gc](https://contrataciondelestado.es/codice/cl/2.07/SyndicationTenderingProcessCode-2.07.gc)

**`contract_type`** (`TypeCode` → `ContractType`, enum ampliado de 3 a 10 valores):

| Código | Enum |
|---|---|
| 1 | `SUPPLIES` |
| 2 | `SERVICES` |
| 3 | `WORKS` |
| 21 | `PUBLIC_SERVICES_MANAGEMENT` |
| 22 | `SERVICES_CONCESSION` |
| 31 | `PUBLIC_WORKS_CONCESSION` |
| 32 | `WORKS_CONCESSION` |
| 40 | `PUBLIC_PRIVATE_COLLABORATION` |
| 7 | `SPECIAL_ADMINISTRATIVE` |
| 8 | `PRIVATE` |
| 50 | `PATRIMONIAL` |

**`status`** (`ContractFolderStatusCode` → `TenderStatus`, se añade `CANCELLED`):

| Código | Enum |
|---|---|
| PRE | `PRIOR_NOTICE` |
| PUB | `OPEN_FOR_SUBMISSION` |
| EV | `PENDING_AWARD` |
| ADJ | `AWARDED` |
| RES | `RESOLVED` |
| ANUL | `CANCELLED` (nuevo) |

**`procedure_type`** (`ProcedureCode` → etiqueta en español, `str` plano):

| Código | Etiqueta |
|---|---|
| 1 | Abierto |
| 2 | Restringido |
| 3 | Negociado sin publicidad |
| 4 | Negociado con publicidad |
| 5 | Diálogo competitivo |
| 6 | Contrato menor |
| 7 | Derivado de acuerdo marco |
| 8 | Concurso de proyectos |
| 9 | Abierto simplificado |
| 10 | Asociación para la innovación |
| 11 | Derivado de asociación para la innovación |
| 12 | Basado en un sistema dinámico de adquisición |
| 13 | Licitación con negociación |
| 100 | Normas internas |
| 999 | Otros |

### Decisiones tomadas en la conversación de planificación

- **`ContractType` ampliado a los 10 códigos oficiales** (no 3 + valor de reserva): mismo criterio que con `status` — ahora que la lista está verificada y es genuinamente cerrada, un enum completo es más correcto que un fallback ad-hoc.
- **Nuevo valor `CANCELLED` en `TenderStatus`**: una licitación anulada es semánticamente distinta de una resuelta (proceso abortado vs. proceso llegado a su fin normal) — mezclarlas perdería una distinción real para un proveedor evaluando si mirar la licitación. Requiere una migración nueva (solo cambia el `CHECK` constraint, gracias a `native_enum=False` decidido en la 1.3 — sin la complicación de alterar un `ENUM` nativo de Postgres).
- **`procedure_type` guarda la etiqueta legible en español** (ej. "Abierto"), no el código crudo ("1") — la tabla está verificada contra la fuente oficial, sin riesgo de inventar valores, y es más útil para cualquiera que consulte la base de datos directamente.
- **`published_at` = mismo valor que `updated_at_source`** (el `<updated>` del propio ATOM) por ahora: simplificación reconocida — en la primera ingesta de una licitación nueva ambos coinciden de todas formas. Revisar si hace falta más precisión (ej. cuando se implemente la carga histórica en 1.8 y se vean modificaciones reales).
- **Namespaces vía diccionario de `ElementTree`** (`root.find("cac:ProcurementProject/cbc:Name", NS)`), no interpolación manual de `{uri}` en cada tag como en `atom_client.py` — con 4 namespaces distintos, interpolar a mano sería muy verboso y propenso a errores. `atom_client.py` solo tenía 1 namespace, ahí sí compensaba.
- **Nuevo módulo `ingestion/codice_codes.py`** para las tres tablas de códigos, separado del parser en sí — mismo criterio de responsabilidad única que ya se aplicó separando `tenders/enums.py` de `tenders/models.py`.

## Progreso

### Paso 1 y 2 (combinados) — Ampliar `ContractType` a 10 valores + añadir `CANCELLED` a `TenderStatus` (completado)

Se hicieron juntos: mismo tipo de arreglo (enums incompletos frente a las tablas oficiales), descubierto y verificado en la misma investigación.

- `tenders/enums.py`: `ContractType` ampliado a los 10 valores oficiales; `TenderStatus` con `CANCELLED` añadido.
- `uv run alembic revision --autogenerate` solo detectó cambio en `contract_type` (no en `status`) — investigado por qué en vez de asumir que estaba bien:
  - **Corrección a algo que dije mal en la 1.3**: `native_enum=False` en SQLAlchemy 2.0 **no crea ningún `CHECK` constraint** — verificado directamente (`Enum(...).create_constraint` es `False` por defecto). Solo crea una columna `VARCHAR` dimensionada al valor más largo del enum. En la 1.3 dije "VARCHAR+CHECK"; era solo VARCHAR — todavía más simple de evolucionar de lo que pensaba entonces, porque no hay ningún constraint que alterar, solo el ancho de columna si hace falta.
  - Confirmado contra la base de datos real (`\d+ tenders`): efectivamente, cero `CHECK` constraints en la tabla.
  - **Por qué autogenerate no detectó `status`**: el valor más largo de `TenderStatus` seguía siendo `"open_for_submission"` (20 caracteres) — `"cancelled"` (9) cabe de sobra en la columna `VARCHAR(19)` ya existente. No hace falta ninguna migración para `status`, el cambio en Python ya es suficiente.
  - `contract_type` sí necesitaba migración: el valor más largo pasó de 8 caracteres (`"services"`/`"supplies"`) a 28 (`"public_private_collaboration"`).
- Migración `364d5b8e1271` aplicada: `contract_type` de `VARCHAR(8)` a `VARCHAR(28)`.
- Verificado de extremo a extremo con un insert real (rollback después, sin dejar datos): `contract_type=PUBLIC_PRIVATE_COLLABORATION` y `status=CANCELLED` se guardan y leen correctamente a través del ORM.

### Paso 3 — `ingestion/codice_codes.py`: las tres tablas de códigos (pendiente)

### Paso 4 — `ingestion/codice_parser.py`: mapeo campo a campo a `TenderSchema` (pendiente)

### Paso 5 — Tests con el fixture real guardado (pendiente)

### Paso 6 — Verificación final: Docker, ruff, pytest (pendiente)
