import fitz
import pytest

_SAMPLE_TEXT = (
    "Total and Permanent Disability means the life insured is unable to perform their own "
    "occupation. This policy is available to applicants aged 18 to 65, smoker or non-smoker."
)


@pytest.fixture
def synthetic_pdf_bytes() -> bytes:
    """A one-page, native-text PDF - real bytes, no network, Docling never invoked.

    insert_text() silently drops whatever doesn't fit on the line (it does not
    wrap); insert_textbox() wraps within a rect instead, so the full text lands
    on the page regardless of length.
    """
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(72, 72, 523, 770), _SAMPLE_TEXT, fontsize=10)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
