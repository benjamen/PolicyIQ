"""Tests the subprocess-based timeout wrapper around Docling itself
(real-Docling invocation stays in test_docling_backend.py, skipped by
default). Real production incident (2026-07-30): a real document hung
Docling for 35+ minutes with near-zero CPU usage - a genuine hang that a
per-document try/except can't catch, since a hung call never raises.

`impl` functions here are module-level (not lambdas/closures) on purpose -
multiprocessing's "spawn" context re-imports them by qualified name in the
child process, so a closure or lambda can't be pickled across that
boundary."""

import time

import pytest

from app.ocr.docling_backend import extract_structured
from app.ocr.types import ParsedDocument, ParsedPage, TextBlock


def _fake_fast_impl(pdf_bytes: bytes) -> ParsedDocument:
    return ParsedDocument(
        pages=(ParsedPage(page_number=1, text_blocks=(TextBlock(text="ok", bbox=(0, 0, 0, 0), paragraph_ref="1.1"),), native_text_coverage=0.0),),
        backend_used="docling",
    )


def _fake_hung_impl(pdf_bytes: bytes) -> ParsedDocument:
    time.sleep(60)
    raise AssertionError("should have been killed before returning")


def _fake_failing_impl(pdf_bytes: bytes) -> ParsedDocument:
    raise ValueError("simulated real Docling conversion error")


def test_fast_extraction_returns_normally():
    result = extract_structured(b"fake pdf bytes", timeout_seconds=10, impl=_fake_fast_impl)

    assert result.backend_used == "docling"
    assert len(result.pages) == 1


def test_hung_extraction_is_killed_and_raises_timeout_error():
    start = time.monotonic()

    with pytest.raises(TimeoutError, match="timed out after"):
        extract_structured(b"fake pdf bytes", timeout_seconds=2, impl=_fake_hung_impl)

    elapsed = time.monotonic() - start
    assert elapsed < 10, "should be killed close to the timeout, not wait for the full 60s sleep"


def test_a_real_exception_in_the_subprocess_is_reraised_in_the_parent():
    with pytest.raises(ValueError, match="simulated real Docling conversion error"):
        extract_structured(b"fake pdf bytes", timeout_seconds=10, impl=_fake_failing_impl)
