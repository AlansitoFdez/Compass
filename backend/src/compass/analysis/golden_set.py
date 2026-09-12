"""Golden set: real PCAPs, hand-annotated field by field.

Started in 3.4 with 4 pliegos to pick the extraction model; extended in 4.3 to 25-30
so the regression gate (`regression_eval`) measures citation faithfulness and extraction
correctness on enough documents to mean something. Same "small-to-medium, real, no blind
pick" method the 2.4 embedding decision and the 3.4 model decision both used, just at a
larger scale for that statistical purpose. RAGAS was expected here when 4.3 was planned;
it ended up in 5.6, scoring the descriptions this set deliberately doesn't annotate.

Each entry is a real `expediente` from the seeded provider's live matches (`GET
/matches`), picked for structural diversity, not for being easy: narrative
clause-numbered PCAPs alongside "Cuadro de Características" summary-table formats, and
each of solvencia/garantías/subcontratación/plazo/lotes intentionally varies in how (or
whether) it's expressed -- some as a hard euro threshold, some computed from a formula
the pliego states but doesn't pre-calculate, some as an insurance policy, some deferred
entirely to the anuncio de licitación or the PPT, some explicitly exempted. A model
that only pattern-matches "solvencia económica -> find a euro figure" will get some of
these wrong; that's the point.

**Real limitations found while building the 4.3 batch, not present in the original
4**: several real candidates considered for this set turned out structurally unusable
for extraction, for reasons worth knowing about rather than silently discarding:
- A PCAP whose `pcap_url` is a "pliego tipo" (template) that defers every concrete
  figure -- solvencia, plazos, garantía, criterios -- to a separate "Cuadro Resumen" or
  "Apartado"/"Anexo I" that isn't part of the downloaded document at all
  (`document.extract_pages` returns real text, just none of the substantive values).
  Seen six times among the discarded candidates -- common enough that a quick check
  for real "ANEXO I"/"CARACTERÍSTICAS" section content (not just a reference to one) is
  now the first triage step before committing to a full read.
- A PCAP (Ayuntamiento de Ayerbe, `1868392P`) whose every page extracts to nothing but
  its own digital-signature header/footer boilerplate -- the clause text itself never
  appears in `extract_pages`'s output, likely from how that municipality's e-signature
  platform overlays the signed stamp on the original document. `has_text_layer` would
  not catch this today: there's plenty of (repeated, boilerplate) text per page, just
  none of it substantive. Not fixed here -- flagged as a real gap for a future
  subphase, not this one's job (see phase4.3.md).
- A PCAP whose extraction comes back as reversed, letter-by-letter text interleaved
  with unmapped `(cid:N)` glyph codes for entire pages -- a broken font/encoding map in
  the source PDF, not an empty text layer, so `has_text_layer` doesn't catch this
  either.
- A PCAP dominated by a rotated diagonal watermark: `extract_pages` returns real
  characters, but ~93% of its lines are one or two stray characters from the
  watermark, with the substantive text unrecoverable from the noise.

Not a failure mode, but worth knowing when reading the entries below: three PCAPs
(Red.es, `003/26-SI`, `009/26-SG`, `015/25-SI`) split each tender's PCAP into two
documents by design -- "Condiciones Específicas" (downloaded here, the only one that's
`pcap_url`) and a separate, stable "Condiciones Generales" reused across many Red.es
expedientes. Garantías, lotes and the submission deadline live exclusively in the
latter, so those three fields are genuinely `None` for all three entries -- not a
missed citation, just outside the document this project ingests.

**Re-annotated in 5.8 for the schema change, against the PCAPs and not by inference.**
Two fields gained a required answer, and both were filled by reading the documents again
rather than by converting what was already written:

- `certifications` now carries a `role` per item. All 22 across the nine annotated
  entries came back `REQUIRED_TO_BID`, each confirmed in its own pliego -- clause 6.4 of
  `A41119033-2026/000065-PeAS` ("los licitadores deberán acreditar además el cumplimiento
  de los requisitos de solvencia técnica y profesional que se refieren a continuación"),
  clause 10.1.l) of `2545974A` ("Obligatoriamente licitador deberá entregar..."), clause
  12.A) "Habilitación" of `SERV-2026000088`, and the "se exige la presentación de
  certificado" clauses of the three Red.es pliegos. So the human labels were right all
  along; what the role field fixes is the *model's* output, not this file's.
- Each certification carries its own citation now, but only the first item of each list
  actually has one: the pre-5.8 annotation wrote a single citation per list, and that
  quote names only one certification. The rest are `None` rather than borrowing a quote
  that doesn't mention them. Citations aren't scored (`scoring.score_extraction`
  compares names and roles), so this costs the gate nothing.
- `execution_deadline` split into base duration plus `extensions_allowed` /
  `extensions_description`. Where the existing annotation stated the extensions, the
  split is a re-reading of it; where it said nothing, the PCAP was re-opened rather than
  marked unknown -- and that caught two entries that would have been labelled wrong.
  `A41119033-2026/000065-PeAS` defers the *duration* to the PPT but states on page 2 "No
  se ha previsto la posibilidad de prórroga", and `2026000731` says on page 16 "Dado que
  no se prevén prórrogas ni modificaciones". Both are `False`, not `None`. The three that
  remain `None` mention prórrogas nowhere at all (`23/2026`, and the two Red.es pliegos
  whose Condiciones Generales are a separate document, as noted above).

Annotated directly from the PCAP text (`compass.analysis.document.extract_pages`
against the tender's real `pcap_url`), not from a summary -- every `Citation.quote`
below is copied verbatim from the pliego. The 3.4 batch was downloaded 2026-09-09; the
4.3 batch, 2026-09-11.
"""

from compass.analysis.enums import CertificationRole
from compass.analysis.extraction_schema import (
    AwardCriteria,
    AwardCriterion,
    Citation,
    EconomicSolvency,
    ExecutionDeadline,
    Guarantees,
    Lots,
    PliegoExtraction,
    RequiredCertification,
    Subcontracting,
    SubmissionDeadline,
    TechnicalSolvency,
)

