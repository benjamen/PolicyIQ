"""Real Docling invocation - skipped by default. Docling's layout model
downloads from Hugging Face Hub on first use; network-restricted sandboxes
(confirmed: this dev environment) can't reach it. Run explicitly
(`pytest -m docling`) somewhere with real internet access and a writable
model cache once that's available - e.g. baked into the production image."""

import pytest

pytestmark = pytest.mark.skip(
    reason="Docling's layout model requires downloading from huggingface.co on first "
    "use; this environment's network policy blocks that host. Run with real internet "
    "access (e.g. the deployed container) once the model cache is warmed."
)


def test_extract_structured_on_synthetic_pdf():
    import fitz

    from app.ocr.docling_backend import extract_structured

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Docling structured extraction smoke test.")
    pdf_bytes = doc.tobytes()
    doc.close()

    result = extract_structured(pdf_bytes)
    assert result.backend_used == "docling"
    assert len(result.pages) >= 1
