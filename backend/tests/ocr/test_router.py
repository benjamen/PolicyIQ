from app.ocr.router import route_ocr
from app.ocr.types import ParsedDocument, ParsedPage, TextBlock

_NATIVE_RESULT = ParsedDocument(
    pages=(ParsedPage(page_number=1, text_blocks=(TextBlock("native", (0, 0, 1, 1), "1.1"),), native_text_coverage=1.0),),
    backend_used="pymupdf",
)
_STRUCTURED_RESULT = ParsedDocument(
    pages=(ParsedPage(page_number=1, text_blocks=(TextBlock("structured", (0, 0, 1, 1), "1.1"),), native_text_coverage=0.0),),
    backend_used="docling",
)


def test_uses_native_result_when_available():
    calls = {"structured": 0}

    def fake_native(_pdf_bytes):
        return _NATIVE_RESULT

    def fake_structured(_pdf_bytes):
        calls["structured"] += 1
        return _STRUCTURED_RESULT

    result = route_ocr(b"fake-pdf-bytes", native_extractor=fake_native, structured_extractor=fake_structured)

    assert result.backend_used == "pymupdf"
    assert calls["structured"] == 0  # never falls through when native succeeds


def test_falls_through_to_structured_when_native_returns_none():
    def fake_native(_pdf_bytes):
        return None

    def fake_structured(_pdf_bytes):
        return _STRUCTURED_RESULT

    result = route_ocr(b"fake-pdf-bytes", native_extractor=fake_native, structured_extractor=fake_structured)

    assert result.backend_used == "docling"
