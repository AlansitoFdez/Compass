"""Tests for the 4.5 trace-hygiene mask -- not `get_langfuse_client` itself, which just
wires already-validated settings into the SDK's constructor.
"""

from compass.analysis.tracing import _MAX_TRACED_STRING_LENGTH, _mask_long_text


def test_short_strings_pass_through_unchanged() -> None:
    """Protects that ordinary citation quotes/descriptions aren't touched."""
    text = "cifra de negocio minima de 100000 euros"
    assert _mask_long_text(data=text) == text


def test_long_strings_are_truncated_with_their_original_length_noted() -> None:
    """Protects the actual point: a full PCAP page (thousands of characters) doesn't
    reach Langfuse whole.
    """
    text = "a" * (_MAX_TRACED_STRING_LENGTH + 100)

    result = _mask_long_text(data=text)

    assert isinstance(result, str)
    assert len(result) < len(text)
    assert result.startswith("a" * _MAX_TRACED_STRING_LENGTH)
    assert str(len(text)) in result


def test_recurses_into_dicts_and_lists() -> None:
    """Protects the real shape this runs against: `PliegoAnalysisState["pages"]` is a
    list of per-page strings nested inside the traced state dict, not a bare string.
    """
    # A realistic PCAP page (thousands of characters), not a value barely over the
    # threshold -- the truncation message itself has some overhead, so a string only
    # a few bytes past the limit could come back *longer*, not shorter.
    long_page = "b" * (_MAX_TRACED_STRING_LENGTH * 20)
    state = {"pcap_url": "https://example.test/pliego.pdf", "pages": [long_page, "short"]}

    result = _mask_long_text(data=state)

    assert isinstance(result, dict)
    assert result["pcap_url"] == "https://example.test/pliego.pdf"
    pages = result["pages"]
    assert isinstance(pages, list)
    assert pages[1] == "short"
    assert len(pages[0]) < len(long_page)


def test_non_string_scalars_pass_through() -> None:
    """Protects that this never breaks on the non-string data Langfuse also masks
    (numbers, booleans, None) -- nothing here should ever need truncating.
    """
    assert _mask_long_text(data=42) == 42
    assert _mask_long_text(data=True) is True
    assert _mask_long_text(data=None) is None
