from app.ocr.types import ParsedDocument, ParsedPage, TextBlock
from app.verification import verify_citation

_PAGE_TEXT = (
    "Total and Permanent Disability means the life insured is, in the opinion of "
    "two registered medical practitioners, permanently unable to perform their own "
    "occupation due to illness or injury. This is assessed on an own occupation basis."
)


def _doc(page_number: int = 1) -> ParsedDocument:
    return ParsedDocument(
        pages=(
            ParsedPage(
                page_number=page_number,
                text_blocks=(TextBlock(_PAGE_TEXT, (0, 0, 1, 1), f"{page_number}.1"),),
                native_text_coverage=1.0,
            ),
        ),
        backend_used="pymupdf",
    )


def test_exact_substring_verifies():
    result = verify_citation(_doc(), page=1, claimed_quote="assessed on an own occupation basis")
    assert result.verified is True
    assert result.reason == "exact_substring"
    assert result.match_score == 1.0


def test_reworded_but_similar_quote_verifies_via_fuzzy_match():
    # Same meaning, slightly different words/punctuation than the source.
    reworded = "assessed on an own-occupation basis"
    result = verify_citation(_doc(), page=1, claimed_quote=reworded)
    assert result.verified is True
    assert result.reason == "fuzzy_match"
    assert result.match_score >= 0.85


def test_fabricated_unrelated_quote_fails():
    result = verify_citation(_doc(), page=1, claimed_quote="premiums are waived after five years of cancer")
    assert result.verified is False
    assert result.reason == "no_match"


def test_out_of_range_page_returns_section_not_found():
    result = verify_citation(_doc(page_number=1), page=99, claimed_quote="anything")
    assert result.verified is False
    assert result.reason == "section_not_found"


def test_empty_quote_does_not_verify():
    result = verify_citation(_doc(), page=1, claimed_quote="   ")
    assert result.verified is False
    assert result.reason == "no_match"