GOLDEN_SET: dict[str, PliegoExtraction] = {
    # Gobierno de Canarias -- sistema Hipatia. Narrative clause-numbered PCAP, 53
    # pages. Submission deadline deliberately deferred to the anuncio, not restated.
    "SER/2026/0000006435": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=37305.00,
            description="Volumen anual de negocios en el ámbito del contrato, mejor de los tres "
            "últimos ejercicios, mínimo 37.305,00 €.",
            citation=Citation(
                clause="4.3.1",
                page=6,
                quote="con un valor mínimo de treinta y siete\nmil trescientos cinco euros "
                "(37.305,00 €)",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=26113.50,
            description="Relación de principales servicios similares en los últimos tres años, con "
            "importe mínimo de 26.113,50 € en el mejor ejercicio.",
            citation=Citation(
                clause="4.3.2",
                page=6,
                quote="con un valor mínimo de veintiséis mil ciento trece euros con cincuenta "
                "céntimos (26.113,50 €)",
            ),
        ),
        certifications=[],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Experiencia del equipo", points=15, is_price=False),
                AwardCriterion(name="Adaptación de la arquitectura", points=15, is_price=False),
                AwardCriterion(name="Descripción de funcionalidades", points=15, is_price=False),
                AwardCriterion(name="Importe", points=30, is_price=True),
                AwardCriterion(name="Estabilidad en el empleo", points=25, is_price=False),
            ],
            citation=Citation(
                clause="12.1",
                page=12,
                quote="El contrato se adjudicará a la proposición que oferte la mejor relación "
                "calidad-precio",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Sin garantía provisional. Garantía definitiva del 5% del precio final "
            "ofertado (IGIC excluido); 10% adicional si la oferta estaba incursa en "
            "presunción de anormalidad.",
            citation=Citation(
                clause="21.1",
                page=25,
                quote="la constitución de la garantía definitiva por importe del 5 por 100 del "
                "precio final ofertado, IGIC excluido",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="Vigencia máxima de 2 años desde la formalización.",
            extensions_allowed=True,
            extensions_description="Prorrogable; la prestación del servicio tiene un máximo de 4 "
            "años incluyendo prórrogas.",
            citation=Citation(
                clause="10.1",
                page=11,
                quote="El contrato tendrá un plazo máximo de vigencia de dos años, computado a "
                "partir del día siguiente a su\nformalización",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se fija una fecha explícita en el PCAP; remite al plazo señalado en el "
            "anuncio de licitación de la Plataforma de Contratación del Sector Público.",
            citation=Citation(
                clause="13.1",
                page=16,
                quote="Las proposiciones y la documentación complementaria se presentarán, en el "
                "plazo señalado en el\nanuncio de licitación",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida, sujeta a declaración obligatoria en la oferta cuando implique "
            "tratamiento de datos personales (servidores/servicios asociados), "
            "identificando el subcontratista.",
            citation=Citation(
                clause="15.1.10",
                page=18,
                quote="Los licitadores deberán indicar expresamente, en el momento de la "
                "presentación de su oferta, si\ntienen previsto subcontratar los servidores o "
                "los servicios asociados",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No procede división en lotes: unidad funcional única del sistema HIPATIA, "
            "necesidad de coordinación técnica continua entre perfiles, y mayor "
            "coste/complejidad de gestión si se fragmentara.",
            citation=Citation(
                clause="1.2",
                page=2,
                quote="en la presente contratación no procede la división en\nlotes por los "
                "siguientes motivos",
            ),
        ),
    ),
    # INPRO (Sociedad Provincial de Informática de Sevilla) -- soporte y desarrollo
    # OpenCms/PHP. "Cuadro de Características" summary-table PCAP, 34 pages -- a
    # structurally different format from the other three, and the richest in
    # explicit certifications (CMMI, four ISO families, ENS).
    "A41119033-2026/000065-PeAS": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=58344.00,
            description="Volumen anual de negocios de al menos 1,5 veces el valor estimado del "
            "contrato (38.896,00 € x 1,5).",
            citation=Citation(
                clause="6.1",
                page=2,
                quote="deberá\nser al menos de una vez y media el valor estimado del "
                "contrato\nconforme al art. 87.3.a) LCSP. Esto es: 58.344,00 € (38.896,00 x "
                "1,5)",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=27227.20,
            description="Relación de principales suministros similares en los últimos tres años, "
            "con importe anual acumulado en el año de mayor ejecución igual o superior "
            "al 70% de la anualidad media del contrato (27.227,20 €).",
            citation=Citation(
                clause="6.2",
                page=3,
                quote="27.227,20 € (74.088,00 x 0,7) 70 % de la anualidad media del\ncontrato "
                "conforme al art.89.3 LCSP",
            ),
        ),
        certifications=[
            RequiredCertification(
                name="CMMI nivel 3 o superior",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=Citation(
                    clause="6.4",
                    page=3,
                    quote="Certificado expedido por organismo independiente, conforme a las "
                    "normas\nrelativas a la certificación, que acredite que el "
                    "empresario cumple con "
                    "la\ncertificación de Modelo de Madurez de Capacidades de Integración "
                    "(CMMI)\nnivel 3 o superior",
                ),
            ),
            RequiredCertification(
                name="ISO 9000 o equivalente",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=None,
            ),
            RequiredCertification(
                name="ISO 14000 o equivalente",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=None,
            ),
            RequiredCertification(
                name="ISO 20000 o equivalente",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=None,
            ),
            RequiredCertification(
                name="ISO 27000 o equivalente",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=None,
            ),
            RequiredCertification(
                name="ENS nivel medio/alto (certificado CCN-CERT)",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=None,
            ),
        ],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(
                    name="Calidad de la Oferta Técnica (juicio de valor)", points=40, is_price=False
                ),
                AwardCriterion(name="Oferta económica (fórmula)", points=60, is_price=True),
            ],
            citation=Citation(
                clause="9.1",
                page=4,
                quote="Puntuación Máxima: 40 puntos\nCriterio: Calidad de la Oferta Técnica",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Sin garantía provisional. Garantía definitiva del 5% del precio final "
            "ofertado (IVA excluido). Sin garantía complementaria.",
            citation=Citation(
                clause="8",
                page=4,
                quote="8.2. Definitiva: 5 % del precio final ofertado (excluido el IVA)",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="No se fija en el PCAP: remite al Pliego de Prescripciones Técnicas.",
            extensions_allowed=False,
            extensions_description=None,
            citation=Citation(
                clause="14.1",
                page=10,
                quote="Plazo de ejecución: Según lo previsto en el Pliego de Prescripciones "
                "Ténicas",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="15 días naturales a contar desde el siguiente a la publicación del "
            "anuncio en el perfil de contratante.",
            citation=Citation(
                clause="11.1",
                page=9,
                quote="15 días naturales para contar desde el siguiente a la publicación "
                "del\nanuncio en el perfil de contratante",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida para la realización parcial de la prestación. Penalidad del 10% "
            "del importe subcontratado si se incumplen las condiciones establecidas.",
            citation=Citation(
                clause="17.2",
                page=11,
                quote="el\ncontratista podrá concertar con terceros la realización parcial de "
                "la\nprestación",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes.",
            citation=Citation(clause="2.3", page=1, quote="2.3. Lotes: SI ( )\nNO ( X )"),
        ),
    ),
    # Ayuntamiento de Cieza -- hosting y plugins WordPress. Narrative
    # clause-numbered PCAP, 29 pages. Economic/technical solvency deliberately NOT
    # expressed as euro thresholds here (an insurance policy and a count of past
    # jobs instead) -- a case a model could get wrong by forcing a number.
    "1276564F": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=None,
            description="No se exige volumen de negocio: se acredita mediante póliza de seguro de "
            "responsabilidad civil con capital mínimo garantizado de 100.000 €, vigente "
            "durante toda la ejecución del contrato.",
            citation=Citation(
                clause="20ª",
                page=14,
                quote="el\nlicitador aportará copia de póliza de seguro de responsabilidad civil, "
                "por un capital\nmínimo garantizado de 100.000 €",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=None,
            description="Al menos tres servicios similares ejecutados en los últimos tres años, "
            "para entidades de tamaño y complejidad comparable, sin umbral económico "
            "explícito.",
            citation=Citation(
                clause="20ª",
                page=14,
                quote="licitadores deberán acreditar la realización de, al\nmenos, tres (3) "
                "servicios de características similares al objeto del presente\ncontrato, "
                "ejecutados en los últimos tres (3) años",
            ),
        ),
        certifications=[],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(
                    name="Criterios de juicio de valor (mejoras)", points=40, is_price=False
                ),
                AwardCriterion(name="Oferta económica", points=60, is_price=True),
            ],
            citation=Citation(
                clause="22ª",
                page=19,
                quote="La puntuación máxima que la Mesa puede otorgar y que cada una de las "
                "ofertas\npresentadas puede obtener es de 100 puntos",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Sin garantía provisional. Garantía definitiva del 5% del precio de "
            "adjudicación anual, por cada año de duración del contrato. Plazo de "
            "garantía de 6 meses tras la vigencia.",
            citation=Citation(
                clause="16ª",
                page=7,
                quote="una fianza definitiva por importe equivalente al 5 por 100 del\nprecio de "
                "adjudicación anual, por los años de duración del contrato",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="Duración de tres años desde la formalización; implantación del "
            "servicio en un plazo máximo de tres meses.",
            extensions_allowed=True,
            extensions_description="Prorrogable hasta dos años más.",
            citation=Citation(
                clause="9ª",
                page=5,
                quote="La duración del presente contrato será de TRES AÑOS, contados desde la "
                "fecha de\nformalización del mismo",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se fija una fecha explícita en el PCAP; remite al plazo señalado en el "
            "anuncio de licitación de la Plataforma de Contratación del Sector Público.",
            citation=Citation(
                clause="21.2",
                page=15,
                quote="Las proposiciones junto con la documentación preceptiva se presentarán, "
                "dentro del plazo\nseñalado en el anuncio de licitación",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida conforme al art. 215 LCSP. Debe comunicarse por escrito al "
            "Ayuntamiento tras la adjudicación, identificando subcontratista, precio y "
            "aptitud técnica. Penalidad del 20% del importe subcontratado en caso de "
            "incumplimiento.",
            citation=Citation(
                clause="29ª",
                page=23,
                quote="En caso de que el contratista decida\nsubcontratar con un tercero la "
                "realización parcial de la prestación, lo deberá comunicar por\nescrito al "
                "Ayuntamiento",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No procede división en lotes: el servicio de hosting y el "
            "suministro/mantenimiento de licencias forman una unidad funcional "
            "inseparable.",
            citation=Citation(
                clause="1.3",
                page=1,
                quote="el objeto del contrato no se divide en lotes\nmotivado por el hecho de que "
                "dada la naturaleza del contrato, el servicio contratado se\ncompone de dos "
                "prestaciones principales e inseparables",
            ),
        ),
    ),
    # Ayuntamiento de San Andrés del Rabanedo (León) -- mantenimiento AYTOS/BL
    # España Software. Procedimiento negociado sin publicidad por exclusividad de
    # proveedor: precio como único criterio, subcontratación expresamente
    # PROHIBIDA (el único de los cuatro), y el plazo de presentación remite al
    # escrito de invitación en vez de a un anuncio público.
    "69/2026": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=76600.00,
            description="Volumen de negocios mínimo anual de 76.600,00 €, IVA no incluido, en "
            "cualquiera de los tres últimos ejercicios contables.",
            citation=Citation(
                clause="6",
                page=5,
                quote="Se deberá acreditar un volumen de negocios mínimo anual igual o superior a "
                "76.600,00 euros, IVA no incluido",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=None,
            description="Relación de principales servicios similares en los últimos tres años; "
            "correspondencia por coincidencia de los tres primeros dígitos del código "
            "CPV, sin umbral económico explícito.",
            citation=Citation(
                clause="6",
                page=5,
                quote="tomando como criterio de correspondencia entre los servicios ejecutados por "
                "el licitador\ny los que constituyen el objeto del contrato, la coincidencia "
                "con los tres primeros dígitos del/de los código/s\nCPV del contrato",
            ),
        ),
        certifications=[],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[AwardCriterion(name="Precio", points=100, is_price=True)],
            citation=Citation(
                clause="9",
                page=7,
                quote="Se establece como único criterio de adjudicación el precio",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Sin garantía provisional. Garantía definitiva del 5% del importe de "
            "adjudicación, IVA no incluido; no se admite constitución mediante "
            "retención en el precio.",
            citation=Citation(
                clause="13",
                page=8,
                quote="GARANTÍA DEFINITIVA\nProcede: Si\nImporte: 5 % del importe de adjudicación "
                "del contrato, IVA no incluido",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="Cuatro meses desde el 30 de agosto de 2026 o el día siguiente a la "
            "formalización; el contrato se extingue en todo caso el 30 de diciembre de "
            "2026.",
            extensions_allowed=False,
            extensions_description=None,
            citation=Citation(
                clause="17",
                page=9,
                quote="El plazo de ejecución del contrato será de CUATRO MESES, desde el día 30 de "
                "agosto de 2026 o día siguiente\na la formalización del contrato",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se fija una fecha explícita en el PCAP: al ser procedimiento negociado "
            "sin publicidad, remite a la forma, plazo y lugar indicados en el escrito "
            "de invitación (no a un anuncio público).",
            citation=Citation(
                clause="10",
                page=14,
                quote="La proposición se presentará en la forma, plazo y lugar indicados en el "
                "escrito de invitación",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=False,
            description="No permitida: el contrato debe ser ejecutado directamente por el "
            "adjudicatario dada la naturaleza y condiciones de la prestación.",
            citation=Citation(
                clause="30",
                page=26,
                quote="El adjudicatario del contrato no podrá subcontratar con terceros la "
                "realización parcial del mismo",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes: el servicio únicamente puede ejecutarlo la empresa "
            "propietaria del software (BL España Software / AYTOS), que ostenta "
            "derechos de exclusividad sobre su mantenimiento.",
            citation=Citation(clause="1", page=3, quote="– División en lotes: NO"),
        ),
    ),
    # Ajuntament de Picanya -- alojamiento/mantenimiento de servidores, procedimiento
    # negociado sin publicidad por exclusividad técnica. Narrative, 32 páginas. Único
    # de los nueve con exención EXPLÍCITA de solvencia económica y técnica (art. 11
    # RGLCAP), y el más rico en certificaciones formales exigidas (ENS + seis ISO).
    "2545974A": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=None,
            description="Los licitadores están exentos de acreditar la solvencia económica y "
            "financiera, por aplicación del artículo 11 del Reglamento general de la LCAP.",
            citation=Citation(
                clause="10.2",
                page=8,
                quote="los licitadores están exentos de acreditar la solvencia\neconómica y "
                "financiera y técnica o profesional",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=None,
            description="Los licitadores están exentos de acreditar la solvencia técnica o "
            "profesional, por la misma exención que la solvencia económica.",
            citation=Citation(
                clause="10.2",
                page=8,
                quote="los licitadores están exentos de acreditar la solvencia\neconómica y "
                "financiera y técnica o profesional",
            ),
        ),
        certifications=[
            RequiredCertification(
                name="Certificado cumplimiento del ENS en categoría ALTA",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=Citation(
                    clause="10.1.l)",
                    page=7,
                    quote="Certificado cumplimiento del ENS en categoría ALTA del licitador.",
                ),
            ),
            RequiredCertification(
                name="Certificado ISO 20000",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=None,
            ),
            RequiredCertification(
                name="Certificado ISO 27001",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=None,
            ),
            RequiredCertification(
                name="Certificado ISO 27017",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=None,
            ),
            RequiredCertification(
                name="Certificado ISO 27018",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=None,
            ),
            RequiredCertification(
                name="Certificado ISO 22301",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=None,
            ),
            RequiredCertification(
                name="Certificación ISO 50001",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=None,
            ),
        ],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Precio", points=80, is_price=True),
                AwardCriterion(
                    name="Precio por usuario adicional a los inicialmente previstos",
                    points=20,
                    is_price=True,
                ),
            ],
            citation=Citation(
                clause="9.1",
                page=6,
                quote="Precio (80 puntos)\nEste criterio se establece para la eficiente "
                "utilización de los fondos públicos.",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Sin garantía provisional. Garantía definitiva del 5% del importe de "
            "adjudicación, IVA excluido.",
            citation=Citation(
                clause="11",
                page=8,
                quote="la constitución de la garantía definitiva por importe del 5 por 100 "
                "del\nimporte de adjudicación del contrato, excluido el Impuesto sobre el "
                "Valor Añadido",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="Vigencia de un año desde la firma del contrato.",
            extensions_allowed=True,
            extensions_description="Prorrogable por un año más por acuerdo del órgano de "
            "contratación.",
            citation=Citation(
                clause="8",
                page=5,
                quote="el contrato tendrá una vigencia de un año, prorrogable por UN año "
                "más, por\nacuerdo del órgano de contratación con una antelación mínima de "
                "dos meses",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se fija una fecha explícita: al ser procedimiento negociado sin "
            "publicidad, la adjudicación se negocia directamente con el contratista "
            "exclusivo, sin anuncio público.",
            citation=Citation(
                clause="9",
                page=5,
                quote="se adjudicará mediante\nprocedimiento negociado sin publicidad, de "
                "conformidad con lo establecido en los\nartículos 168 y ss. de la LCSP",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=False,
            description="No se admite la subcontratación: las prestaciones deben ser "
            "ejecutadas directamente por el contratista.",
            citation=Citation(
                clause="22",
                page=15,
                quote="No se admitirá la subcontratación, por lo que las prestaciones que "
                "constituyen el objeto\ndel presente contrato deberán ser ejecutadas "
                "directamente por la persona o entidad del\ncontratista.",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No procede división en lotes: las prestaciones constituyen una "
            "unidad operativa o funcional inseparable, por aplicación de la excepción "
            "del art. 99.3 LCSP.",
            citation=Citation(
                clause="4",
                page=4,
                quote="No se prevé la división en lotes del objeto del contrato en "
                "aplicación de la excepción\nprevista en el artículo 99.3 de la LCSP.",
            ),
        ),
    ),
    # Aragonesa de Servicios Telemáticos (AST) -- desarrollo de app de gestión de bolsa
    # de empleo. Formato "Cuadro de Características" con anexos numerados, 54 páginas.
    # Solvencia técnica sin umbral económico (proyectos cualitativos, no un importe);
    # criterios de adjudicación con un desglose inusualmente granular (9 líneas).
    "AST-2026-20162": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=121000.00,
            description="Volumen anual de negocios referido al mejor de los tres últimos "
            "ejercicios, igual o superior a 121.000,00 €.",
            citation=Citation(
                clause="ANEXO III.1.a)",
                page=22,
                quote="Los licitadores deberán acreditar un volumen anual de negocios "
                "referido al mejor ejercicio\ndentro de los tres últimos concluidos por "
                "importe igual o superior a 121.000,00 €.",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=None,
            description="Participación en al menos dos proyectos de desarrollo de sistemas "
            "de información de similares características tecnológicas en los últimos "
            "tres años, sin umbral económico explícito.",
            citation=Citation(
                clause="ANEXO III.1.a)",
                page=23,
                quote="Los licitadores deberán acreditar haber participado en los últimos "
                "tres años en al menos DOS\nproyectos de desarrollo de sistemas de "
                "información de similares características tecnológicas a\nlas del objeto "
                "de la presente licitación",
            ),
        ),
        certifications=[],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Oferta económica", points=18, is_price=True),
                AwardCriterion(name="Calidad de la solución propuesta", points=31, is_price=False),
                AwardCriterion(name="Calidad del equipo de trabajo", points=10, is_price=False),
                AwardCriterion(
                    name="Organización y planificación de los trabajos", points=8, is_price=False
                ),
                AwardCriterion(
                    name="Criterios técnicos de valoración automática adicionales "
                    "(capacitación del equipo, bolsa de horas, garantía adicional)",
                    points=33,
                    is_price=False,
                ),
            ],
            citation=Citation(
                clause="ANEXO VI.I",
                page=35,
                quote="Los criterios evaluables mediante juicio de valor suponen 49 puntos "
                "de los 100 puntos máximos de\nadjudicación.",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="El Cuadro de Características no contempla una garantía provisional "
            "distinta de la definitiva. Garantía definitiva del 5% del importe de "
            "adjudicación, IVA excluido.",
            citation=Citation(
                clause="K",
                page=3,
                quote="5 % del importe de adjudicación IVA excluido COMPLEMENTARIA",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="Desde el día siguiente de la firma del contrato hasta el 30 de diciembre "
            "de 2026.",
            extensions_allowed=True,
            extensions_description="Posible prórroga, con un preaviso general de dos meses.",
            citation=Citation(
                clause="H",
                page=2,
                quote="Duración del contrato: Desde el día siguiente de la firma del "
                "contrato hasta el 30 de diciembre de 2026.",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se fija una fecha límite explícita en el PCAP: la presentación "
            "se realiza electrónicamente a través del Gestor de Licitaciones (GLIC) del "
            "Gobierno de Aragón, según lo publicado en el anuncio de licitación.",
            citation=Citation(
                clause="2.6.1",
                page=8,
                quote="Para la presentación de proposiciones, el acceso a GLIC se realizará "
                "a través de la siguiente dirección\nelectrónica (URL): "
                "https://contratacionpublica.aragon.es/licitaciones/portal_licitador/login, "
                "mediante\ncertificado electrónico.",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida (Anexo VII), sin restricciones específicas rellenadas en "
            "el cuadro más allá del régimen general de la LCSP.",
            citation=Citation(
                clause="N",
                page=3,
                quote="N. SUBCONTRATACIÓN Y CESIÓN\nSI, ver Anexo VII NO",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No aplica división en lotes.",
            citation=Citation(
                clause="ANEXO I", page=20, quote="LIMITACIONES A LOS LOTES\nNo aplica"
            ),
        ),
    ),
    # Urbanizadora Municipal, S.A. (URBAMUSA) -- mantenimiento de aplicación. Narrativo,
    # 76 páginas, contrato de naturaleza privada (poder adjudicador no Administración
    # Pública). Solvencia económica y técnica expresadas como FÓRMULA (1,5x/70% del
    # valor anual medio del contrato) que el propio pliego no pre-calcula -- el modelo
    # tiene que hacer la cuenta, no solo copiar una cifra ya escrita.
    "23/2026": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=57588.44,
            description="Volumen anual de negocios de al menos una vez y media el valor "
            "anual medio del contrato (191.961,45 € / 5 anualidades = 38.392,29 €; "
            "x1,5 = 57.588,44 €). El pliego da la fórmula, no la cifra final ya "
            "calculada.",
            citation=Citation(
                clause="18.2",
                page=22,
                quote="cuando el\nvolumen anual de negocios del licitador alcance, al "
                "menos, una vez y media el\nvalor anual medio del contrato, IVA excluido",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=26874.60,
            description="Importe acumulado de servicios similares de al menos el 70% del "
            "valor anual medio del contrato (70% de 38.392,29 € = 26.874,60 €), "
            "ejecutados en los últimos cinco años.",
            citation=Citation(
                clause="19.3",
                page=24,
                quote="El importe acumulado de los servicios o trabajos acreditados "
                "alcance,\ncomo mínimo, el setenta por ciento (70 %) del valor anual "
                "medio\nestimado del presente contrato, IVA excluido.",
            ),
        ),
        certifications=[],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Oferta económica", points=30, is_price=True),
                AwardCriterion(
                    name="Experiencia específica de los medios personales adscritos a la "
                    "ejecución del contrato",
                    points=35,
                    is_price=False,
                ),
                AwardCriterion(
                    name="Propuesta técnica de prestación del servicio",
                    points=35,
                    is_price=False,
                ),
            ],
            citation=Citation(
                clause="23.1",
                page=27,
                quote="23.1 Criterios evaluables mediante la aplicación de fórmulas (65 puntos)",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Sin garantía provisional. Garantía definitiva del 5% del precio "
            "final ofertado, IVA excluido.",
            citation=Citation(
                clause="26",
                page=40,
                quote="hubiera presentado la mejor oferta deberá constituir una garantía "
                "definitiva\npor importe equivalente al cinco por ciento (5 %) del precio "
                "final ofertado,\nexcluido el Impuesto sobre el Valor Añadido (IVA)",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="Duración inicial de un año desde la formalización del contrato "
            "(o la fecha que se determine en el documento de formalización).",
            extensions_allowed=None,
            extensions_description=None,
            citation=Citation(
                clause="5",
                page=10,
                quote="el contrato tendrá una duración\ninicial de un (1) año, contado "
                "desde la fecha de su formalización o desde la\nfecha que expresamente se "
                "determine en el documento de formalización.",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se fija una fecha explícita en el PCAP; remite al plazo "
            "señalado en el anuncio de licitación de la Plataforma de Contratación del "
            "Sector Público.",
            citation=Citation(
                clause="14",
                page=15,
                quote="Las proposiciones se presentarán exclusivamente por medios "
                "electrónicos a\ntravés de la Plataforma de Contratación del Sector "
                "Público, dentro del plazo\nseñalado en el anuncio de licitación",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida conforme a los artículos 215 a 217 LCSP, salvo para "
            "prestaciones configuradas como obligaciones personales del adjudicatario o "
            "determinantes para la solvencia técnica acreditada.",
            citation=Citation(
                clause="29",
                page=42,
                quote="La subcontratación de las prestaciones objeto del contrato se "
                "regirá por lo\ndispuesto en los artículos 215 a 217 de la Ley 9/2017, de "
                "8 de noviembre, de\nContratos del Sector Público.",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No procede división en lotes: las prestaciones recaen sobre una "
            "única aplicación informática y constituyen un servicio técnica y "
            "funcionalmente interdependiente.",
            citation=Citation(
                clause="1.6", page=7, quote="no procede la división del contrato en lotes."
            ),
        ),
    ),
    # Junta de Contratación del Ministerio de Inclusión, Seguridad Social y Migraciones
    # -- consultoría en protección de datos. Formato "Cuadro de Características" con
    # checkboxes ☒/☐, 89 páginas. Sin certificaciones ni habilitación empresarial
    # exigida; criterios de adjudicación con cinco líneas explícitas, no agrupadas.
    "202601JC0007": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=27702.02,
            description="Volumen anual de negocios referido al mejor de los tres últimos "
            "ejercicios, mínimo 27.702,02 €.",
            citation=Citation(
                clause="15",
                page=10,
                quote="disponibles por importe mínimo de 27.702,02 €.",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=12927.60,
            description="Relación de principales servicios similares en los últimos 3 años, "
            "importe anual acumulado en el año de mayor ejecución igual o superior a "
            "12.927,60 € (IVA no incluido).",
            citation=Citation(
                clause="15",
                page=10,
                quote="Requisitos: El importe anual acumulado en el año de mayor ejecución "
                "–dentro\ndel citado periodo de tres años- será igual o superior a "
                "12.927,60 € (IVA no\nincluido).",
            ),
        ),
        certifications=[],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Oferta económica", points=48, is_price=True),
                AwardCriterion(
                    name="Realización de auditoría presencial adicional",
                    points=18,
                    is_price=False,
                ),
                AwardCriterion(
                    name="Ampliación del horario de servicio", points=18, is_price=False
                ),
                AwardCriterion(
                    name="Reducción del tiempo de resolución de consultas",
                    points=14,
                    is_price=False,
                ),
                AwardCriterion(
                    name="Adscripción como Abogado de una persona certificada por la AEPD "
                    "como Delegado de Protección de Datos",
                    points=2,
                    is_price=False,
                ),
            ],
            citation=Citation(
                clause="17",
                page=11,
                quote="1. Oferta económica. Máximo 48 puntos (N)",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Sin garantía provisional. Garantía definitiva del 5% del precio "
            "final ofertado, impuestos indirectos excluidos. Sin garantía "
            "complementaria.",
            citation=Citation(
                clause="12",
                page=8,
                quote="El 5% del precio final ofertado (art. 107.1 de la LCSP), impuestos "
                "indirectos\nexcluidos",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="12 meses desde el 1 de enero de 2027 o desde la formalización si fuera "
            "posterior.",
            extensions_allowed=True,
            extensions_description="Prórroga prevista hasta un máximo de 36 meses en total, "
            "renovada anualmente.",
            citation=Citation(
                clause="22",
                page=14,
                quote="El plazo de ejecución del contrato será de 12 meses",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se fija una fecha explícita en el PCAP; remite al plazo "
            "señalado en el anuncio de licitación de la Plataforma de Contratación del "
            "Sector Público.",
            citation=Citation(
                clause="14",
                page=9,
                quote="antes de que finalice el plazo de presentación de ofertas "
                "recogido\nen el anuncio de licitación.",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida (art. 215 LCSP); ninguna tarea queda excluida de la "
            "subcontratación.",
            citation=Citation(
                clause="26",
                page=17,
                quote="Los licitadores deberán indicar la parte del contrato que tengan "
                "previsto\nsubcontratar, mediante suscripción de la declaración a que se "
                "refiere el Anexo\nVIII",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes: la división conllevaría riesgo de "
            "restringir la competencia y dificultaría la correcta ejecución técnica del "
            "contrato.",
            citation=Citation(
                clause="8",
                page=4,
                quote="La división en lotes conlleva el riesgo de restringir "
                "injustificadamente la\ncompetencia (artículo 99.3.a) de la LCSP).",
            ),
        ),
    ),
    # Área de Gobierno de Políticas Sociales, Familia e Igualdad (Ayuntamiento de
    # Madrid) -- mantenimiento de la app "Dignitas" (servicio "Madrid en Calle").
    # Narrativo con Anexo I de características al final, 93 páginas. Solvencia
    # económica y técnica comparten el mismo umbral (15.000 €) -- caso deliberado
    # para comprobar que el modelo no confunde ambos campos ni duplica por descuido.
    "300/2026/01246": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=15000.00,
            description="Volumen anual de negocios de al menos 15.000 € en el mejor de los "
            "últimos tres ejercicios disponibles (2023-2025).",
            citation=Citation(
                clause="11",
                page=59,
                quote="que deberá ser igual o superior a\n15.000€.",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=15000.00,
            description="Servicios similares realizados en al menos uno de los tres "
            "últimos ejercicios (2023-2025) por importe igual o superior a 15.000 €.",
            citation=Citation(
                clause="11",
                page=60,
                quote="por lo menos en uno de los tres ejercicios citados, servicios por "
                "un\nimporte igual o superior a 15.000€.",
            ),
        ),
        certifications=[],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Oferta económica", points=70, is_price=True),
                AwardCriterion(name="Mejoras técnicas", points=10, is_price=False),
                AwardCriterion(
                    name="Otros criterios relacionados con la calidad de la prestación",
                    points=20,
                    is_price=False,
                ),
            ],
            citation=Citation(
                clause="19",
                page=62,
                quote="A) CRITERIOS VALORABLES EN CIFRAS O PORCENTAJES: HASTA 30 PUNTOS\n"
                "(MÁXIMO 30%).",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Sin garantía provisional. Garantía definitiva del 5% del precio "
            "final ofertado, IVA excluido. Garantía complementaria del 1% para ofertas "
            "inicialmente incursas en presunción de anormalidad.",
            citation=Citation(
                clause="15",
                page=62,
                quote="Su cuantía será igual al 5 por 100 del importe del precio final "
                "ofertado por el\nlicitador, excluido el Impuesto sobre el Valor Añadido.",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="24 meses desde el 1 de diciembre de 2026 (o desde la formalización si "
            "fuera posterior).",
            extensions_allowed=True,
            extensions_description="Prorrogable hasta 24 meses más.",
            citation=Citation(
                clause="8",
                page=58,
                quote="Plazo total: 24 meses.\nFecha prevista de Inicio: 01 de diciembre "
                "de 2026, o desde la formalización del",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se fija una fecha explícita en el PCAP; remite a la forma, "
            "plazo y lugar indicados en el anuncio de licitación.",
            citation=Citation(
                clause="23",
                page=16,
                quote="Las proposiciones se presentarán en la forma, plazo y lugar "
                "indicados en el anuncio de\nlicitación, sin que se admitan aquellas "
                "proposiciones que no se presenten en la forma, plazos y lugar indicado.",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida. Los licitadores deben indicar en la oferta la parte "
            "del contrato a subcontratar, su importe y el perfil del subcontratista. Sin "
            "pago directo a subcontratistas.",
            citation=Citation(
                clause="26",
                page=70,
                quote="26.- Subcontratación.\nSÍ procede subcontratación.",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes: la naturaleza del servicio exige una "
            "ejecución conjunta, global y coordinada; dividirlo en lotes arriesgaría la "
            "correcta ejecución del contrato.",
            citation=Citation(
                clause="1.4",
                page=52,
                quote="la división en lotes podría generar un riesgo de perjudicar con "
                "severa gravedad la ejecución adecuada del contrato.",
            ),
        ),
    ),
    # Isdefe, para la Inspección General del Ejército (IGE) -- evolución y mejora del
    # sistema informático de gestión de la alimentación. Narrativo, 97 páginas.
    "2026-01027": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=112800.00,
            description="Volumen anual de negocios referido al mejor de los tres últimos "
            "ejercicios, igual o superior a 112.800,00 € (IVA excluido).",
            citation=Citation(
                clause="5.1",
                page=10,
                quote="por importe igual o\nsuperior a: 112.800,00 euros IVA excluido.",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=13200.00,
            description="Al menos dos contratos de servicios análogos en los últimos tres "
            "años, cada uno por un importe de al menos 13.200 € (umbral por contrato, "
            "no acumulado).",
            citation=Citation(
                clause="5.2",
                page=11,
                quote="Al menos DOS (2) contratos de servicios de apoyo técnico ( servicios "
                "de evolución y mejora\ndel sistema informático) por un importe total cada "
                "uno de ellos de al menos 13.200 euros.",
            ),
        ),
        certifications=[],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(
                    name="Experiencia en diseño e implementación ASP.NET/Visual Studio",
                    points=40,
                    is_price=False,
                ),
                AwardCriterion(
                    name="Experiencia en bases de datos Microsoft SQL Server",
                    points=20,
                    is_price=False,
                ),
                AwardCriterion(name="Criterios económicos", points=40, is_price=True),
            ],
            citation=Citation(
                clause="6.2",
                page=17,
                quote="El contrato se adjudicará conforme a los siguientes criterios:\n"
                "6.2.1. CRITERIOS AUTOMÁTICOS DISTINTOS DEL PRECIO",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Sin garantía provisional. Garantía definitiva del 5% del precio del "
            "contrato, IVA excluido; retención adicional del 10% si la oferta estuvo "
            "incursa en presunción de anormalidad.",
            citation=Citation(
                clause="11.2",
                page=41,
                quote="la garantía definitiva correspondiente al CINCO\nPOR CIENTO (5%) del "
                "precio del contrato, excluido el Impuesto sobre el Valor Añadido",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="Duración inicial de 3 meses.",
            extensions_allowed=True,
            extensions_description="Dos posibles prórrogas de 12 meses cada una, hasta 27 meses en "
            "total.",
            citation=Citation(
                clause="2.1",
                page=7,
                quote="Duración Inicial 1 3 MESES 400 h 18.800,00 €",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se fija una fecha explícita en el PCAP; remite al plazo señalado "
            "en el anuncio de licitación de la Plataforma de Contratación del Sector "
            "Público.",
            citation=Citation(
                clause="10",
                page=40,
                quote="Las proposiciones, junto con la documentación preceptiva prevista en "
                "el presente Pliego se presentarán,\ndentro del plazo señalado en el anuncio",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida conforme al art. 215 LCSP, salvo para las tareas críticas "
            "que deben ejecutarse directamente por el contratista.",
            citation=Citation(
                clause="17",
                page=44,
                quote="El contratista podrá concertar con terceros la realización parcial de "
                "la prestación en los términos previstos\nen el artículo 215 de la LCSP.",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes: la coordinación entre distintos contratistas "
            "podría socavar la correcta ejecución del contrato.",
            citation=Citation(
                clause="4",
                page=6,
                quote="Isdefe no ha dividido el presente contrato en lotes debido a que la "
                "citada división haría que la\ncoordinación de los diferentes contratistas "
                "pueda conllevar el riesgo de socavar la adecuada eje-\ncución del contrato.",
            ),
        ),
    ),
    # ACOSOL (Aguas y Saneamientos, Costa del Sol) -- adquisición, implantación,
    # mantenimiento y soporte de plataforma de comunicaciones y software de
    # transferencia segura. Narrativo, 79 páginas, publicado vía plataforma de firma
    # electrónica sedipualba (huella de firma en el pie de página, cuerpo intacto).
    "69-26": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=60000.00,
            description="Volumen anual de negocios de al menos una vez y media el valor "
            "estimado del contrato (40.000 € x 1,5 = 60.000 €). El pliego da la fórmula, no "
            "la cifra final ya calculada.",
            citation=Citation(
                clause="4.B",
                page=48,
                quote="de la persona licitadora y de presentación de ofertas por importe "
                "mínimo una vez y media el valor\nestimado del contrato.",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=None,
            description="Al menos tres certificados que acrediten la participación en "
            "proyectos iguales o similares, sin umbral económico explícito.",
            citation=Citation(
                clause="4.C",
                page=49,
                quote="al menos TRES (3.-) CERTIFICADOS que\nacrediten la participación en "
                "proyectos de construcción iguales o similares vinculados al\nobjeto "
                "principal del contrato",
            ),
        ),
        certifications=[
            RequiredCertification(
                name="Esquema Nacional de Seguridad (ENS)",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=Citation(
                    clause="4.A.2",
                    page=48,
                    quote="El ENS actúa como condición mínima de acceso y ejecución.",
                ),
            ),
        ],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Implantación", points=17, is_price=False),
                AwardCriterion(name="Plan de Mantenimiento y Soporte", points=15, is_price=False),
                AwardCriterion(name="Plan de Formación", points=3, is_price=False),
                AwardCriterion(name="Proposición económica", points=65, is_price=True),
            ],
            citation=Citation(
                clause="8.A",
                page=52,
                quote="CRITERIOS DE ADJUDICACIÓN PONDERABLES EN FUNCIÓN DE UN JUICIO\nDE "
                "VALOR. Hasta 35 puntos:",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Sin garantía provisional. Garantía definitiva del 5% del precio "
            "final ofertado, IVA excluido.",
            citation=Citation(
                clause="7",
                page=50,
                quote="Garantía Provisional: No\nGarantía definitiva: Sí. En caso "
                "afirmativo: 5 % del precio final ofertado (excluido el IVA)",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="36 meses de mantenimiento desde la implantación, más 2 meses para la "
            "implantación.",
            extensions_allowed=False,
            extensions_description=None,
            citation=Citation(
                clause="3",
                page=47,
                quote="36 meses el mantenimiento, desde la implantación\n- 2 meses para la "
                "implantacion",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se fija una fecha explícita en el PCAP; remite al anuncio del "
            "expediente.",
            citation=Citation(
                clause="6",
                page=50,
                quote="Plazo de publicación: indicada en el anuncio del expediente",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida, salvo determinadas partes o trabajos que deben ser "
            "ejecutados directamente por el contratista.",
            citation=Citation(
                clause="10",
                page=53,
                quote="Determinadas partes o trabajos deberán ser ejecutadas directamente "
                "por la persona\ncontratista o, en el caso de una oferta presentada por una "
                "unión de empresarios, por un",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes: razones de unidad funcional, coherencia "
            "técnica, coordinación documental y responsabilidad única.",
            citation=Citation(
                clause="1",
                page=46,
                quote="Se considera técnicamente justificada la no división en lotes del "
                "presente contrato, al concurrir\nrazones de unidad funcional, coherencia "
                "técnica, coordinación documental y necesidad de\nresponsabilidad única en "
                "la prestación.",
            ),
        ),
    ),
    # Ayuntamiento de Gilet (Valencia) -- solución tecnológica integral para la
    # prevención, monitorización y gestión del riesgo de incendio. Narrativo, 53
    # páginas, procedimiento abierto simplificado abreviado de bajo valor: único de
    # este lote sin ninguna exigencia de solvencia ni garantía en absoluto.
    "CMA 04/2026": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=None,
            description="No se exige acreditación de solvencia económica y financiera: "
            "procedimiento abierto simplificado abreviado (art. 159.6 LCSP), contrato de "
            "bajo valor. La palabra 'solvencia' no aparece en ningún punto del pliego.",
            citation=None,
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=None,
            description="No se exige acreditación de solvencia técnica o profesional, misma "
            "razón que la solvencia económica.",
            citation=None,
        ),
        certifications=[],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Proposición económica", points=25, is_price=True),
                AwardCriterion(
                    name="Criterios técnicos y de calidad de la solución",
                    points=15,
                    is_price=False,
                ),
                AwardCriterion(
                    name="Valoración de la plataforma y del Dashboard", points=15, is_price=False
                ),
                AwardCriterion(
                    name="Participación del fabricante/desarrollador y del equipo técnico "
                    "especializado",
                    points=15,
                    is_price=False,
                ),
                AwardCriterion(
                    name="Condición de empresa desarrolladora, fabricante o responsable "
                    "tecnológico",
                    points=15,
                    is_price=False,
                ),
                AwardCriterion(
                    name="Proyectos con tecnología idéntica, similar o compatible en "
                    "municipios o territorios cercanos",
                    points=15,
                    is_price=False,
                ),
            ],
            citation=Citation(
                clause="7.A",
                page=31,
                quote="7.A. Criterios de adjudicación valorados mediante la aplicación de fórmulas",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=None,
            description="El pliego no exige garantía provisional ni definitiva -- ninguna de "
            "las dos palabras aparece en ningún punto del documento, coherente con un "
            "procedimiento simplificado de bajo valor.",
            citation=None,
        ),
        execution_deadline=ExecutionDeadline(
            description="4 años desde la notificación de la Resolución de Adjudicación; 3 meses "
            "para el suministro y puesta en funcionamiento inicial.",
            extensions_allowed=False,
            extensions_description=None,
            citation=Citation(
                clause="3",
                page=29,
                quote="Plazo total (en meses): 4 años a contar desde la notificación de la "
                "Resolución de Adjudicación del\ncontrato.",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se fija una fecha explícita en el PCAP; remite al plazo señalado "
            "en el anuncio publicado en el perfil de contratante.",
            citation=Citation(
                clause="9.1",
                page=5,
                quote="Las proposiciones, junto con la documentación preceptiva, se "
                "presentarán únicamente por medios\nelectrónicos a través de la plataforma "
                "de contratación del sector público dentro del plazo señalado en\nel anuncio "
                "realizado en el perfil de contratante del órgano de contratación.",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida: no hay partes que deban ejecutarse obligatoriamente de "
            "forma directa por el contratista.",
            citation=Citation(
                clause="9",
                page=35,
                quote="Determinadas partes o trabajos deberán ser ejecutadas directamente "
                "por la\npersona contratista o, en el caso de una oferta presentada por una "
                "unión de\nempresarios, por un participante en la misma: No.",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes: la realización independiente de las "
            "prestaciones dificultaría la coordinación de un sistema único de seguridad.",
            citation=Citation(
                clause="1",
                page=28,
                quote="Se justifica la no división en lotes de este contrato, atendiendo a "
                "lo establecido en el articulo 99.3 de la\nLey de Contratos del Sector "
                "Publico",
            ),
        ),
    ),
    # CETEDEX (Centro Tecnológico de la Defensa, INTA) -- desarrollo de un prototipo de
    # análisis de vulnerabilidades. Narrativo, 53 páginas, organismo vinculado a la
    # seguridad del Estado: subcontratación siempre sujeta a autorización previa.
    "582026020000": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=50000.00,
            description="Volumen anual de negocios de al menos el 50% del valor estimado "
            "del contrato (100.000 € x 0,5 = 50.000 €). El pliego da la fórmula, no la "
            "cifra final ya calculada.",
            citation=Citation(
                clause="12.1.a)",
                page=32,
                quote="El requisito mínimo será que el volumen anual de negocios del "
                "licitador, que referido\nal año de mayor volumen de negocio de los tres "
                "últimos concluidos deberá ser igual\no superior al 50% del valor estimado "
                "del contrato o del/los lote/s al/los que licite.",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=50000.00,
            description="Importe anual acumulado en el año de mayor ejecución de al menos "
            "el 50% de la anualidad media del contrato -- aproximado aquí al 50% del "
            "valor estimado (100.000 €), dado que el contrato no tiene anualidades "
            "distintas (14 meses, sin prórroga).",
            citation=Citation(
                clause="12.2.a)",
                page=33,
                quote="El requisito mínimo será que el importe anual acumulado en el año "
                "de mayor ejecu-\nción sea igual o superior al 50% de la anualidad media "
                "del contrato o del/los lote/s\nal/los que licite.",
            ),
        ),
        certifications=[],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Precio", points=40, is_price=True),
                AwardCriterion(name="Lenguajes adicionales", points=30, is_price=False),
                AwardCriterion(name="Modelo", points=15, is_price=False),
                AwardCriterion(name="Capacidad de detección", points=15, is_price=False),
            ],
            citation=Citation(
                clause="7",
                page=30,
                quote="7.- CRITERIOS DE VALORACIÓN DE LAS OFERTAS.\n- Criterio 1.- Precio: 40%",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Sin garantía provisional. Garantía definitiva del 5% del "
            "presupuesto del contrato, IVA/IGIC excluido; garantía complementaria "
            "adicional del 5%.",
            citation=Citation(
                clause="13",
                page=33,
                quote="13.- GARANTÍAS.\nProvisional: No procede.\nDefinitiva: Sí procede. "
                "5.00% del presupuesto del contrato (IVA/IGIC no incluido).",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="14 meses desde la formalización, con hitos parciales a los 3 meses (40% "
            "del importe) y 14 meses (60% del importe).",
            extensions_allowed=False,
            extensions_description=None,
            citation=Citation(
                clause="14",
                page=33,
                quote="El plazo de ejecución del contrato será de 14 meses o, en su caso, "
                "el que oferte el\ncontratista, si fuese menor que aquel.",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se fija una fecha explícita en el PCAP; remite al plazo "
            "señalado en el anuncio de licitación de la Plataforma de Contratación del "
            "Sector Público.",
            citation=Citation(
                clause="10",
                page=8,
                quote="fecha, en la que concluya el plazo de presentación de ofertas que "
                "figura en el",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida, salvo las tareas críticas para la ejecución del "
            "contrato (documentación de diseño preliminar y final, preparación de datos, "
            "integración de software y modelos, formación), que no pueden subcontratarse. "
            "Requiere siempre autorización por tratarse de un organismo vinculado a la "
            "seguridad del Estado.",
            citation=Citation(
                clause="16",
                page=34,
                quote="Las tareas que no pueden ser objeto de subcontratación por ser "
                "críticas para la\nejecución del contrato son: documentación del diseño "
                "preliminar, preparación de\ndatos y datasets, documentación de diseño "
                "final (modelos), integración del software\ny modelos y, formación.",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes: las ofertas deben cubrir la totalidad del "
            "expediente.",
            citation=Citation(
                clause="6",
                page=30,
                quote="Las ofertas deberán ser hechas por: la totalidad del expediente",
            ),
        ),
    ),
    # Gobierno del Principado de Asturias -- visor web GIS del Registro de Derechos
    # Mineros. Narrativo, 122 páginas: el más largo del conjunto. Único con una fecha
    # de cierre de presentación expresada como hora exacta ("23:59:59").
    "2026000731": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=170280.00,
            description="Volumen anual de negocios de al menos una vez y media el valor "
            "estimado del contrato (170.280,00 €).",
            citation=Citation(
                clause="9.5.1",
                page=28,
                quote="deberá ser igual o superior a una vez y media el valor estimado\ndel "
                "contrato (170.280,00€).",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=79464.00,
            description="Trabajos de igual o similar naturaleza en los últimos 3 años, por "
            "un importe igual o superior al 70% del valor estimado del contrato "
            "(79.464,00 €).",
            citation=Citation(
                clause="9.5.2",
                page=28,
                quote="por un\nimporte igual o superior al 70% del valor estimado del "
                "contrato (79.464,00 €).",
            ),
        ),
        certifications=[],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Oferta Económica", points=41, is_price=True),
                AwardCriterion(name="Mejoras", points=10, is_price=False),
                AwardCriterion(name="Solución técnica", points=49, is_price=False),
            ],
            citation=Citation(
                clause="11.1",
                page=43,
                quote="CRITERIOS DE VALORACIÓN PUNTUACIÓN\nCriterios automáticos 51\nOferta "
                "Económica 41",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Sin garantía provisional. Garantía definitiva del 5% del precio "
            "final ofertado, IVA excluido.",
            citation=Citation(
                clause="12.4.d)",
                page=62,
                quote="El licitador propuesto como adjudicatario deberá acreditar la "
                "constitución a favor del órgano de\ncontratación de una garantía "
                "definitiva de un 5% del precio final ofertado, excluido el Impuesto\nsobre "
                "el Valor Añadido.",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="Periodo de ejecución máxima de 8 meses, con hitos consecutivos "
            "(análisis y diseño, migración y publicación, configuración del visor, etc.).",
            extensions_allowed=False,
            extensions_description=None,
            citation=Citation(
                clause="6.1",
                page=17,
                quote="El contrato tendrá un periodo de ejecución máxima de OCHO (8) MESES, "
                "con los siguientes\nhitos de ejecución consecutivos:",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="Finaliza a las 23:59:59 horas del día señalado en el anuncio de "
            "licitación, no inferior a quince días desde la publicación del anuncio en el "
            "perfil de contratante.",
            citation=Citation(
                clause="8.1",
                page=34,
                quote="El plazo de presentación de proposiciones finalizará a las 23:59:59 "
                "horas del día señalado en el\nanuncio de licitación del contrato, que no "
                "será inferior a quince días contados desde el día\nsiguiente al de la "
                "publicación del anuncio en el perfil de contratante.",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida conforme al art. 215 LCSP, salvo los medios personales "
            "de adscripción a la ejecución del contrato, que no son subcontratables.",
            citation=Citation(
                clause="22.2",
                page=92,
                quote="Se admite la subcontratación de las prestaciones, no siendo "
                "susceptibles de subcontratación los\nmedios personales de adscripción a la "
                "ejecución del presente contrato descritos en la cláusula\n9.5 del pliego.",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes: fuerte interdependencia técnica entre "
            "componentes (geodatabase, servicios, visores, normalización y migración).",
            citation=Citation(
                clause="1.3",
                page=5,
                quote="En este caso, no resulta procedente dividir el contrato en lotes "
                "debido a la fuerte\ninterdependencia entre los componentes técnicos "
                "(geodatabase, servicios, visores,\nnormalización y migración).",
            ),
        ),
    ),
    # Mogán Gestión Municipal, S.L. (GESTIONA) -- servicio integral de gestión del
    # tiempo de trabajo y control horario, en modalidad SaaS. Narrativo, 57 páginas.
    "L26-SERV-06": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=27000.00,
            description="Volumen anual de negocios mínimo de 27.000,00 €, equivalente a una "
            "vez y media el importe correspondiente a una anualidad del contrato.",
            citation=Citation(
                clause="4.3.1",
                page=5,
                quote="El volumen anual de negocios mínimo exigido será de VEINTISIETE MIL "
                "EUROS (27.000,00 €),\nequivalente a una vez y media el importe "
                "correspondiente a una anualidad del contrato, IVA/IGIC\nexcluido.",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=12600.00,
            description="Importe anual acumulado de servicios similares en el año de mayor "
            "ejecución de al menos 12.600,00 € (70% de la anualidad media del contrato).",
            citation=Citation(
                clause="4.3.2",
                page=6,
                quote="El requisito mínimo será que el importe anual acumulado de los "
                "servicios de igual o similar naturaleza\nejecutados durante el año de "
                "mayor ejecución de los tres últimos años sea igual o superior a DOCE "
                "MIL\nSEISCIENTOS EUROS (12.600,00 €).",
            ),
        ),
        certifications=[],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Oferta económica", points=35, is_price=True),
                AwardCriterion(
                    name="Mejoras funcionales de la plataforma", points=45, is_price=False
                ),
                AwardCriterion(
                    name="Tres terminales adicionales sin coste", points=10, is_price=False
                ),
                AwardCriterion(
                    name="Reducción del plazo máximo de implantación", points=10, is_price=False
                ),
            ],
            citation=Citation(
                clause="12",
                page=13,
                quote="La puntuación máxima será de CIEN (100) PUNTOS, distribuidos de la "
                "siguiente forma:\nCriterio Puntuación máxima\n1. Oferta económica 35 "
                "puntos",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Sin garantía provisional. Garantía definitiva del 5% del precio "
            "final ofertado.",
            citation=Citation(
                clause="14",
                page=20,
                quote="no se exige la constitución de garantía provisional para participar\n"
                "en la presente licitación.",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="Duración inicial de un año desde la formalización.",
            extensions_allowed=True,
            extensions_description="Prorrogable conforme al art. 29.2 LCSP.",
            citation=Citation(
                clause="10.1",
                page=11,
                quote="El contrato tendrá una duración inicial de UN (1) AÑO, contado "
                "desde el día siguiente al de su\nformalización o desde la fecha que "
                "expresamente se determine en el documento contractual.",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se fija una fecha explícita en el PCAP; remite al plazo "
            "señalado en el anuncio de licitación.",
            citation=Citation(
                clause="13.1",
                page=19,
                quote="Las proposiciones y la documentación complementaria se presentarán "
                "dentro del plazo\nseñalado en el anuncio de licitación y en la forma "
                "indicada en los apartados siguientes.",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida conforme a los artículos 215 y siguientes LCSP, sin "
            "alterar la responsabilidad exclusiva de la empresa contratista.",
            citation=Citation(
                clause="29",
                page=42,
                quote="La empresa contratista podrá concertar con terceros la realización "
                "parcial de las prestaciones\nobjeto del contrato, de conformidad con lo "
                "previsto en los artículos 215 y siguientes de la Ley 9/2017,\nde 8 de "
                "noviembre, de Contratos del Sector Público.",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes: unidad funcional que requiere ejecución "
            "coordinada e integrada entre la plataforma SaaS, la app móvil y los "
            "terminales de fichaje.",
            citation=Citation(
                clause="1.2",
                page=2,
                quote="el presente contrato no se divide en lotes,\nal constituir las "
                "prestaciones que\nintegran su objeto una unidad funcional que requiere "
                "una ejecución coordinada e integrada.",
            ),
        ),
    ),
    # Sociedad Estatal Correos y Telégrafos -- plataforma SaaS para gestión de redes
    # sociales integrada con Salesforce Service Cloud. Formato "instrucciones"
    # tabular con checkboxes, 84 páginas. Único criterio de adjudicación: precio.
    "MT260312": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=80683.20,
            description="Volumen anual de negocios en el ámbito del contrato, referido al "
            "mejor de los tres últimos ejercicios, de al menos 80.683,20 €.",
            citation=Citation(
                clause="5",
                page=6,
                quote="Volumen anual de negocios en el ámbito al que se refiere\nel "
                "contrato, referido al mejor ejercicio de los tres últimos, de\nal menos "
                "80.683,20 euros.",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=80683.20,
            description="Haber realizado un servicio de igual o similar naturaleza en los "
            "tres últimos años, cuyo importe anual acumulado en el año de mayor ejecución "
            "sea igual o superior a 80.683,20 €.",
            citation=Citation(
                clause="5",
                page=7,
                quote="Haber realizado un servicio de igual o similar naturaleza\nque los "
                "que constituyen el objeto del contrato en los tres\núltimos años, cuyo "
                "importe anual acumulado en el año de\nmayor ejecución sea igual o "
                "superior a 80.683,20 €.",
            ),
        ),
        certifications=[],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(
                    name="Precio (mejor relación coste-eficacia)", points=100, is_price=True
                ),
            ],
            citation=Citation(
                clause="6.5.1.1",
                page=9,
                quote="Como criterio de adjudicación se considera la mejor relación "
                "coste-eficacia al ser\nempleados únicamente criterios automáticos y no "
                "utilizarse criterios sujetos a juicio de\nvalor.",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Sin garantía provisional. Garantía definitiva del 5% del importe "
            "de adjudicación del contrato, IVA excluido; garantía complementaria "
            "adicional del 5% si la oferta ganadora fue considerada anormalmente baja.",
            citation=Citation(
                clause="7.6",
                page=13,
                quote="5% del importe de",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="Duración inicial de 20 meses desde la fecha del acuerdo de "
            "aceptación, con inicio previsto el 1 de octubre de 2026 y fin el 31 de mayo "
            "de 2028.",
            extensions_allowed=False,
            extensions_description=None,
            citation=Citation(
                clause="3",
                page=5,
                quote="El plazo máximo de ejecución será de 20 meses, a contar desde la "
                "fecha que conste\nen el documento de acuerdo de aceptación, suponiendo su "
                "inicio el 1 de octubre del\n2026 y en todo caso finalizará el 31 de mayo "
                "del 2028, inclusive.",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="30 días naturales a contar desde el día siguiente a la "
            "publicación del anuncio de licitación en el perfil de contratante.",
            citation=Citation(
                clause="6.3",
                page=8,
                quote="Las ofertas se presentarán en plazo de 30 días naturales a contar "
                "desde el día\nsiguiente a aquél en que se publique el anuncio de "
                "licitación en el perfil de contratante.",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida, con obligación de identificar en la oferta la parte a "
            "subcontratar, su importe y el perfil del subcontratista.",
            citation=Citation(
                clause="8.3.2",
                page=21,
                quote="El contratista podrá concertar con terceros la realización parcial "
                "de la prestación bajo\nlas siguientes condiciones:",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes: se mantiene un único sistema de "
            "suscripciones que afecta a producción, preproducción y desarrollo, conforme "
            "al art. 99.3.b) LCSP.",
            citation=Citation(
                clause="Lotes",
                page=4,
                quote="El presente procedimiento de licitación, no se divide en lotes.\nLa "
                "no división en lotes se justifica en el artículo 99.3 b) LCSP,\n“El hecho "
                "de que, la realización independiente de las",
            ),
        ),
    ),
    # Ayuntamiento de Granada -- soporte especializado y mantenimiento de la
    # plataforma de seguridad ZENworks. Formato "Anexo I" con apartados numerados, 74
    # páginas. Solvencia expresada como fórmula sobre el valor anual medio, no como
    # cifra ya calculada.
    "SERV-2026000088": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=7869.98,
            description="Volumen anual de negocios de al menos el valor anual medio del "
            "contrato (15.739,96 € de valor estimado / 2 años de duración = 7.869,98 €). "
            "El pliego da la fórmula, no la cifra final ya calculada.",
            citation=Citation(
                clause="12.B)",
                page=43,
                quote="a) Volumen anual de negocios del licitador, que referido al año de "
                "mayor volumen de negocio\nde los tres últimos concluidos deberá ser al "
                "menos igual al valor anual medio del contrato.",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=5508.99,
            description="Importe acumulado en el año de mayor ejecución de al menos el 70% "
            "del valor medio anual del contrato (70% de 7.869,98 € = 5.508,99 €).",
            citation=Citation(
                clause="12.B)",
                page=43,
                quote="a) Una relación de los principales servicios o trabajos realizados "
                "en los últimos tres años, de igual\no similar naturaleza que los que "
                "constituyen el objeto del contrato, que incluya importe, fechas\ny el "
                "destinatario, público o privado, de los mismos y donde el importe "
                "acumulado en el año de\nmayor ejecución sea igual o superior al 70% del "
                "valor medio anual del contrato que se licita.",
            ),
        ),
        certifications=[
            RequiredCertification(
                name="Esquema Nacional de Seguridad (ENS)",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=Citation(
                    clause="12.A)",
                    page=43,
                    quote="Certificación ENS (Esquema Nacional de Seguridad) nivel medio o alto",
                ),
            ),
        ],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Oferta económica", points=49, is_price=True),
                AwardCriterion(
                    name="Mejoras (horas adicionales de bolsa dinámica y cualificación "
                    "técnica especializada)",
                    points=51,
                    is_price=False,
                ),
            ],
            citation=Citation(
                clause="20",
                page=49,
                quote="Pluralidad de criterios\nCriterios evaluables de forma automática",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Sin garantía provisional. Garantía definitiva del 5% del importe "
            "de adjudicación (tareas fijas anuales) y del 5% del presupuesto de licitación "
            "(bolsa dinámica), IVA excluido en ambos casos.",
            citation=Citation(
                clause="8",
                page=41,
                quote="Tareas fijas anuales: 5 por 100 del importe de adjudicación del "
                "contrato para el periodo de duración\ntotal del mismo (IVA excluido).",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="Duración de dos años desde la formalización del contrato.",
            extensions_allowed=False,
            extensions_description=None,
            citation=Citation(
                clause="4",
                page=40,
                quote="El contrato tendrá una duración de DOS años, a contar desde la "
                "fecha de formalización del\nmismo.",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="Al menos quince días naturales desde la publicación del anuncio "
            "de licitación en el perfil de contratante.",
            citation=Citation(
                clause="28.4",
                page=59,
                quote="El plazo de presentación de proposiciones será como mínimo de "
                "QUINCE días naturales, contados a\npartir del siguiente a aquel en que "
                "aparezca la inserción del anuncio de licitación en el Perfil de\n"
                "Contratante.",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida, con comunicación previa al órgano de contratación "
            "identificando la parte a subcontratar y el subcontratista.",
            citation=Citation(
                clause="18",
                page=46,
                quote="Procede: Sí\nEl contratista deberá comunicar por escrito, tras la "
                "adjudicación del contrato y, a más tardar, cuando\ninicie la ejecución de "
                "este, al órgano de contratación la intención de celebrar los "
                "subcontratos,",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes: el objeto se refiere a un único tipo de "
            "servicios profesionales (soporte especializado en ZENworks) sin posibilidad "
            "de división.",
            citation=Citation(
                clause="1",
                page=38,
                quote="División en lotes: No procede, ya que el objeto de contrato hace "
                "referencia a un mismo tipo de\nservicios profesionales (soporte "
                "especializado en ZENworks) sin posibilidad de división.",
            ),
        ),
    ),
    # Conselleria de Famílies, Benestar Social i Atenció a la Dependència (Illes
    # Balears) -- suport i manteniment de l'aplicació de gestió de pensions no
    # contributives. Formato "Quadre de característiques" en catalán, 96 páginas.
    "CONTR 2026 17947": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=43942.36,
            description="Volumen anual de negocios en el ámbito del contrato de al menos "
            "43.942,36 € (IVA excluido), referido al mejor de los tres últimos ejercicios.",
            citation=Citation(
                clause="F.2",
                page=5,
                quote="Es considerarà que es disposa de solvència econòmica suficient per "
                "executar el\ncontracte quan el volum anual de negocis en l’àmbit a què es "
                "refereix el contracte\nsigui igual o superior a 43.942,36 € (IVA exclòs).",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=43942.36,
            description="Experiencia en servicios de igual naturaleza con un importe anual "
            "acumulado, en el mejor de los tres últimos años, igual o superior al 70% del "
            "presupuesto base de licitación (43.942,36 €).",
            citation=Citation(
                clause="F.3",
                page=6,
                quote="És requisit mínim de solvència tècnica l’experiència en la "
                "prestació de serveis del\nmateix tipus o naturalesa de l’objecte del "
                "contracte per un import anual acumulat,\nen el millor dels últims tres "
                "anys, igual o superior al 70% del pressupost base de\nlicitació (IVA "
                "exclòs), això és, 43.942,36 €.",
            ),
        ),
        certifications=[],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Oferta econòmica", points=45, is_price=True),
                AwardCriterion(
                    name="Compromís de contractació indefinida del personal",
                    points=15,
                    is_price=False,
                ),
                AwardCriterion(name="Qualitat del projecte tècnic", points=40, is_price=False),
            ],
            citation=Citation(
                clause="A",
                page=17,
                quote="Criteri Ponderació\nCriteris avaluables automàticament mitjançant "
                "fórmula (60 punts)\n1. Oferta econòmica 45 punts\n2. Compromís de "
                "contractació indefinida del personal 15 punts",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Garantia provisional no exigida ('Import: No és procedent'). "
            "Garantia definitiva del 5% del pressupost base de licitació, IVA exclòs.",
            citation=Citation(
                clause="H.2",
                page=7,
                quote="H.2. GARANTIA DEFINITIVA: 5% del pressupost base de licitació (IVA exclòs)",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="Duración de 1 año, con inicio previsto el 16 de septiembre de 2026 (o el "
            "día siguiente a la formalización, si fuera posterior).",
            extensions_allowed=True,
            extensions_description="Prorrogable hasta dos años más, en prórrogas sucesivas de un "
            "año.",
            citation=Citation(
                clause="D",
                page=5,
                quote="D. DURADA DEL CONTRACTE. TERMINI D’EXECUCIÓ. PRÒRROGA\nDurada del "
                "contracte. Termini d’execució\nDurada del contracte: 1 any",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="8 días naturales a contar desde el día siguiente a la publicación "
            "del anuncio de licitación en el perfil de contratante.",
            citation=Citation(
                clause="I",
                page=7,
                quote="Data límit: 8 dies naturals a comptar des del dia següent de la "
                "publicació de l’anunci de\nlicitació en el perfil de contractant.",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida, con obligación de declarar en la oferta la parte a "
            "subcontratar y de comunicar la identidad del subcontratista tras la "
            "adjudicación.",
            citation=Citation(
                clause="P",
                page=11,
                quote="S’exigeix la presentació amb l’oferta d’una declaració sobre la "
                "part del contracte\nque el licitador tengui previst subcontractar en els "
                "termes de l’article 215.2.a) de la\nLCSP.",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes: el apartado C del cuadro de características "
            "no describe ningún lote, lo que indica que el contrato se licita como un todo.",
            citation=Citation(
                clause="C",
                page=4,
                quote="C. LOTS (art. 99 LCSP)\nDivisió del contracte en lots",
            ),
        ),
    ),
    # Fundació Turisme Palma 365 (Ajuntament de Palma) -- allotjament web i
    # manteniment integral del portal www.visitpalma.com. Narrativo en catalán, 98
    # páginas, publicado vía plataforma de firma electrónica sedipualba (huella de
    # firma reversa/garbled en el pie de página, cuerpo intacto).
    "INN 26 002": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=13238.55,
            description="Volumen anual de negocios de al menos 1,5 veces el valor anual "
            "medio del contrato (8.825,70 € x 1,5 = 13.238,55 €). El pliego da la "
            "fórmula, no la cifra final ya calculada.",
            citation=Citation(
                clause="F.2",
                page=5,
                quote="Requisit mínim: el volum anual de negocis del licitador, referit a "
                "l’any de major volum de negoci dels 3 últims\nconclosos, ha de ser al "
                "menys 1,5 vegades el valor anual mitjà del contracte.",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=6177.99,
            description="Importe anual acumulado de servicios similares en el año de "
            "mayor ejecución de al menos el 70% de la anualidad media del contrato (70% "
            "de 8.825,70 € = 6.177,99 €).",
            citation=Citation(
                clause="F.3",
                page=6,
                quote="Requisit mínim: l’import anual acumulat dels principals serveis "
                "realitzats, a l’any de major execució dels 3 últims\nexercicis, ha de "
                "ser de al manco del 70% de l’anualitat mitjana sense IVA.",
            ),
        ),
        certifications=[],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Preu de l’oferta", points=40, is_price=True),
                AwardCriterion(
                    name="Proposta tècnica i metodologia de treball", points=20, is_price=False
                ),
                AwardCriterion(
                    name="Metodologia de manteniment (correctiu, evolutiu i preventiu)",
                    points=15,
                    is_price=False,
                ),
                AwardCriterion(
                    name="Pla de seguretat i continuïtat del servei", points=10, is_price=False
                ),
                AwardCriterion(name="Normes de qualitat", points=6, is_price=False),
                AwardCriterion(
                    name="Ampliació de la capacitat de l’allotjament", points=5, is_price=False
                ),
                AwardCriterion(name="Millores funcionals proposades", points=4, is_price=False),
            ],
            citation=Citation(
                clause="A",
                page=15,
                quote="Els criteris que serveixen de base per a l’adjudicació del "
                "contracte, d’acord amb la puntuació següent, són:\nCriteris Puntuació",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Garantia provisional no exigida ('NO ESCAU'). Garantia "
            "definitiva del 5% del importe de adjudicación, IVA excluido.",
            citation=Citation(
                clause="H.2",
                page=7,
                quote="H.2 Garantia definitiva: 5 % de l’import d’adjudicació (IVA exclòs)",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="Duración de 1 año desde la formalización.",
            extensions_allowed=True,
            extensions_description="Prorrogable hasta 4 años adicionales conforme al art. 29.2 "
            "LCSP.",
            citation=Citation(
                clause="C",
                page=5,
                quote="C. DURADA DEL CONTRACTE. TERMINI D’EXECUCIÓ\nDurada del contracte: 1 any",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se fija una fecha explícita en el PCAP; remite a la fecha y "
            "hora indicadas en el anuncio de licitación.",
            citation=Citation(
                clause="I",
                page=8,
                quote="I. PRESENTACIÓ DE PROPOSICIONS. Lloc i forma de presentació "
                "(Clàusula 13.1).\nLicitació electrònica. A la Plataforma de "
                "Contractació del Sector Públic.\nData i hora límit: La indicada a "
                "l'anunci de licitació.",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida para tareas no esenciales que no afecten a las "
            "funciones críticas del mantenimiento, con autorización previa del órgano de "
            "contratación.",
            citation=Citation(
                clause="Q",
                page=9,
                quote="Q. SUBCONTRACTACIÓ. Art. 215 LCSP 9/2017\nEs permet la "
                "subcontractació de determinades prestacions del contracte, sempre que "
                "siguin tasques no essencials\ni que no afectin les funcions crítiques "
                "del manteniment integral del portal www.visitpalma.com.",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes, declarado explícitamente en la portada del pliego.",
            citation=Citation(
                clause="Objecte del contracte",
                page=1,
                quote="Divisió del contracte en lots: : NO",
            ),
        ),
    ),
    # Grupo Tragsa (Tragsatec), para el Ministerio para la Transición Ecológica y el
    # Reto Demográfico -- soporte y mantenimiento del Registro de Aguas electrónico
    # (RAe). Formato "Anexo I" con letras A-P, 79 páginas. Único sin ninguna garantía
    # exigida (ni provisional ni definitiva) y con un valor de tabla desplazado por el
    # layout de dos columnas que, sumado al resto, confirma un total exacto de 100.
    "TEC0007188": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=150000.00,
            description="Cifra anual de negocios referida al mejor de los tres últimos "
            "ejercicios disponibles de al menos 150.000,00 €, impuestos indirectos no "
            "incluidos.",
            citation=Citation(
                clause="E",
                page=44,
                quote="Solvencia que indique una cifra anual de negocios referida al "
                "mejor ejercicio de los últimos tres años disponibles\neconómica y "
                "(2023, 2024 y 2025) en función de las fechas de constitución o de "
                "inicio de actividades del licitador y\nfinanciera de presentación de "
                "las ofertas por importe igual o superior a CIENTO CINCUENTA MIL EUROS\n"
                "(150.000,00 €), Impuestos indirectos no incluidos.",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=79070.00,
            description="Servicios de igual o similar naturaleza (mismo código CPV) en el "
            "año de mayor ejecución de los últimos tres años, por un importe acumulado de "
            "al menos 79.070,00 €, impuestos indirectos no incluidos.",
            citation=Citation(
                clause="E",
                page=44,
                quote="que indique que han realizado servicios de igual o similar "
                "naturaleza que los que constituyen el objeto\nSolvencia\ndel contrato "
                "(relativos al mismo código CPV: 72267000-4 ─ Servicios de "
                "mantenimiento y reparación\nTécnica o\nde software), en el año de "
                "mayor ejecución de los últimos tres (3) años naturales (2023, 2024 y "
                "2025)\nProfesional\npor un importe acumulado igual o superior a "
                "SETENTA Y NUEVE MIL SETENTA EUROS (79.070,00 €),",
            ),
        ),
        certifications=[
            RequiredCertification(
                name="Esquema Nacional de Seguridad (ENS), categoría media o superior",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=Citation(
                    clause="E",
                    page=43,
                    quote="Declaración responsable, firmada electrónicamente por el "
                    "representante legal de la empresa licitante,\nindicando que está en "
                    "posesión y, en caso de resultar seleccionado para participar en este "
                    "acuerdo\nHabilitación\nmarco, aportará: Certificación de Conformidad con "
                    "el Esquema Nacional de Seguridad referida a sus\nempresarial\nsistemas de "
                    "información, incluidos los aportados por terceros, que dan soporte a los "
                    "servicios objeto\ndel contrato, en la Categoría MEDIA o superior, conforme "
                    "al RD 311/2022 de 3 de mayo.",
                ),
            ),
        ],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Precio de la oferta", points=49, is_price=True),
                AwardCriterion(
                    name="Experiencia adicional del jefe de equipo", points=12, is_price=False
                ),
                AwardCriterion(
                    name="Experiencia adicional del analista programador",
                    points=10,
                    is_price=False,
                ),
                AwardCriterion(
                    name="Mejora del período de garantía del software", points=10, is_price=False
                ),
                AwardCriterion(name="Extensión del horario de servicio", points=10, is_price=False),
                AwardCriterion(name="Mejora de entrega de manuales", points=4.5, is_price=False),
                AwardCriterion(name="Mejora de formación", points=4.5, is_price=False),
            ],
            citation=Citation(
                clause="I",
                page=46,
                quote="I. CRITERIOS DE ADJUDICACIÓN\nCriterios evaluables de forma "
                "automática mediante fórmulas:",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=None,
            description="Ni la garantía provisional ('No aplica') ni la definitiva "
            "('Exigible: No') son exigidas en este contrato.",
            citation=Citation(
                clause="F",
                page=45,
                quote="Garantía provisional:\nNo aplica.\nGarantía definitiva:\nExigible: "
                "Sí ☐ No ☒",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="Plazo de ejecución de 5 meses desde la formalización del contrato.",
            extensions_allowed=True,
            extensions_description="Una prórroga de 2 meses, ya prevista en el pliego.",
            citation=Citation(
                clause="K",
                page=49,
                quote="K. PLAZO DE VIGENCIA Y EJECUCIÓN DEL CONTRATO\nPlazo de vigencia "
                "del contrato 5 Meses",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="Fecha máxima de presentación de ofertas: 02/09/2026 a las 14:00.",
            citation=Citation(
                clause="D",
                page=42,
                quote="Fecha máxima de presentación de ofertas:\n02/09/2026 14:00",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida, salvo la interlocución y coordinación con el Grupo "
            "Tragsa, considerada tarea crítica no subcontratable.",
            citation=Citation(
                clause="P",
                page=57,
                quote="Se permite la subcontratación parcial de la prestación objeto del "
                "presente pliego, a excepción de la interlocución y\ncoordinación con el "
                "Grupo Tragsa, por considerarse tarea crítica.",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes: la oferta debe cubrir la totalidad del "
            "objeto del contrato.",
            citation=Citation(
                clause="G",
                page=46,
                quote="G. ÁMBITO DE LA OFERTA\nTotalidad: Sí ☒ No ☐",
            ),
        ),
    ),
    # Empresa Municipal de Aguas y Saneamiento de Murcia (EMUASA) -- servicios de
    # certificación en continuidad de negocio (ISO 22301), auditorías externas de
    # recertificación y seguimiento. Formato "Cuadro de Características" con letras
    # A-S, 82 páginas. La certificación exigida es una acreditación ENAC del propio
    # organismo certificador, no una certificación de calidad interna del licitador.
    "019-SER-2026": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=5850.00,
            description="Volumen anual de negocios de al menos una vez y media el valor "
            "estimado anual del contrato (19.500,00 € / 5 años máximos con prórroga = "
            "3.900,00 €/año; x1,5 = 5.850,00 €). El pliego da la fórmula, no la cifra "
            "final ya calculada.",
            citation=Citation(
                clause="F)",
                page=6,
                quote="Volumen anual de negocios, referido al mejor ejercicio dentro de "
                "los tres últimos\ndisponibles, en función de las fechas de constitución "
                "o de inicio de actividades del\nempresario y de presentación de las "
                "ofertas, por importe igual o superior a una vez y\nmedia el valor "
                "estimado anual del contrato.",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=2730.00,
            description="Trabajos similares en los últimos tres años con importe anual "
            "acumulado en el año de mayor ejecución de al menos el 70% de la anualidad "
            "media del contrato (70% de 3.900,00 € = 2.730,00 €).",
            citation=Citation(
                clause="F)",
                page=6,
                quote="Trabajos efectuados en los tres últimos años, que deberán ser de "
                "igual o similar\nnaturaleza que los que constituyen el objeto del "
                "contrato, y cuyo importe anual\nacumulado en el año de mayor ejecución "
                "sea igual o superior al 70 por ciento de la\nanualidad media del "
                "contrato.",
            ),
        ),
        certifications=[
            RequiredCertification(
                name="Acreditación ENAC para la certificación de la norma UNE-EN ISO 22301",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=Citation(
                    clause="F)",
                    page=7,
                    quote="Acreditación ENAC (o entidad de acreditación equivalente) para la\n"
                    "certificación de la NORMA UNE EN ISO 22301. Las empresas\nlicitadoras que se "
                    "presenten deberán estar acreditadas en España por\nparte de la Entidad "
                    "Nacional de Acreditación (ENAC), u otra entidad de\nacreditación equivalente "
                    "para la certificación de la NORMA UNE EN ISO\n22301, para garantizar la "
                    "aceptación de los certificados emitidos a nivel\nnacional e internacional.",
                ),
            ),
        ],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Oferta Económica", points=49, is_price=True),
                AwardCriterion(
                    name="Criterio Social: Plan de Formación", points=21, is_price=False
                ),
                AwardCriterion(
                    name="Experiencia adicional auditor jefe", points=20, is_price=False
                ),
                AwardCriterion(
                    name="Acto de Entrega Oficial del Certificado de Renovación",
                    points=10,
                    is_price=False,
                ),
            ],
            citation=Citation(
                clause="G)",
                page=8,
                quote="Varios criterios de adjudicación, en base a la mejor relación "
                "calidad-precio,\nestableciéndose para ello los siguientes criterios:",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=5.0,
            description="Sin garantía provisional. Garantía definitiva del 5% del "
            "importe de adjudicación, IVA excluido; complementaria de hasta otro 5% del "
            "presupuesto base de licitación si la oferta estuvo incursa en presunción de "
            "anormalidad.",
            citation=Citation(
                clause="P)",
                page=13,
                quote="DEFINITIVA:\nSi se exige: 5% del importe de adjudicación (IVA excluido).",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="Duración de 3 años.",
            extensions_allowed=True,
            extensions_description="Prorrogable una única vez, hasta 2 años más.",
            citation=Citation(
                clause="E)",
                page=6,
                quote="La duración del contrato será de TRES (3) Años .\nEl contrato es "
                "prorrogable.",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se fija una fecha explícita en el PCAP; remite al anuncio de "
            "licitación publicado en el perfil de contratante de EMUASA.",
            citation=Citation(
                clause="A)",
                page=4,
                quote="La fecha y hora en la que finaliza el plazo para\nproposiciones "
                "presentar oferta figuran en el anuncio de licitación\npublicado en el "
                "Perfil del Contratante de EMUASA en la\nPlataforma de Contratación del "
                "Sector Público.",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida, con comunicación previa al órgano de contratación "
            "identificando la parte a subcontratar y el subcontratista; no existen "
            "tareas críticas excluidas de subcontratación.",
            citation=Citation(
                clause="K)",
                page=12,
                quote="K) SUBCONTRATACIÓN\nProcede:\nSI",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes, justificado en el apartado 2 de la "
            "Memoria Justificativa del contrato.",
            citation=Citation(
                clause="C)",
                page=5,
                quote="Posibilidad de licitar por NO, tal y como se justifica en el "
                "apartado 2 de la\nlotes Memoria Justificativa del contrato.",
            ),
        ),
    ),
    # Equipos Nucleares, S.A., S.M.E. (ENSA) -- servicio de desarrollo e implantación
    # de una aplicación de gestión de desviaciones y acciones. Contrato de naturaleza
    # PRIVADA (ENSA no es Administración Pública), 53 páginas. Sin garantía definitiva
    # en absoluto -- solo un periodo de garantía técnica sobre la solución entregada.
    "001213/2026": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=127500.00,
            description="Volumen anual de negocios de al menos una vez y media el valor "
            "estimado del contrato (85.000 € x 1,5 = 127.500 €), al ser la duración del "
            "contrato de 12 meses (no superior a un año). Además, seguro de "
            "responsabilidad civil vigente por un importe no inferior al valor estimado "
            "del contrato.",
            citation=Citation(
                clause="5.2.1",
                page=17,
                quote="Declaración sobre el volumen anual de negocios, referido como "
                "máximo a los\ntres últimos ejercicios disponibles en función de la "
                "fecha de creación o de inicio\nde actividades del empresario, que "
                "referido al año de mayor volumen deberá ser\nal menos una vez y media "
                "el valor estimado del contrato cuando su duración no\nsea superior a "
                "un año, y al menos una vez y media el valor anual medio del\ncontrato "
                "si su duración es superior a un año.",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=59500.00,
            description="Servicios similares en los últimos tres años con importe anual "
            "acumulado en el año de mayor ejecución de al menos el 70% de la anualidad "
            "media del contrato (70% de 85.000 € = 59.500 €, al coincidir la anualidad "
            "media con el valor estimado en un contrato de 12 meses).",
            citation=Citation(
                clause="12",
                page=3,
                quote="Relación de las principales obras/servicios/suministros\n"
                "realizados en los últimos tres años similares al solicitado, cuyo\n"
                "importe anual acumulado en el año de mayor ejecución sea igual\no "
                "superior al 70 por ciento de la anualidad media del contrato",
            ),
        ),
        certifications=[],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Proposición económica", points=51, is_price=True),
                AwardCriterion(name="Descripción de la Solución", points=37, is_price=False),
                AwardCriterion(name="Plan de Proyecto", points=8, is_price=False),
                AwardCriterion(name="Plan de Formación", points=4, is_price=False),
            ],
            citation=Citation(
                clause="14",
                page=3,
                quote="Los criterios de adjudicación no evaluables mediante fórmulas\n"
                "(CRITERIOS\nserán valorados con hasta un máximo de cuarenta y nueve\n"
                "SUBJETIVOS)\n(49) puntos, según:",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=None,
            description="La licitación no contempla garantía provisional; el pliego no "
            "menciona en ningún punto una garantía definitiva -- solo un periodo de "
            "garantía técnica (24 meses) sobre la solución entregada, coherente con "
            "tratarse de un contrato de naturaleza privada (ENSA no es Administración "
            "Pública).",
            citation=Citation(
                clause="4",
                page=15,
                quote="La presente licitación no contempla la constitución de garantía "
                "provisional.",
            ),
        ),
        execution_deadline=ExecutionDeadline(
            description="Duración de 12 meses desde la fecha indicada en el contrato.",
            extensions_allowed=False,
            extensions_description=None,
            citation=Citation(
                clause="11",
                page=3,
                quote="El plazo de ejecución será de doce (12) meses, a contar desde\n"
                "11 PLAZOS\nla fecha indicada en el contrato.",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="Hasta las 13:00 horas del día 25 de mayo de 2026.",
            citation=Citation(
                clause="13",
                page=3,
                quote="Hasta las 13:00 horas del día 25 de mayo de 2026",
            ),
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida con consentimiento previo y por escrito de ENSA; el "
            "licitador debe indicar en su oferta si prevé subcontratar y el perfil del "
            "subcontratista.",
            citation=Citation(
                clause="18",
                page=7,
                quote="El adjudicatario no podrá ceder ni subcontratar el contrato en\n"
                "todo o en parte sin el consentimiento previo y por escrito de\nENSA.",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="No dividido en lotes: el objeto del contrato constituye una "
            "unidad funcional indivisible.",
            citation=Citation(
                clause="6",
                page=2,
                quote="No procede su división en lotes debido a que el objeto del "
                "contrato\n6 LOTES\nconstituye una unidad funcional indivisible.",
            ),
        ),
    ),
    # Red.es -- servicio avanzado de desarrollo, administración, soporte y
    # mantenimiento de la plataforma de Datos.gob.es. "Condiciones Específicas" de un
    # PCAP partido en dos documentos, 65 páginas -- garantías, lotes y plazo de
    # presentación viven en las "Condiciones Generales" compartidas, no incluidas en
    # este `pcap_url`. El más rico en certificaciones formales (ISO 20000 + ISO/IEC
    # 15504-SPICE nivel 3).
    "003/26-SI": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=1307566.50,
            description="Volumen anual de negocios de al menos una vez y media la "
            "anualidad media del contrato (1.307.566,50 €, ya calculada en el propio "
            "pliego), impuestos indirectos excluidos.",
            citation=Citation(
                clause="3.1",
                page=12,
                quote="de presentación de las ofertas por importe igual o superior a "
                "una vez y media la\nanualidad media del contrato (1.307.566,50 €), "
                "impuestos indirectos aplicables\nexcluidos).",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=610197.70,
            description="Servicios similares en los últimos tres años con importe anual "
            "acumulado en el año de mayor ejecución de al menos 610.197,70 € (70% de la "
            "anualidad media del contrato, ya calculado en el propio pliego).",
            citation=Citation(
                clause="3.2",
                page=12,
                quote="El importe anual acumulado en el año de mayor ejecución deberá "
                "ser igual o\nsuperior a 610.197,70 € (70% de la anualidad media del "
                "contrato), impuestos\nindirectos aplicables excluidos.",
            ),
        ),
        certifications=[
            RequiredCertification(
                name="ISO 20000 (gestión de servicios TI) o norma EN ISO equivalente",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=Citation(
                    clause="3.2.b)",
                    page=13,
                    quote="Dado el objeto del contrato, se exige la presentación de "
                    "certificado expedido\npor organismo independiente conforme a la s normas "
                    "europeas relativas a la\ncertificación, que acredite que el empresario "
                    "cumple con el sistema de gestión de la\ncalidad contenido en la norma ISO "
                    "20.000, como mínimo, o norma EN ISO\nequivalente.",
                ),
            ),
            RequiredCertification(
                name="ISO/IEC 15504-SPICE Nivel 3 (madurez de ingeniería del software) o "
                "certificación equivalente",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=None,
            ),
        ],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Precio", points=55, is_price=True),
                AwardCriterion(
                    name="Propuestas de mejora del desarrollo e implantación de los evolutivos",
                    points=22.5,
                    is_price=False,
                ),
                AwardCriterion(
                    name="Propuestas de mejora de la monitorización de la plataforma",
                    points=22.5,
                    is_price=False,
                ),
            ],
            citation=Citation(
                clause="9.1",
                page=31,
                quote="Los criterios cuya cuantificación depende de un juicio de valor "
                "tendrán un peso del\n45% en la valoración total de la oferta.",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=None,
            description="El documento menciona la existencia de una garantía "
            "definitiva (a efectos de ejecutar penalidades contra ella) pero remite su "
            "régimen y porcentaje a las Condiciones Generales del Pliego de Cláusulas "
            "Administrativas Particulares -- un documento base compartido por varios "
            "expedientes de Red.es (024/23-SI, 013/22-SI) que no forma parte de este "
            "PCAP descargado.",
            citation=None,
        ),
        execution_deadline=ExecutionDeadline(
            description="Duración de 48 meses desde la formalización del contrato.",
            extensions_allowed=None,
            extensions_description=None,
            citation=Citation(
                clause="5",
                page=19,
                quote="El plazo de duración del contrato será de CUARENTA Y OCHO (48) "
                "MESES, a contar\ndesde el día de su formalización.",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se menciona una fecha ni un plazo de presentación de "
            "ofertas en este documento; remite implícitamente a las Condiciones "
            "Generales del Pliego, no incluidas en este PCAP.",
            citation=None,
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida con sujeción a lo dispuesto en los pliegos; "
            "obligación de identificar en la oferta la parte a subcontratar y el "
            "perfil del subcontratista.",
            citation=Citation(
                clause="2.2",
                page=7,
                quote="El contratista podrá concertar con terceros la realización "
                "parcial de la prestación\ncon sujeción a lo dispuesto en los pliegos.",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="La división en lotes no se menciona en ningún punto de este "
            "documento; remite implícitamente a las Condiciones Generales del Pliego, "
            "no incluidas en este PCAP.",
            citation=None,
        ),
    ),
    # Red.es -- servicio de soporte, mantenimiento y mejora de los sistemas de gestión
    # de la entidad. Misma familia documental que 003/26-SI, 46 páginas. Único de los
    # tres con el 100% de la valoración en criterios de fórmula (sin ningún criterio de
    # juicio de valor) y con prórroga obligatoria de otros 24 meses.
    "009/26-SG": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=298350.00,
            description="Volumen anual de negocios de al menos una vez y media la "
            "anualidad media del contrato (298.350 €, ya calculada en el propio "
            "pliego), impuestos indirectos excluidos.",
            citation=Citation(
                clause="3.1",
                page=10,
                quote="de presentación de las ofertas por importe igual o superior a "
                "una vez y media la\nanualidad media del contrato (298.350 €).",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=139230.00,
            description="Servicios similares en los últimos tres años con importe "
            "anual acumulado en el año de mayor ejecución de al menos 139.230 €, "
            "impuestos indirectos excluidos.",
            citation=Citation(
                clause="3.2",
                page=10,
                quote="El importe anual acumulado en el año de mayor ejecución deberá "
                "ser igual o\nsuperior a 139.230 € impuestos indirectos aplicables "
                "excluidos.",
            ),
        ),
        certifications=[
            RequiredCertification(
                name="ISO 9001 (gestión de la calidad) o norma EN ISO equivalente",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=Citation(
                    clause="3.2.b)",
                    page=11,
                    quote="b) Dado el objeto del contrato, se exige la presentación de "
                    "certificado expedido por\norganismo independiente conforme a las normas "
                    "europeas relativas a la\ncertificación, que acredite que el empresario "
                    "cumple con la norma EN ISO 9001,\no equivalente.",
                ),
            ),
        ],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Criterio económico", points=60, is_price=True),
                AwardCriterion(name="Criterio Técnico Cuantificable 1", points=5, is_price=False),
                AwardCriterion(name="Criterio Técnico Cuantificable 2", points=5, is_price=False),
                AwardCriterion(name="Criterio Técnico Cuantificable 3", points=15, is_price=False),
                AwardCriterion(name="Criterio Técnico Cuantificable 4", points=15, is_price=False),
            ],
            citation=Citation(
                clause="9.2",
                page=26,
                quote="Los criterios cuantificables mediante la mera aplicación de "
                "fórmulas tendrán un\npeso del 100% de la valoración total de la "
                "oferta e incluyen, además del resto de los\ncriterios que presentan "
                "tal naturaleza, el criterio económico.",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=None,
            description="El documento menciona la existencia de una garantía "
            "definitiva (a efectos de ejecutar penalidades contra ella) pero remite su "
            "régimen y porcentaje a las Condiciones Generales del Pliego de Cláusulas "
            "Administrativas Particulares, un documento base compartido por varios "
            "expedientes de Red.es que no forma parte de este PCAP descargado.",
            citation=None,
        ),
        execution_deadline=ExecutionDeadline(
            description="Duración de 24 meses desde la formalización.",
            extensions_allowed=True,
            extensions_description="Prorrogable, obligatoriamente para el contratista, por un "
            "periodo adicional de 24 meses.",
            citation=Citation(
                clause="5",
                page=16,
                quote="El plazo de duracio n del Contrato sera de 24 MESES desde el "
                "dí a de su formalizacio n.",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se menciona una fecha ni un plazo de presentación de "
            "ofertas en este documento; remite implícitamente a las Condiciones "
            "Generales del Pliego, no incluidas en este PCAP.",
            citation=None,
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida con sujeción a lo dispuesto en los pliegos; "
            "obligación de identificar en la oferta el porcentaje a subcontratar y el "
            "perfil del subcontratista.",
            citation=Citation(
                clause="2.2",
                page=7,
                quote="El contratista podrá concertar con terceros la realización "
                "parcial de la prestación\ncon sujeción a lo dispuesto en los pliegos.",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="La división en lotes no se menciona en ningún punto de este "
            "documento; remite implícitamente a las Condiciones Generales del Pliego, "
            "no incluidas en este PCAP.",
            citation=None,
        ),
    ),
    # Red.es -- servicio de desarrollo, implantación y mantenimiento de servicios de
    # Inteligencia Artificial y automatización de procesos. Misma familia documental
    # que 003/26-SI y 009/26-SG, 54 páginas. El único de los tres con dos
    # certificaciones formales (ISO 9001 + ISO 27001) y con sus criterios de juicio de
    # valor y de fórmula desglosados en subcriterios de grano fino.
    "015/25-SI": PliegoExtraction(
        economic_solvency=EconomicSolvency(
            minimum_annual_turnover_eur=971327.5,
            description="Volumen anual de negocios de al menos una vez y media la "
            "anualidad media del presupuesto base de licitación del contrato "
            "(971.327,5 €, ya calculada en el propio pliego).",
            citation=Citation(
                clause="3.1",
                page=12,
                quote="superior a una vez y media la anualidad media del presupuesto "
                "base de licitación del\ncontrato (971.327,5 €).",
            ),
        ),
        technical_solvency=TechnicalSolvency(
            minimum_amount_eur=453286.17,
            description="Servicios similares en los últimos tres años con importe "
            "anual acumulado en el año de mayor ejecución de al menos 453.286,17 €, "
            "impuestos indirectos excluidos.",
            citation=Citation(
                clause="3.2",
                page=13,
                quote="El importe anual acumulado de los servicios realizados en el "
                "año de mayor\nejecución deberá ser igual o superior a CUATROCIENTOS "
                "CINCUENTA Y TRES MIL\nDOSCIENTOS OCHENTA Y SEIS EUROS CON DIECISIETE "
                "CÉNTIMOS (453.286,17€),\nimpuestos indirectos aplicables excluidos.",
            ),
        ),
        certifications=[
            RequiredCertification(
                name="ISO 9001 (gestión de la calidad) o certificación equivalente",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=Citation(
                    clause="3.2.b)",
                    page=13,
                    quote="b) Dado el objeto del contrato, se exige la presentación de "
                    "certificado\nexpedido por organismo independiente conforme a las "
                    "normas europeas relativas a\nla certificación, que acredite que el "
                    "empresario cumple con la norma EN ISO 9001,\no certificación "
                    "equivalente.",
                ),
            ),
            RequiredCertification(
                name="ISO 27001 (gestión de la seguridad de la información) o certificación "
                "equivalente",
                role=CertificationRole.REQUIRED_TO_BID,
                citation=None,
            ),
        ],
        award_criteria=AwardCriteria(
            total_points=100,
            criteria=[
                AwardCriterion(name="Criterio económico", points=42, is_price=True),
                AwardCriterion(
                    name="Propuestas de medidas de utilización eficiente de la "
                    "plataforma tecnológica",
                    points=16,
                    is_price=False,
                ),
                AwardCriterion(
                    name="Propuestas de fomento de la concienciación y uso "
                    "responsable de la plataforma",
                    points=12,
                    is_price=False,
                ),
                AwardCriterion(
                    name="Propuestas de mejora del rendimiento de los servicios de "
                    "ejecución masiva",
                    points=12,
                    is_price=False,
                ),
                AwardCriterion(
                    name="Criterio Técnico cuantificable CTC1 (cualificación de "
                    "perfiles expertos en inteligencia artificial)",
                    points=9,
                    is_price=False,
                ),
                AwardCriterion(
                    name="Criterio Técnico cuantificable CTC2 (cualificación de "
                    "perfiles expertos en automatización)",
                    points=9,
                    is_price=False,
                ),
            ],
            citation=Citation(
                clause="9.1",
                page=29,
                quote="Los criterios cuya cuantificación depende de un juicio de "
                "valor tendrán un\npeso del 40% del total en la valoración de la "
                "oferta.",
            ),
        ),
        guarantees=Guarantees(
            provisional_required=False,
            definitive_percentage=None,
            description="El documento menciona la existencia de una garantía "
            "definitiva (a efectos de ejecutar penalidades contra ella) pero remite su "
            "régimen y porcentaje a las Condiciones Generales del Pliego de Cláusulas "
            "Administrativas Particulares, un documento base compartido por varios "
            "expedientes de Red.es que no forma parte de este PCAP descargado.",
            citation=None,
        ),
        execution_deadline=ExecutionDeadline(
            description="Duración de 36 meses desde el día siguiente a la formalización del "
            "contrato.",
            extensions_allowed=None,
            extensions_description=None,
            citation=Citation(
                clause="5",
                page=19,
                quote="El plazo de duración del Contrato será de TREINTA Y SEIS (36) "
                "MESES desde\nel día siguiente a su formalización.",
            ),
        ),
        submission_deadline=SubmissionDeadline(
            description="No se menciona una fecha ni un plazo de presentación de "
            "ofertas en este documento; remite implícitamente a las Condiciones "
            "Generales del Pliego, no incluidas en este PCAP.",
            citation=None,
        ),
        subcontracting=Subcontracting(
            allowed=True,
            description="Permitida con sujeción a lo dispuesto en los pliegos; "
            "obligación de identificar en la oferta el porcentaje a subcontratar y el "
            "perfil del subcontratista.",
            citation=Citation(
                clause="2.3",
                page=9,
                quote="El contratista podrá concertar con terceros la realización "
                "parcial de la\nprestación con sujeción a lo dispuesto en los "
                "pliegos.",
            ),
        ),
        lots=Lots(
            divided_into_lots=False,
            can_bid_partial_lots=None,
            description="La división en lotes no se menciona en ningún punto de este "
            "documento; remite implícitamente a las Condiciones Generales del Pliego, "
            "no incluidas en este PCAP.",
            citation=None,
        ),
    ),
}
