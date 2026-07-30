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

Also seeds each insurer's likely documents-hub page (registry.py's
DEFAULT_DOCUMENT_HUB_PATHS) as additional start_urls, not just the
homepage. Researched 2026-07-30: no NZ government registry exists for
life/trauma/TPD/income-protection policy wordings (unlike KiwiSaver,
which must file on the Companies Office Disclose Register) - each
insurer's own site is genuinely the only source, and a homepage-rooted
crawl alone can miss a real documents hub that isn't linked prominently
from anywhere the homepage leads within DEPTH_LIMIT (confirmed: Asteron
Life's /important-information page is real, live content, but wasn't
reachable via link-following in this crawl's first real run).

That same run also surfaced real noise: hub-path seeding found a large
archive of old (2017-2019) investment/superannuation fund documents that
have nothing to do with life/trauma/TPD/income-protection cover. Every
discovered document now carries an `in_scope` flag (registry.py's
OUT_OF_SCOPE_DOC_TYPES/excluded_path_substrings) - flagged, not dropped
at discovery time (still visible in the crawl output), so downstream
processing can skip spending download/OCR/LLM time on documents this
vertical slice doesn't need.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import scrapy

from policyiq_crawler.doctype import classify
from policyiq_crawler.items import DiscoveredDocumentItem
from policyiq_crawler.registry import OUT_OF_SCOPE_DOC_TYPES, discover_insurers


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
        hub_urls = [
            urljoin(self.insurer_seed.website_root, path)
            for path in self.insurer_seed.crawl_policy.document_hub_paths
        ]
        self.start_urls = [self.insurer_seed.website_root, *hub_urls]
        domain = urlparse(self.insurer_seed.website_root).netloc
        self.allowed_domains = [domain]

        self.custom_settings = {
            "DOWNLOAD_DELAY": self.insurer_seed.crawl_policy.request_delay_seconds,
        }

    async def start(self):
        """Scrapy 2.13+ replaced the old sync `start_requests()` hook with
        this async generator - `start_requests()` is dead code under
        Scrapy 2.17 (confirmed directly: base Spider has no such attribute
        at all, and nothing in the engine bridges it), which is exactly
        why known_document_urls silently never appeared in a single real
        crawl despite a passing unit test - that test called
        `start_requests()` as a plain method directly, which works in
        isolation but is never what the actual crawl engine calls."""
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse)
        # known_document_urls (registry.py) are real documents already
        # verified live but not reachable via link-following within crawl
        # depth - yielded directly rather than discovered via parse(),
        # since parse() drops PDF responses (they're not pages to follow
        # links from) and would never otherwise turn a start_url PDF into
        # a DiscoveredDocumentItem.
        for document_url in self.insurer_seed.crawl_policy.known_document_urls:
            yield self._known_document_item(document_url)

    def _known_document_item(self, document_url: str) -> DiscoveredDocumentItem:
        doc_type_guess = classify("", document_url)
        return DiscoveredDocumentItem(
            insurer=self.insurer_seed.name,
            source_page_url=self.insurer_seed.website_root,
            document_url=document_url,
            link_text="",
            doc_type_guess=doc_type_guess,
            discovered_at=datetime.now(timezone.utc).isoformat(),
            in_scope=self._is_in_scope(doc_type_guess, document_url),
        )

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
                doc_type_guess = classify(text, absolute_url)
                yield DiscoveredDocumentItem(
                    insurer=self.insurer_seed.name,
                    source_page_url=response.url,
                    document_url=absolute_url,
                    link_text=text,
                    doc_type_guess=doc_type_guess,
                    discovered_at=datetime.now(timezone.utc).isoformat(),
                    in_scope=self._is_in_scope(doc_type_guess, absolute_url),
                )
            elif urlparse(absolute_url).netloc == self.allowed_domains[0]:
                yield response.follow(absolute_url, callback=self.parse)

    def _is_in_scope(self, doc_type_guess: str, document_url: str) -> bool:
        """Flags claim/application forms, known noise paths (e.g. old
        investment-fund archives - see registry.py), and off-domain PDFs
        as out of scope for this vertical slice. Flagged, not dropped -
        the item is still yielded so the crawl output stays a complete,
        honest record.

        Off-domain check added 2026-07-30: a real Fidelity Life crawl
        picked up an FMA (regulator) licensing PDF linked from Fidelity's
        own site - a third party's document is never the insurer's own
        policy wording, regardless of what the link text says."""
        if doc_type_guess in OUT_OF_SCOPE_DOC_TYPES:
            return False
        if urlparse(document_url).netloc != self.allowed_domains[0]:
            return False
        url_lower = document_url.lower()
        if any(s in url_lower for s in self.insurer_seed.crawl_policy.excluded_path_substrings):
            return False
        return True
