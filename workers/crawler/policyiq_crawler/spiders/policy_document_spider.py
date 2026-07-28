"""Generic per-insurer document-discovery spider.

One spider class driven by registry config, not a bespoke spider per
insurer - the crawler strategy calls for a maintained per-insurer *rule
set* (doc-type keywords, allowed paths), not duplicated crawl logic. Run
one insurer at a time: `scrapy crawl policy_documents -a insurer="AIA New Zealand"`.

Discovery order per docs/04-CRAWLER-STRATEGY.md: sitemap.xml first (cheap,
most sites have one), falling back to following in-domain links up to
DEPTH_LIMIT (settings.py) for sites that need it. This spider handles the
link-following fallback and PDF extraction; Playwright rendering for JS-only
nav is a separate, heavier fallback invoked only when this pass finds
suspiciously few links (see docs/04-CRAWLER-STRATEGY.md "static fetch tried
first, per URL") - not implemented in this skeleton, flagged as a TODO
rather than stubbed with fake behavior.
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

        for link in response.css("a[href]"):
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
