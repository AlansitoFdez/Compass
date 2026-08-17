"""Official PLACSP CODICE code lists, verified against the source classification documents.

Sources:
- https://contrataciondelestado.es/codice/cl/2.08/ContractCode-2.08.gc
- https://contrataciondelestado.es/codice/cl/2.04/SyndicationContractFolderStatusCode-2.04.gc
- https://contrataciondelestado.es/codice/cl/2.07/SyndicationTenderingProcessCode-2.07.gc
"""

from compass.tenders.enums import ContractType, TenderStatus

CONTRACT_TYPE_CODES: dict[str, ContractType] = {
    "1": ContractType.SUPPLIES,
    "2": ContractType.SERVICES,
    "3": ContractType.WORKS,
    "21": ContractType.PUBLIC_SERVICES_MANAGEMENT,
    "22": ContractType.SERVICES_CONCESSION,
    "31": ContractType.PUBLIC_WORKS_CONCESSION,
    "32": ContractType.WORKS_CONCESSION,
    "40": ContractType.PUBLIC_PRIVATE_COLLABORATION,
    "7": ContractType.SPECIAL_ADMINISTRATIVE,
    "8": ContractType.PRIVATE,
    "50": ContractType.PATRIMONIAL,
}

STATUS_CODES: dict[str, TenderStatus] = {
    "PRE": TenderStatus.PRIOR_NOTICE,
    "PUB": TenderStatus.OPEN_FOR_SUBMISSION,
    "EV": TenderStatus.PENDING_AWARD,
    "ADJ": TenderStatus.AWARDED,
    "RES": TenderStatus.RESOLVED,
    "ANUL": TenderStatus.CANCELLED,
}

PROCEDURE_TYPE_LABELS: dict[str, str] = {
    "1": "Abierto",
    "2": "Restringido",
    "3": "Negociado sin publicidad",
    "4": "Negociado con publicidad",
    "5": "Diálogo competitivo",
    "6": "Contrato menor",
    "7": "Derivado de acuerdo marco",
    "8": "Concurso de proyectos",
    "9": "Abierto simplificado",
    "10": "Asociación para la innovación",
    "11": "Derivado de asociación para la innovación",
    "12": "Basado en un sistema dinámico de adquisición",
    "13": "Licitación con negociación",
    "100": "Normas internas",
    "999": "Otros",
}


def get_contract_type(code: str) -> ContractType:
    try:
        return CONTRACT_TYPE_CODES[code]
    except KeyError:
        raise ValueError(f"Unknown contract type code: {code!r}") from None


def get_status(code: str) -> TenderStatus:
    try:
        return STATUS_CODES[code]
    except KeyError:
        raise ValueError(f"Unknown status code: {code!r}") from None


def get_procedure_type_label(code: str) -> str:
    try:
        return PROCEDURE_TYPE_LABELS[code]
    except KeyError:
        raise ValueError(f"Unknown procedure type code: {code!r}") from None
