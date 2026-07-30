import asyncio

import scrapy

from policyiq_crawler.items import DiscoveredDocumentItem
from policyiq_crawler.registry import DEFAULT_DOCUMENT_HUB_PATHS
from policyiq_crawler.spiders.policy_document_spider import PolicyDocumentSpider

_URL = "https://www.partnerslife.co.nz/"


def _drain_async_gen(agen):
    """Scrapy 2.13+'s `Spider.start()` is an async generator - the real
    crawl engine drives it with `anext()` in an event loop. Calling it as
    a plain sync method (as an earlier version of this test did, against
    the old `start_requests()` name) only proves the method body runs; it
    proves nothing about what the actual engine will do, since Scrapy
    2.17 never calls a spider's `start_requests()` at all (confirmed:
    base Spider has no such attribute)."""

    async def _collect():
        return [item async for item in agen]

    return asyncio.run(_collect())


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


def test_annual_reports_are_flagged_out_of_scope_not_dropped():
    """Real noise hit crawling Fidelity Life (2026-07-30): an annual
    report PDF has zero policy content but is expensive to download/OCR/
    extract - a 45+ minute real run confirmed via docker top + /proc
    inspection to be genuinely churning through one, not hung."""
    body = '<html><body><a href="/media/xyz/fidelity-life-annual-report-2024.pdf">Fidelity Life Annual Report</a></body></html>'
    response = _make_response(body)

    results = list(_spider().parse(response))
    items = [r for r in results if isinstance(r, DiscoveredDocumentItem)]

    assert len(items) == 1
    assert items[0].get("doc_type_guess") == "annual_report"
    assert items[0].get("in_scope") is False


def test_out_of_path_pdfs_are_flagged_out_of_scope_and_pages_are_not_followed():
    """Real gap found crawling Chubb Life NZ (2026-07-30/31): chubb.com
    shares one domain, one AEM content repository, and one site across
    every country AND every Chubb NZ product line (property, travel,
    cyber, aviation), not just life. allowed_paths (registry.py, scoped
    to the actual retail life product) must be enforced both for document
    scoping AND for whether a same-domain page even gets followed at all
    - the second part matters more: without it, the crawl wastes real
    requests/time wandering the whole multinational/multi-product site
    before any per-document scoping ever runs."""
    chubb_url = "https://www.chubb.com/nz-en/"
    body = (
        '<html><body>'
        '<a href="/content/dam/chubb-sites/chubb-com/us-en/some-us-campaign.pdf">US PDF</a>'
        '<a href="/nz-en/business/aviation-insurance/">NZ general-insurance page</a>'
        '<a href="/nz-en/life/life-and-living/critical-illness-cover.html">NZ life page</a>'
        '</body></html>'
    )
    request = scrapy.Request(url=chubb_url)
    response = scrapy.http.HtmlResponse(url=chubb_url, body=body.encode("utf-8"), encoding="utf-8", request=request)

    spider = PolicyDocumentSpider(insurer="Chubb Life NZ")
    results = list(spider.parse(response))
    items = [r for r in results if isinstance(r, DiscoveredDocumentItem)]
    requests = [r for r in results if isinstance(r, scrapy.Request)]

    assert len(items) == 1
    assert items[0].get("in_scope") is False

    # Only the /nz-en/life/... page gets followed - the /nz-en/business/...
    # one, same domain and same country, but a different (general-
    # insurance) product line, is never even requested.
    assert len(requests) == 1
    assert requests[0].url == "https://www.chubb.com/nz-en/life/life-and-living/critical-illness-cover.html"


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


def test_known_document_urls_are_yielded_directly_as_discovered_items():
    """Real gap found crawling Fidelity Life (2026-07-30): its actual
    policy-wording PDFs exist on its own domain but aren't linked from any
    page within crawl depth - only search-engine-indexed. registry.py's
    known_document_urls seeds these directly; start() must turn
    each into a DiscoveredDocumentItem, not a page-fetch (parse() drops
    PDF responses outright, so routing these through the normal page-fetch
    path would silently lose every one of them)."""
    spider = PolicyDocumentSpider(insurer="Fidelity Life")

    results = _drain_async_gen(spider.start())
    items = [r for r in results if isinstance(r, DiscoveredDocumentItem)]
    page_requests = [r for r in results if isinstance(r, scrapy.Request)]

    known_urls = spider.insurer_seed.crawl_policy.known_document_urls
    assert len(known_urls) > 0
    assert {i.get("document_url") for i in items} == set(known_urls)
    assert all(i.get("in_scope") is True for i in items)
    assert len(page_requests) == len(spider.start_urls)


def test_smeindex_documents_are_flagged_out_of_scope_not_dropped():
    """Real noise hit crawling Asteron Life (2026-07-31): the /documents/
    SMEIndex/ directory held 14+ small-business research reports spanning
    2018-2023, none of them insurance product content - a sibling problem
    to the existing /investments/ exclusion."""
    body = (
        '<html><body>'
        '<a href="/sites/default/files/documents/SMEIndex/asteron-life-sme-index-2023.pdf">'
        'SME Index 2023</a>'
        '</body></html>'
    )
    request = scrapy.Request(url="https://www.asteronlife.co.nz/")
    response = scrapy.http.HtmlResponse(
        url="https://www.asteronlife.co.nz/", body=body.encode("utf-8"), encoding="utf-8", request=request
    )

    spider = PolicyDocumentSpider(insurer="Asteron Life")
    results = list(spider.parse(response))
    items = [r for r in results if isinstance(r, DiscoveredDocumentItem)]

    assert len(items) == 1
    assert items[0].get("in_scope") is False
