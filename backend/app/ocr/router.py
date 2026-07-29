"""Routes a PDF to the fast PyMuPDF native-text path when available, else
Docling's structured/OCR path - per docs/05-AI-EXTRACTION-STRATEGY.md."""

from __future__ import annotations

from typing import Callable

from app.ocr.docling_backend import extract_structured
from app.ocr.pymupdf_backend import extract_native
from app.ocr.types import ParsedDocument


def route_ocr(
    pdf_bytes: bytes,
    *,
    native_extractor: Callable[[bytes], ParsedDocument | None] = extract_native,
    structured_extractor: Callable[[bytes], ParsedDocument] = extract_structured,
) -> ParsedDocument:
    native_result = native_extractor(pdf_bytes)
    if native_result is not None:
        return native_result
    return structured_extractor(pdf_bytes)
