import scrapy

from policyiq_crawler.items import DiscoveredDocumentItem
from policyiq_crawler.registry import DEFAULT_DOCUMENT_HUB_PATHS
from policyiq_crawler.spiders.policy_document_spider import PolicyDocumentSpider

_URL = "https://www.partnerslife.co.nz/"


def _make_response(body: str, *, playwright_rendered: bool = False) -> scrapy.http.HtmlResponse:
    request = scrapy.Request(url=_URL, meta={"playwright": playwright_rendered})
    return scrapy.http.HtmlResponse(
        url=_URL, body=body.encode("utf-8"), encoding="utf-8", request=request
    )


def _spider() -> PolicyDocumentSpider:
    return PolicyDocumentSpider(insurer="Partners Life")


def test_extracts_pdf_links_and_follows_same_domain_links_only():
    body = """
    <html><body>
        <a href="/policies/life-pds.pdf">Life PDS</a>
        <a href="/about">About Us</a>
        <a href="https://external.example.com/x">External</a>
    </body></html>
    """
    response = _make_response(body)

    results = list(_spider().parse(response))

    items = [r for r in results if isinstance(r, DiscoveredDocumentItem)]
    requests = [r for r in results if isinstance(r, scrapy.Request)]

    assert len(items) == 1
    assert items[0].get("document_url") == "https://www.partnerslife.co.nz/policies/life-pds.pdf"
    assert items[0].get("in_scope") is True

    # Only the same-domain, non-PDF link gets followed - the external one does not.
    assert len(requests) == 1
    assert requests[0].url == "https://www.partnerslife.co.nz/about"


def test_claim_forms_are_flagged_out_of_scope_not_dropped():
    """Claim/application forms are real, correctly-discovered documents -
    just not useful for comparing coverage terms. Flagged, still yielded."""
    body = '<html><body><a href="/forms/life-claim-form.pdf">Life Claim Form</a></body></html>'
    response = _make_response(body)

    results = list(_spider().parse(response))
    items = [r for r in results if isinstance(r, DiscoveredDocumentItem)]

    assert len(items) == 1
    assert items[0].get("doc_type_guess") == "form"
    assert items[0].get("in_scope") is False


def test_known_noise_paths_are_flagged_out_of_scope_not_dropped():
    """Real noise hit crawling Asteron Life (2026-07-29): a large archive
    of old investment/superannuation fund documents under /investments/ -
    live, real documents, just irrelevant to this vertical slice."""
    body = (
        '<html><body>'
        '<a href="/sites/default/files/documents/investments/some-fund-2019.pdf">'
        'Some Fund Annual Report</a>'
        '</body></html>'
    )
    response = _make_response(body)

    results = list(_spider().parse(response))
    items = [r for r in results if isinstance(r, DiscoveredDocumentItem)]

    assert len(items) == 1
    assert items[0].get("in_scope") is False


def test_off_domain_pdfs_are_flagged_out_of_scope_not_dropped():
    """Real noise hit crawling Fidelity Life (2026-07-30): its own site
    linked an FMA (regulator) licensing PDF, off fidelitylife.co.nz
    entirely - a third party's document is never the insurer's own
    policy wording, no matter what the link text says. Still yielded,
    same flagged-not-dropped pattern as claim forms / noise paths."""
    body = (
        '<html><body>'
        '<a href="https://www.fma.govt.nz/assets/some-licensing-guide.pdf">'
        'Standard Conditions for full FAP licences</a>'
        '</body></html>'
    )
    response = _make_response(body)

    results = list(_spider().parse(response))
    items = [r for r in results if isinstance(r, DiscoveredDocumentItem)]

    assert len(items) == 1
    assert items[0].get("document_url") == "https://www.fma.govt.nz/assets/some-licensing-guide.pdf"
    assert items[0].get("in_scope") is False


def test_zero_links_on_a_static_response_retries_with_playwright():
    body = "<html><body>No links here at all - just an empty SPA shell.</body></html>"
    response = _make_response(body, playwright_rendered=False)

    results = list(_spider().parse(response))

    assert len(results) == 1
    assert isinstance(results[0], scrapy.Request)
    assert results[0].url == _URL
    assert results[0].meta.get("playwright") is True
    assert results[0].dont_filter is True


def test_zero_links_on_an_already_rendered_response_does_not_retrigger_playwright():
    """The loop-guard: a Playwright-rendered response with genuinely zero
    links (e.g. a real empty page) must not retry itself forever."""
    body = "<html><body>Still no links, even after rendering.</body></html>"
    response = _make_response(body, playwright_rendered=True)

    results = list(_spider().parse(response))

    assert results == []


def test_start_urls_include_the_homepage_and_every_document_hub_path():
    """No government registry cross-references policy wordings (researched
    2026-07-30) - each insurer's own site is the only source, and a
    homepage-rooted crawl alone can miss a real documents hub (confirmed:
    Asteron Life's /important-information wasn't reachable via link-
    following). So every insurer's likely hub paths get seeded directly,
    not just the homepage."""
    spider = _spider()

    assert spider.start_urls[0] == "https://www.partnerslife.co.nz"
    for path in DEFAULT_DOCUMENT_HUB_PATHS:
        assert f"https://www.partnerslife.co.nz{path}" in spider.start_urls
    assert len(spider.start_urls) == 1 + len(DEFAULT_DOCUMENT_HUB_PATHS)
