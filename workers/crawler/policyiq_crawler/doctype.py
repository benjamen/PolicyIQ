"""Document-type classification heuristics (docs/04-CRAWLER-STRATEGY.md:
"a maintained per-insurer rule set, not a single generic regex" - this is
that rule set's shared core; insurer-specific overrides can extend
PATTERNS without touching the spider).

Kept deliberately simple keyword matching for now. Anything that doesn't
match confidently returns "unknown" and is routed to admin review rather
than guessed - see docs/04-CRAWLER-STRATEGY.md classification section.
"""

from __future__ import annotations

PATTERNS: dict[str, tuple[str, ...]] = {
    # Out-of-vertical categories checked first, deliberately - real gap found
    # 2026-07-31 (MAS): "MAS_Contents_Insurance_Policy_Document.pdf" and
    # "MAS_KiwiSaver_Scheme_Product_Disclosure_Statement.pdf" both also
    # contain "policy document"/"product disclosure statement" (matching
    # "wording"/"pds" below), and dict iteration order determines which
    # category wins first - these must be classified as out-of-vertical
    # before the generic wording/pds keywords ever get a chance to match.
    "corporate_comms": (
        "investor news", "media release", "media statement", "whistleblowing",
        "climate disclosure", "fair conduct programme", "sme index", "board and leadership",
        "completes acquisition", "product updates and enhancements", "passback",
        "onmas", "chairman report", "foundation report",
    ),
    "investment_or_kiwisaver": (
        "kiwisaver", "retirement savings", "investment fund", "sipo",
        "fund update", "fund holding", "financial statement",
    ),
    "general_insurance": (
        "contents insurance", "house insurance", "business risks", "cyber insurance",
    ),
    "pds": ("product disclosure statement", "pds"),
    "wording": ("policy wording", "policy document", "terms and conditions"),
    "brochure": ("brochure", "product guide", "at a glance", "fact sheet"),
    "claims_guide": ("claims guide", "claim guide", "how to claim", "making a claim", "how to make a claim"),
    "underwriting_guide": ("underwriting guide", "adviser guide", "underwriting manual"),
    "form": ("application form", "claim form", "change of details"),
    "renewal_doc": ("renewal notice", "renewal terms"),
    "faq": ("frequently asked questions", "faq"),
    "annual_report": ("annual report", "annual statement", "investor report"),
}

_SEPARATORS = str.maketrans("-_/", "   ")


def classify(link_text: str, url: str) -> str:
    """Keyword match against link text + URL. URL path separators (-, _, /)
    are normalized to spaces first so "policy-wording.pdf" matches the same
    phrase patterns as human-readable link text. Dict order matters - see
    the out-of-vertical comment above PATTERNS."""
    haystack = f"{link_text} {url}".lower().translate(_SEPARATORS)
    for doc_type, keywords in PATTERNS.items():
        if any(keyword in haystack for keyword in keywords):
            return doc_type
    return "unknown"
