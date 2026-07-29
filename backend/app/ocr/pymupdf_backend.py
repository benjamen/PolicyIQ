"""Fast path: PyMuPDF's native text layer. Per docs/05-AI-EXTRACTION-
STRATEGY.md, only used when the PDF has a usable native text layer covering
>=95% of pages with real (non-garbled) text - otherwise route_ocr() (router.py)
falls through to the Docling structured/OCR path."""

from __future__ import annotations

import fitz  # PyMuPDF

from app.ocr.types import ParsedDocument, ParsedPage, TextBlock

_MIN_CHARS_FOR_REAL_TEXT = 20
_NATIVE_TEXT_COVERAGE_THRESHOLD = 0.95


def extract_native(pdf_bytes: bytes) -> ParsedDocument | None:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        pages: list[ParsedPage] = []
        pages_with_real_text = 0

        for page_index in range(doc.page_count):
            page = doc[page_index]
            page_number = page_index + 1
            raw_blocks = page.get_text("blocks")

            text_blocks: list[TextBlock] = []
            page_char_count = 0
            for block_index, raw in enumerate(raw_blocks):
                x0, y0, x1, y1, text, *_rest = raw
                text = text.strip()
                if not text:
                    continue
                page_char_count += len(text)
                text_blocks.append(
                    TextBlock(
                        text=text,
                        bbox=(x0, y0, x1, y1),
                        paragraph_ref=f"{page_number}.{block_index + 1}",
                    )
                )

            if page_char_count >= _MIN_CHARS_FOR_REAL_TEXT:
                pages_with_real_text += 1

            pages.append(
                ParsedPage(
                    page_number=page_number,
                    text_blocks=tuple(text_blocks),
                    native_text_coverage=1.0 if page_char_count >= _MIN_CHARS_FOR_REAL_TEXT else 0.0,
                )
            )

        if doc.page_count == 0:
            return None

        overall_coverage = pages_with_real_text / doc.page_count
        if overall_coverage < _NATIVE_TEXT_COVERAGE_THRESHOLD:
            return None

        return ParsedDocument(pages=tuple(pages), backend_used="pymupdf")
    finally:
        doc.close()
