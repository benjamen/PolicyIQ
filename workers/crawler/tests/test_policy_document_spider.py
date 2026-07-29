import scrapy

from policyiq_crawler.items import DiscoveredDocumentItem
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

    # Only the same-domain, non-PDF link gets followed - the external one does not.
    assert len(requests) == 1
    assert requests[0].url == "https://www.partnerslife.co.nz/about"


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
