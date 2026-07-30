from policyiq_crawler.doctype import classify


def test_classifies_pds_by_link_text():
    assert classify("Product Disclosure Statement", "/docs/life-pds.pdf") == "pds"


def test_classifies_wording_by_url_when_text_is_generic():
    assert classify("Download", "/documents/policy-wording-2026.pdf") == "wording"


def test_unknown_when_nothing_matches():
    assert classify("Read more", "/about-us") == "unknown"


def test_claims_guide_detected():
    assert classify("How to make a claim", "/claims/guide.pdf") == "claims_guide"


def test_annual_report_detected():
    """Real noise hit crawling Fidelity Life (2026-07-30): a company
    annual report PDF has zero policy content but is expensive to
    download/OCR/extract - flagged out of scope in registry.py."""
    assert classify("Fidelity Life Annual Report", "/media/xyz/fidelity-life-annual-report-2024.pdf") == "annual_report"


def test_corporate_comms_detected():
    """Real noise hit crawling Asteron Life (2026-07-31): investor news,
    media releases, whistleblowing policy, SME Index research reports -
    real Asteron Life content, but corporate communications, not
    insurance policy content."""
    assert classify("", "/documents/Asteron-Life-Investor-News-Issue-27.pdf") == "corporate_comms"
    assert classify("", "/documents/Whistleblowing-Policy-2025.pdf") == "corporate_comms"


def test_investment_or_kiwisaver_takes_priority_over_pds():
    """Real gap found crawling MAS (2026-07-31): a KiwiSaver Product
    Disclosure Statement also contains the literal phrase "product
    disclosure statement", which would otherwise match "pds" - dict
    order must check out-of-vertical categories first."""
    assert classify("", "/documents/639/MAS_KiwiSaver_Scheme_Product_Disclosure_Statement.pdf") == "investment_or_kiwisaver"


def test_general_insurance_takes_priority_over_wording():
    """Real gap found crawling MAS (2026-07-31): a Contents Insurance
    Policy Document also contains the literal phrase "policy document",
    which would otherwise match "wording"."""
    assert classify("", "/documents/1103/MAS_Contents_Insurance_Policy_Document.pdf") == "general_insurance"
