"""What counts as a formal certification, shared by the verdict and the regression gate.

Both need the same answer to the same question and they used to answer it apart: 5.8 found
`scoring.py` measuring a field through an ISO-only regex while `verdict.py` acted on every
string in it, which is how a field full of garbage passed its own gate while emitting false
NO APTO verdicts. One definition, imported by both, is what stops that from drifting again.

**Why the verdict needs this at all**, when the extraction already carries a
`CertificationRole`. Because the model does not fill that role reliably. Measured in 5.8
over three real pliegos re-analyzed against the 5.8 schema: **every certification came back
`required_to_bid`**, including a "Declaración responsable" that the field's own description
names as paperwork, and four job profiles ("Responsable tècnic del projecte",
"Especialista en Seguretat Informàtica") that the same description tells the model are
staffing requirements and never certifications. The role is the right structure and it
stays -- when the model does use it, the verdict honours it -- but a verdict that blocks a
bid cannot rest on a judgement call the model is observably getting wrong.

So the code keeps the last word, which is the project's own rule (`docs/phases/phase3/
phase3.md`, "el LLM extrae, el código decide"). A certification blocks only with positive
evidence that it is a formal certification a company holds: a recognised standard family
with its number, or one of the named schemes. Anything else the model flagged as required
becomes a *reservation* -- it still reaches the reader, with its citation, but as "the
pliego asks for this and your profile can't be checked against it" rather than a silent
rejection.

That direction is deliberate. `verdict.py` used to justify its permissive matching by
saying a missing certification blocks the bid entirely, so precision could wait until there
was evidence it was needed. The evidence arrived, and it points the other way: the failure
this product cannot afford is discarding a tender the provider could have won, in silence.
Trading it for a visible APTO CON RESERVAS is the cheap side of that trade.
"""

import re
import unicodedata

_WORD_RE = re.compile(r"[a-z0-9]+")

# The families a Spanish PCAP actually names. `ENS` and `CCN-CERT` are the national
# security scheme and the body that certifies it; `ENAC` accredits the certifiers
# themselves and appears as a requirement in its own right (golden set, `019-SER-2026`).
_STANDARD_RE = re.compile(
    r"(?:ISO/?\s?IEC|ISO|UNE(?:[-\s]?EN)?|EN)\s?\d{4,5}|CMMI|ENS\b|CCN-?CERT|ENAC",
    re.IGNORECASE,
)
_DIGITS_RE = re.compile(r"\d{4,5}")


def normalized_name(name: str) -> str:
    """A certification's name as lowercase, accent-free words joined by single spaces."""
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(_WORD_RE.findall(without_accents.lower()))


def is_formal_certification(name: str) -> bool:
    """Whether `name` names a recognised certification scheme.

    Deliberately a closed list of families rather than a general "does this look
    official" judgement: the point is to be wrong in a predictable direction. A real
    certification phrased outside these families is downgraded to a reservation, which
    the reader sees; a job profile or a declaración responsable can never block a bid.
    """
    return _STANDARD_RE.search(name) is not None


def identities(name: str) -> set[str]:
    """What `name` claims, as comparable identifiers.

    A standard is identified by its number, not by the family that prefixes it: 'ISO
    27001', 'ISO/IEC 27001' and 'UNE-EN ISO 27001:2013 o equivalente' all reduce to
    `{'27001'}`. A name matching no family keeps its whole normalized text rather than
    reducing to nothing -- the old regex discarded it, and that is what made the
    regression gate blind to the garbage that produced false NO APTO verdicts.
    """
    marks = _STANDARD_RE.findall(name)
    if not marks:
        return {normalized_name(name)}
    found: set[str] = set()
    for mark in marks:
        digits = _DIGITS_RE.search(mark)
        found.add(digits.group(0) if digits else normalized_name(mark))
    return found
