"""Structured/OCR fallback path via Docling, used when PyMuPDF's native text
layer coverage check fails (pymupdf_backend.py). Tables are serialized to
markdown and kept as a single TextBlock so they're never split mid-table
(docs/05-AI-EXTRACTION-STRATEGY.md's chunking rule).

Docling's layout model downloads from Hugging Face Hub on first use - this
call is untestable in network-restricted sandboxes (confirmed this session:
403 at the egress proxy for huggingface.co, even with do_ocr=False, since
the layout model itself - not just OCR - is a required download). Real
invocation needs to happen somewhere with real internet access (e.g. the
production container, where the model gets cached into the image or a
persistent volume after first use)."""

from __future__ import annotations

import io

from app.ocr.types import ParsedDocument, ParsedPage, TextBlock


def extract_structured(pdf_bytes: bytes) -> ParsedDocument:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.io import DocumentStream

    pipeline_options = PdfPipelineOptions(do_ocr=True)
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )
    result = converter.convert(DocumentStream(name="document.pdf", stream=io.BytesIO(pdf_bytes)))
    doc = result.document

    blocks_by_page: dict[int, list[TextBlock]] = {}

    def _add_block(page_no: int, text: str, bbox: tuple[float, float, float, float], ref_index: int) -> None:
        blocks_by_page.setdefault(page_no, []).append(
            TextBlock(text=text, bbox=bbox, paragraph_ref=f"{page_no}.{ref_index}")
        )

    counters: dict[int, int] = {}
    for item in doc.texts:
        text = (item.text or "").strip()
        if not text or not item.prov:
            continue
        prov = item.prov[0]
        page_no = prov.page_no
        counters[page_no] = counters.get(page_no, 0) + 1
        bbox = (prov.bbox.l, prov.bbox.t, prov.bbox.r, prov.bbox.b) if prov.bbox else (0.0, 0.0, 0.0, 0.0)
        _add_block(page_no, text, bbox, counters[page_no])

    for table in doc.tables:
        if not table.prov:
            continue
        prov = table.prov[0]
        page_no = prov.page_no
        counters[page_no] = counters.get(page_no, 0) + 1
        bbox = (prov.bbox.l, prov.bbox.t, prov.bbox.r, prov.bbox.b) if prov.bbox else (0.0, 0.0, 0.0, 0.0)
        markdown = table.export_to_markdown()
        _add_block(page_no, markdown, bbox, counters[page_no])

    page_numbers = sorted(blocks_by_page) or [1]
    pages = tuple(
        ParsedPage(
            page_number=page_no,
            text_blocks=tuple(blocks_by_page.get(page_no, [])),
            native_text_coverage=0.0,
        )
        for page_no in page_numbers
    )
    return ParsedDocument(pages=pages, backend_used="docling")
