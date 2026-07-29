"""Generic per-insurer document-discovery spider.

One spider class driven by registry config, not a bespoke spider per
insurer - the crawler strategy calls for a maintained per-insurer *rule
set* (doc-type keywords, allowed paths), not duplicated crawl logic. Run
one insurer at a time: `scrapy crawl policy_documents -a insurer="AIA New Zealand"`.

Discovery order per docs/04-CRAWLER-STRATEGY.md: sitemap.xml first (cheap,
most sites have one), falling back to following in-domain links up to
DEPTH_LIMIT (settings.py) for sites that need it. This spider handles the
link-following fallback and PDF extraction. Playwright rendering for JS-only
nav (docs/04-CRAWLER-STRATEGY.md: "static fetch tried first, per URL...
Playwright only engages when a page requires JS rendering") is a per-URL
fallback, not a whole-crawl heuristic: any single response with too few
links to be real navigation gets retried once, rendered, before the crawl
moves on. Confirmed necessary against a real site (2026-07-29): Partners
Life's homepage is a Vue SPA shell with zero <a href> tags anywhere in the
raw HTML - real nav only exists after client-side rendering.

This uses a real, honestly-identified headless Chromium (same USER_AGENT
as every other request, see settings.py) - no CDP-hiding, no fingerprint
spoofing, no stealth plugins. It is not expected to (and isn't meant to)
get past a site's deliberate anti-automation controls (e.g. AIA's WAF,
which resets the HTTP/2 stream before any static request even completes) -
that's a different, out-of-scope problem this fallback doesn't touch.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

import scrapy

from policyiq_crawler.doctype import classify
from policyiq_crawler.items import DiscoveredDocumentItem
from policyiq_crawler.registry import discover_insurers


class PolicyDocumentSpider(scrapy.Spider):
    name = "policy_documents"

    # Literally zero links, matching the confirmed Partners Life evidence
    # exactly - conservative on purpose, not a tunable per-insurer knob yet
    # since only one insurer is confirmed to need this.
    link_count_threshold = 1

    def __init__(self, insurer: str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not insurer:
            raise ValueError(
                "Pass -a insurer=\"<name>\" matching an entry in registry.LIFE_INSURER_SEED"
            )

        matches = [i for i in discover_insurers() if i.name == insurer]
        if not matches:
            known = ", ".join(i.name for i in discover_insurers())
            raise ValueError(f"Unknown insurer '{insurer}'. Known insurers: {known}")

        self.insurer_seed = matches[0]
        self.start_urls = [self.insurer_seed.website_root]
        domain = urlparse(self.insurer_seed.website_root).netloc
        self.allowed_domains = [domain]

        self.custom_settings = {
            "DOWNLOAD_DELAY": self.insurer_seed.crawl_policy.request_delay_seconds,
        }

    def parse(self, response: scrapy.http.Response):
        if response.headers.get("Content-Type", b"").decode().startswith("application/pdf"):
            return
        yield from self._extract_links(response)

    def _extract_links(self, response: scrapy.http.Response):
        """Shared PDF/link extraction - identical whether `response` came
        from the plain downloader or a Playwright-rendered page (scrapy-
        playwright still returns a normal TextResponse)."""
        links = response.css("a[href]")

        already_rendered = response.meta.get("playwright", False)
        if not already_rendered and len(links) < self.link_count_threshold:
            self.logger.info(
                "Only %d link(s) found statically at %s; retrying with Playwright",
                len(links), response.url,
            )
            yield scrapy.Request(
                response.url,
                callback=self.parse,
                meta={"playwright": True},
                # Same URL, different rendering path - must bypass
                # RFPDupeFilter or this retry is silently dropped as a
                # "duplicate" of the request that just returned 0 links.
                dont_filter=True,
            )
            return

        for link in links:
            href = link.attrib.get("href", "")
            text = " ".join(link.css("::text").getall()).strip()
            if not href:
                continue

            absolute_url = response.urljoin(href)

            if absolute_url.lower().endswith(".pdf") or "content-type" in href.lower():
                yield DiscoveredDocumentItem(
                    insurer=self.insurer_seed.name,
                    source_page_url=response.url,
                    document_url=absolute_url,
                    link_text=text,
                    doc_type_guess=classify(text, absolute_url),
                    discovered_at=datetime.now(timezone.utc).isoformat(),
                )
            elif urlparse(absolute_url).netloc == self.allowed_domains[0]:
                yield response.follow(absolute_url, callback=self.parse)
