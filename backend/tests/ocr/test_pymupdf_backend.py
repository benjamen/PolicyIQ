import fitz

from app.ocr.pymupdf_backend import extract_native


def _pdf_with_pages(texts: list[str]) -> bytes:
    doc = fitz.open()
    for text in texts:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_extracts_native_text_when_coverage_is_high():
    pdf_bytes = _pdf_with_pages(
        [
            "This is a real sentence with enough characters on page one.",
            "This is a real sentence with enough characters on page two.",
        ]
    )
    result = extract_native(pdf_bytes)
    assert result is not None
    assert result.backend_used == "pymupdf"
    assert len(result.pages) == 2
    assert "page one" in result.page(1).text
    assert "page two" in result.page(2).text


def test_returns_none_when_coverage_below_threshold():
    doc = fitz.open()
    doc.new_page()  # page 1: blank, no text
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Only this page has real, substantial text content.")
    pdf_bytes = doc.tobytes()
    doc.close()

    result = extract_native(pdf_bytes)
    assert result is None  # 1/2 pages with real text = 50% < 95% threshold
