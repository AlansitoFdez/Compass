"""Golden set: real PCAPs, hand-annotated field by field.

Started in 3.4 with 4 pliegos to pick the extraction model; extended in 4.3 to 25-30
for RAGAS (Fase 4) -- a golden set of that size measures faithfulness and extraction
correctness as a real regression gate, per the design doc. Same "small-to-medium,
real, no blind pick" method the 2.4 embedding decision and the 3.4 model decision both
used, just at a larger scale for the statistical purpose RAGAS needs.

Each entry is a real `expediente` from the seeded provider's live matches (`GET
/matches`), picked for structural diversity, not for being easy: narrative
clause-numbered PCAPs alongside "Cuadro de Características" summary-table formats, and
each of solvencia/garantías/subcontratación/plazo/lotes intentionally varies in how (or
whether) it's expressed -- some as a hard euro threshold, some computed from a formula
the pliego states but doesn't pre-calculate, some as an insurance policy, some deferred
entirely to the anuncio de licitación or the PPT, some explicitly exempted. A model
that only pattern-matches "solvencia económica -> find a euro figure" will get some of
these wrong; that's the point.

**Real limitation found while building the 4.3 batch, not present in the original
4**: at least two real candidates considered for this set turned out structurally
unusable for extraction, for reasons worth knowing about rather than silently
discarding:
- A PCAP whose `pcap_url` is a "pliego tipo" (template) that defers every concrete
  figure -- solvencia, plazos, garantía, criterios -- to a separate "Cuadro Resumen"
  that isn't part of the downloaded document at all (`document.extract_pages` returns
  real text, just none of the substantive values). Seen twice among the discarded
  candidates.
- A PCAP (Ayuntamiento de Ayerbe, `1868392P`) whose every page extracts to nothing but
  its own digital-signature header/footer boilerplate -- the clause text itself never
  appears in `extract_pages`'s output, likely from how that municipality's e-signature
  platform overlays the signed stamp on the original document. `has_text_layer` would
  not catch this today: there's plenty of (repeated, boilerplate) text per page, just
  none of it substantive. Not fixed here -- flagged as a real gap for a future
  subphase, not this one's job (see phase4.3.md).

Annotated directly from the PCAP text (`compass.analysis.document.extract_pages`
against the tender's real `pcap_url`), not from a summary -- every `Citation.quote`
below is copied verbatim from the pliego. The 3.4 batch was downloaded 2026-09-09; the
4.3 batch, 2026-09-11.
"""

from compass.analysis.extraction_schema import (
    AwardCriteria,
    AwardCriterion,
    Citation,
    EconomicSolvency,
    ExecutionDeadline,
    Guarantees,
    Lots,
    PliegoExtraction,
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
        certifications_citation=None,
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
            description="Vigencia máxima de 2 años desde la formalización, prorrogable; la "
            "prestación del servicio tiene un máximo de 4 años incluyendo prórrogas.",
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
            "CMMI nivel 3 o superior",
            "ISO 9000 o equivalente",
            "ISO 14000 o equivalente",
            "ISO 20000 o equivalente",
            "ISO 27000 o equivalente",
            "ENS nivel medio/alto (certificado CCN-CERT)",
        ],
        certifications_citation=Citation(
            clause="6.4",
            page=3,
            quote="Certificado expedido por organismo independiente, conforme a las "
            "normas\nrelativas a la certificación, que acredite que el empresario cumple con "
            "la\ncertificación de Modelo de Madurez de Capacidades de Integración "
            "(CMMI)\nnivel 3 o superior",
        ),
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
        certifications_citation=None,
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
            "servicio en un plazo máximo de tres meses; prorrogable hasta dos años más.",
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
        certifications_citation=None,
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
            "2026. No procede prórroga.",
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
            "Certificado cumplimiento del ENS en categoría ALTA",
            "Certificado ISO 20000",
            "Certificado ISO 27001",
            "Certificado ISO 27017",
            "Certificado ISO 27018",
            "Certificado ISO 22301",
            "Certificación ISO 50001",
        ],
        certifications_citation=Citation(
            clause="10.1.l)",
            page=7,
            quote="Certificado cumplimiento del ENS en categoría ALTA del licitador.",
        ),
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
            description="Vigencia de un año desde la firma del contrato, prorrogable por un "
            "año más por acuerdo del órgano de contratación.",
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
        certifications_citation=None,
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
            description="Desde el día siguiente de la firma del contrato hasta el 30 de "
            "diciembre de 2026, con posible prórroga con un preaviso general de dos "
            "meses.",
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
        certifications_citation=None,
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
            description="Duración inicial de un año desde la formalización del contrato (o "
            "la fecha que se determine en el documento de formalización).",
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
        certifications_citation=None,
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
            description="12 meses desde el 1 de enero de 2027 o desde la formalización si "
            "fuera posterior. Prórroga prevista hasta un máximo de 36 meses, renovada "
            "anualmente.",
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
        certifications_citation=None,
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
            description="24 meses desde el 1 de diciembre de 2026 (o desde la "
            "formalización si fuera posterior), prorrogable hasta 24 meses más.",
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
}
