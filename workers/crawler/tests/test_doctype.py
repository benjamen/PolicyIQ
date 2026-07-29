from policyiq_crawler.doctype import classify


def test_classifies_pds_by_link_text():
    assert classify("Product Disclosure Statement", "/docs/life-pds.pdf") == "pds"


def test_classifies_wording_by_url_when_text_is_generic():
    assert classify("Download", "/documents/policy-wording-2026.pdf") == "wording"


def test_unknown_when_nothing_matches():
    assert classify("Read more", "/about-us") == "unknown"


def test_claims_guide_detected():
    assert classify("How to make a claim", "/claims/guide.pdf") == "claims_guide"
