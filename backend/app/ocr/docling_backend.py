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
persistent volume after first use).

Real production incident (2026-07-30): a real document (likely a scanned/
legacy PDF from Asteron Life's investment-fund archive) hung Docling for
35+ minutes with near-zero CPU usage - a genuine hang, not just slow
processing, and not something the per-document try/except in run_ingest.py
could catch (a hung call never raises). extract_structured() now runs the
actual conversion in a subprocess with a hard wall-clock timeout, so a
stuck document degrades to a typed TimeoutError - handled by run_ingest.py
exactly like any other per-document failure - instead of hanging the whole
batch indefinitely.
"""

from __future__ import annotations

import io
import multiprocessing

from app.ocr.types import ParsedDocument, ParsedPage, TextBlock

DEFAULT_TIMEOUT_SECONDS = 120.0


def _extract_structured_impl(pdf_bytes: bytes) -> ParsedDocument:
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


def _subprocess_entry(pdf_bytes: bytes, queue: "multiprocessing.Queue", impl) -> None:
    try:
        queue.put(("ok", impl(pdf_bytes)))
    except Exception as exc:  # noqa: BLE001 - reraised in the parent, not swallowed
        queue.put(("error", exc))


def extract_structured(
    pdf_bytes: bytes,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    impl=_extract_structured_impl,
) -> ParsedDocument:
    """Runs the real conversion in a subprocess so a stuck document can
    actually be killed - a hang inside Docling/its layout model has no
    other reliable interrupt point (it's CPU-bound, so a thread-based
    timeout can't preempt it either). Raises TimeoutError, not a crash, so
    callers (run_ingest.py's per-document try/except) handle it exactly
    like any other extraction failure.

    `impl` is injectable (must be a module-level function, not a lambda/
    closure - the "spawn" context re-imports it by reference in the child
    process) so the timeout behavior itself can be unit-tested with a fake
    slow function instead of real Docling."""
    ctx = multiprocessing.get_context("spawn")
    queue: multiprocessing.Queue = ctx.Queue()
    process = ctx.Process(target=_subprocess_entry, args=(pdf_bytes, queue, impl))
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
        raise TimeoutError(f"Docling extraction timed out after {timeout_seconds}s")

    if queue.empty():
        raise RuntimeError(
            f"Docling subprocess exited (code {process.exitcode}) without a result - "
            "likely killed by an out-of-memory condition"
        )
    status, payload = queue.get()
    if status == "error":
        raise payload
    return payload
