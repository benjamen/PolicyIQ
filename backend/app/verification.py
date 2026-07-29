"""Citation verification - the mechanism behind "never hallucinate"
(docs/05-AI-EXTRACTION-STRATEGY.md): a mechanical gate the system enforces,
not a prompt instruction trusted at face value. Direct-quote mode only this
pass - every fact in app/providers/llm.py's schema carries a verbatim
source_quote, so exact-substring + fuzzy-match against the parsed page text
covers everything currently in scope. The paraphrase/entailment mode
docs/05 also describes is deferred (verify_entailment stub below) -
building it against a mock LLM would produce a fake confidence number with
no real signal behind it, which is exactly what fail-closed argues against.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Literal

from app.ocr.types import ParsedDocument

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip().lower()


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    match_score: float
    reason: Literal["exact_substring", "fuzzy_match", "no_match", "section_not_found"]


def verify_citation(
    parsed_document: ParsedDocument,
    *,
    page: int,
    claimed_quote: str,
    threshold: float = 0.85,
) -> VerificationResult:
    parsed_page = parsed_document.page(page)
    if parsed_page is None:
        return VerificationResult(verified=False, match_score=0.0, reason="section_not_found")

    page_text = _normalize(parsed_page.text)
    quote = _normalize(claimed_quote)

    if not quote:
        return VerificationResult(verified=False, match_score=0.0, reason="no_match")

    if quote in page_text:
        return VerificationResult(verified=True, match_score=1.0, reason="exact_substring")

    score = _best_fuzzy_ratio(quote, page_text)
    if score >= threshold:
        return VerificationResult(verified=True, match_score=score, reason="fuzzy_match")

    return VerificationResult(verified=False, match_score=score, reason="no_match")


def _best_fuzzy_ratio(quote: str, page_text: str) -> float:
    """Slides a window the size of `quote` across `page_text` and returns the
    best difflib ratio - a whole-page ratio alone penalizes a short true
    quote inside a long page too harshly to be useful."""
    if len(page_text) <= len(quote):
        return difflib.SequenceMatcher(None, quote, page_text).ratio()

    window = len(quote)
    step = max(1, window // 4)
    best = 0.0
    for start in range(0, len(page_text) - window + 1, step):
        candidate = page_text[start : start + window]
        ratio = difflib.SequenceMatcher(None, quote, candidate).ratio()
        best = max(best, ratio)
    return best


def verify_entailment(*_args, **_kwargs) -> VerificationResult:
    """Deferred: paraphrase/entailment verification needs a real LLM call to
    produce a meaningful confidence signal - building it against a mock
    would fabricate a number with no real signal behind it. Not needed this
    pass since every fact in scope carries a verbatim source_quote."""
    raise NotImplementedError(
        "verify_entailment is deferred until a real LLM provider exists to calibrate it "
        "(see app/providers/llm.py) - all facts in this pass's schema use verify_citation instead"
    )
