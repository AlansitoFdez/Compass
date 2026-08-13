"""Filter for the IT-services CPV vertical (Division 72) that scopes ingestion.

Division 72 = "IT services: consulting, software development, Internet and
support" in the EU's CPV classification, covering subgroups 72100000
(hardware consultancy) through 72900000 (backup and catalogue conversion).
"""

IT_SERVICES_CPV_DIVISION = "72"


def normalize_cpv_code(cpv_code: str) -> str:
    """Strip the optional check digit suffix (e.g. "72212730-0" -> "72212730")."""
    return cpv_code.split("-")[0].strip()


def is_it_services_cpv(cpv_code: str) -> bool:
    """Whether a single CPV code falls under Division 72 (IT services)."""
    return normalize_cpv_code(cpv_code).startswith(IT_SERVICES_CPV_DIVISION)


def matches_it_vertical(cpv_codes: list[str]) -> bool:
    """Whether any of a tender's CPV codes falls under Division 72."""
    return any(is_it_services_cpv(code) for code in cpv_codes)
