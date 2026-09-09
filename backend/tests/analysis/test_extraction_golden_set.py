"""Tests for the 3.4 golden set's internal consistency and real-corpus grounding."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.analysis.golden_set import GOLDEN_SET
from compass.tenders.models import Tender


def test_golden_set_has_exactly_four_annotated_pliegos() -> None:
    """Protects the documented scope: a small real golden set (3.4), not the 25-30
    RAGAS set of Fase 4.
    """
    assert len(GOLDEN_SET) == 4


def test_certifications_citation_is_none_only_when_certifications_is_empty() -> None:
    """Protects the schema's own rule: a citation exists only when there's something to cite."""
    for expediente, extraction in GOLDEN_SET.items():
        has_certifications = bool(extraction.certifications)
        has_citation = extraction.certifications_citation is not None
        assert has_certifications == has_citation, expediente


async def test_golden_set_expedientes_still_exist_with_a_pcap_url(db_session: AsyncSession) -> None:
    """Protects the golden set from going stale.

    If one of these four tenders were ever edited or removed from the real
    corpus, or lost its `pcap_url`, this fails loudly instead of quietly
    grounding the 3.4 model decision in a pliego that no longer matches reality.
    """
    result = await db_session.execute(
        select(Tender.expediente, Tender.pcap_url).where(Tender.expediente.in_(GOLDEN_SET.keys()))
    )
    found: dict[str, str | None] = {row.expediente: row.pcap_url for row in result}

    assert found.keys() == GOLDEN_SET.keys()
    assert all(pcap_url for pcap_url in found.values())
