"""Tests for the golden set's internal consistency and real-corpus grounding -- grown
from the original 4 (3.4, model decision) toward 25-30 (4.3, RAGAS golden set).
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compass.analysis.enums import CertificationRole
from compass.analysis.golden_set import GOLDEN_SET
from compass.tenders.models import Tender


def test_golden_set_size_matches_the_current_batch() -> None:
    """Protects against silently losing or duplicating an entry while 4.3 grows the set
    in batches of ~5-7 toward 25-30 -- bumped by hand each time a batch lands, not
    computed, so a missing/extra entry fails loudly instead of passing by accident.
    """
    assert len(GOLDEN_SET) == 25


def test_every_annotated_certification_is_one_that_can_block_a_bid() -> None:
    """Protects what the golden set means by a certification after 5.8.

    All 22 were re-read against their own pliego when the role field landed, and every
    one of them is a condition of admission -- clause 6.4 of
    `A41119033-2026/000065-PeAS`, clause 10.1.l) of `2545974A`, the "Habilitación" of
    `SERV-2026000088`, the "se exige la presentación de certificado" clauses of the
    three Red.es pliegos. If an entry ever arrives with a scored or paperwork
    certification, it needs its own reasoning written down, not a silent label.
    """
    for expediente, extraction in GOLDEN_SET.items():
        for certification in extraction.certifications:
            assert certification.role is CertificationRole.REQUIRED_TO_BID, (
                f"{expediente}: {certification.name}"
            )


def test_extensions_are_answered_for_every_entry() -> None:
    """Protects the 5.8 re-annotation from rotting back into a half-answer: a null here
    means "this PCAP says nothing about prórrogas", which is true of exactly three
    entries, and must stay a deliberate claim rather than a gap nobody filled.
    """
    unanswered = {
        expediente
        for expediente, extraction in GOLDEN_SET.items()
        if extraction.execution_deadline.extensions_allowed is None
    }

    assert unanswered == {"23/2026", "003/26-SI", "015/25-SI"}


def test_an_extension_description_exists_exactly_when_extensions_are_allowed() -> None:
    """Protects the schema's own rule: describing prórrogas that the pliego rules out,
    or allowing them without saying what they are, are both incoherent.
    """
    for expediente, extraction in GOLDEN_SET.items():
        deadline = extraction.execution_deadline
        has_description = deadline.extensions_description is not None
        assert has_description == (deadline.extensions_allowed is True), expediente


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
