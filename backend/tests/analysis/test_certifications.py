"""Tests for what the project is willing to call a certification.

The names here are not invented: every one of them came out of a real extraction during
5.8, which is the point -- this module exists because the model put all of them in the
same field and called them all required.
"""

from compass.analysis.certifications import identities, is_formal_certification, normalized_name


def test_recognizes_the_families_a_pcap_actually_names() -> None:
    """Protects the list from shrinking by accident: each of these appears as a real
    requirement in the golden set or in a re-analyzed pliego.
    """
    for name in (
        "ISO 9001",
        "ISO/IEC 27001:2013 o equivalente",
        "UNE-EN ISO 22301",
        "Certificación de SGSI ISO27001, ENS o equivalente, en vigor",
        "CMMI nivel 3 o superior",
        "ENS categoría media o superior",
        "certificado CCN-CERT",
        "Acreditación ENAC para la certificación de la norma UNE-EN ISO 22301",
    ):
        assert is_formal_certification(name) is True, name


def test_rejects_what_the_model_kept_putting_in_the_field() -> None:
    """Protects the guard that keeps a bid from being refused over these. All four job
    profiles come from `INN 26 002`'s clause F.3, which is a staffing requirement
    ("Indicació del personal tècnic"), and the rest from `2026/20` and `1276564F`.
    """
    for name in (
        "Responsable tècnic del projecte",
        "Administrador de Sistemes informàtics en xarxa",
        "Especialista en Seguretat Informàtica",
        "Declaración responsable",
        "Certificación positiva, expedida por la Agencia Estatal de Administración "
        "Tributaria de hallarse al corriente en el cumplimiento de sus obligaciones "
        "tributarias.",
        "citation",
    ):
        assert is_formal_certification(name) is False, name


def test_a_standard_is_identified_by_its_number_not_its_prefix() -> None:
    """Protects the regression gate from failing on wording: the same requirement written
    three ways is one identity, because the number is what names the standard.
    """
    assert identities("ISO 27001") == identities("ISO/IEC 27001")
    assert identities("ISO 27001") == identities("UNE-EN ISO 27001:2013 o equivalente, en vigor")


def test_an_unrecognized_name_keeps_its_whole_text() -> None:
    """Protects against the blindness 5.8 found: reducing an unrecognized name to nothing
    is what let a field full of garbage score as correct against an empty annotation.
    """
    assert identities("Declaración responsable") == {"declaracion responsable"}


def test_normalized_name_ignores_accents_case_and_punctuation() -> None:
    """Protects comparisons from the three ways the same name is written in practice."""
    assert normalized_name("ISO/IEC 27001:2013") == normalized_name("iso iec 27001 2013")
