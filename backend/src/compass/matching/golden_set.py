"""Golden set for the seeded provider profile: hand-annotated relevance over the real,
complete Etapa 1 survivor population (2026-09-07 snapshot), not a small hand-picked sample.

Used in 2.4 to measure recall@k for candidate embedding models before choosing one; the same
set is meant to be reused as the base for the RAGAS golden set in Fase 4.

Annotation criterion (full reasoning in docs/phases/phase2/subphases/phase2.4.md): a tender
counts as relevant only when it carries an explicit signal matching the profile's declared
specialty -- "web"/"portal" in the title, one of the named technologies (Drupal, WordPress, or
their close family like CiviCRM/OpenCms), explicit accessibility, or explicit sede
electrónica/e-administration. Generic "desarrollo"/"aplicación"/"plataforma" without one of
those signals doesn't count on its own, even for a clearly IT-related tender -- that's exactly
the kind of noise a plain keyword match already produces (2.3's OR-tsquery finding), and this
set exists to measure whether embeddings do better than that.

Five tenders that stayed genuinely ambiguous even under that criterion -- a mobile app, a
specific vendor's financial-suite maintenance, an AI-agent migration PoC, and two generic SaaS
platform implementations -- are excluded from the set entirely rather than forced into a label:
an uncertain annotation is worse than no annotation for a set meant to measure precision.
"""

from datetime import UTC, datetime

ANNOTATED_THROUGH = datetime(2026, 9, 7, tzinfo=UTC)
"""The corpus snapshot these labels cover: every tender ingested on or before this date.

Recorded as a constant in 5.8, because leaving it only in the prose above turned into a
test that could not stay green. `test_golden_set_covers_exactly_the_real_etapa1_survivors`
asserted that every live Etapa 1 survivor carried a label -- true the day it was written,
and false from the first daily ingestion that brought in an IT tender still open for bids.
Four of them had arrived by 5.8 (`2026-074`, `2026-P154`, `2026/CTT_01/000105`,
`45/26 NEG`), all ingested that same morning, and the suite had been failing on the
developer's machine ever since while passing in CI, where the corpus is empty.

A tender ingested after this date was never annotatable, so it is not evidence of a stale
golden set; one ingested before it and still unlabelled is. Scoping the assertion by
`Tender.created_at` keeps the second alarm and drops the first.

The one thing this doesn't fix: `embedding_eval.py` ranks whatever Etapa 1 returns today,
so newer unlabelled tenders do push annotated ones down and depress its recall@k. That
script is the one-off from 2.4 whose numbers are already published; re-scoping it would
silently change what those numbers mean, so it stays as it is and this note says why.
"""

RELEVANT_EXPEDIENTES: frozenset[str] = frozenset(
    {
        "INN 26 002",
        "TEC0007188",
        "69/2026",
        "754/2026",
        "CONTR 2026 17947",
        "582026047500",
        "AST-2026-20162",
        "2026000731",
        "SER/2026/0000006435",
        "A41119033-2026/000065-PeAS",
        "23/2026",
        "MY26/VACTS/SE/60",
        "DEF-401/2026",
        "1276564F",
        "2026/15",
    }
)

NOT_RELEVANT_EXPEDIENTES: frozenset[str] = frozenset(
    {
        "2026/S-ABT/0000025771 - Gestión de expedientes",
        "4276/2026 PASS MIXTO SERV/SUM",
        "11029-113",
        "L26-SERV-06",
        "897/2026",
        "SUMIN/ABR/2026000089",
        "2026000358",
        "CO 5-2026 asesoramiento informatico y telefonia",
        "69-26",
        "1442/2026",
        "SERV/ABR/2026000083",
        "PASA/26/36/0996",
        "SERV/ABR/2026000082",
        "SSCC PA 220/26",
        "PA 15/2026",
        "SERV-2026000088",
        "49P/26",
        "PC-MER/2026/00033-ORD",
        "2026/405040/006-302/00002",
        "CMA 04/2026",
        "2026-059",
        "PA 91/2026",
        "129/25",
        "OC/0002/2026",
        "2026/20",
        "F08/26",
        "2026-SES-054",
        "CMAYOR/2026/AEROC/388",
        "202601JC0007",
        "300/2026/01246",
        "ASE/2026/109",
        "2026/860102",
        "2026-01027",
        "MMUR/012026",
        "61/2025",
        "PAS 325/2026",
        "26/36472",
        "582026020000",
        "582026026100",
        "31-2026 SIT",
        "2026/040.SER.ABR.MC",
    }
)

# Ambiguous even under the criterion above -- dropped from the set entirely, not labeled.
EXCLUDED_EXPEDIENTES: frozenset[str] = frozenset(
    {
        "MT260312",
        "1868392P",
        "PLI-02634",
        "CB-SS 02/2026",
        "2545974A",
    }
)
