"""Tests for the golden set's internal consistency and real-corpus grounding -- grown
from the original 4 (3.4, model decision) toward 25-30 (4.3, RAGAS golden set).
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.analysis.golden_set import GOLDEN_SET
from compass.tenders.models import Tender


def test_golden_set_size_matches_the_current_batch() -> None:
    """Protects against silently losing or duplicating an entry while 4.3 grows the set
    in batches of ~5-7 toward 25-30 -- bumped by hand each time a batch lands, not
    computed, so a missing/extra entry fails loudly instead of passing by accident.
    """
    assert len(GOLDEN_SET) == 25


def test_certifications_citation_is_none_only_when_certifications_is_empty() -> None:
    """Protects the schema's own rule: a citation exists only when there's something to cite."""
    for expediente, extraction in GOLDEN_SET.items():
        has_certifications = bool(extraction.certifications)
        has_citation = extraction.certifications_citation is not None
        assert has_certifications == has_citation, expediente


# Needs the real PLACSP corpus persisted locally, which a CI runner doesn't have --
# see docs/phases/phase4/subphases/phase4.6.md.
@pytest.mark.real_corpus
async def test_golden_set_expedientes_still_exist_with_a_pcap_url(db_session: AsyncSession) -> None:
    """Protects the golden set from going stale.

    If one of these tenders were ever edited or removed from the real corpus, or lost
    its `pcap_url`, this fails loudly instead of quietly grounding a model decision or
    a RAGAS eval in a pliego that no longer matches reality.
    """
    result = await db_session.execute(
        select(Tender.expediente, Tender.pcap_url).where(Tender.expediente.in_(GOLDEN_SET.keys()))
    )
    found: dict[str, str | None] = {row.expediente: row.pcap_url for row in result}

    assert found.keys() == GOLDEN_SET.keys()
    assert all(pcap_url for pcap_url in found.values())
