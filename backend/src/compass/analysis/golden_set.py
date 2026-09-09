"""Golden set for 3.4: four real PCAPs, hand-annotated field by field, used to measure
extraction accuracy for the two free OpenRouter candidates before picking one.

Not 25-30 pliegos (that's the RAGAS golden set of Fase 4, per the design doc) -- a small
set is enough to compare two candidate models on real, heterogeneous pliegos, the same
"small set, real data, no blind pick" method the 2.4 embedding decision used.

Each entry is a real `expediente` from the seeded provider's live matches (`GET
/matches`), picked for structural diversity, not for being easy: two different PCAP
styles (narrative clause-numbered text vs. a "Cuadro de Características" summary
table), and each of solvencia/garantías/subcontratación/plazo intentionally varies in
how (or whether) it's expressed -- some as a hard euro threshold, some as an insurance
policy, some deferred entirely to the anuncio de licitación or the PPT. A model that
only pattern-matches "solvencia económica -> find a euro figure" will get some of these
wrong; that's the point.

Annotated directly from the PCAP text (`compass.analysis.document.extract_pages`
against the tender's real `pcap_url`, downloaded 2026-09-09), not from a summary --
every `Citation.quote` below is copied verbatim from the pliego.
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
}
