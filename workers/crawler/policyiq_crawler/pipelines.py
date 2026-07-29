"""Crawler-stage pipeline: records discovered candidate document URLs.

Intentionally does not fetch, hash, or persist documents - that's the
Downloader worker's job (docs/01-ARCHITECTURE.md service map), which does
the ETag/Last-Modified/hash version-detection dance from
docs/04-CRAWLER-STRATEGY.md and is unrelated to Scrapy's own item pipeline.
This pipeline's only responsibility is to emit a clean, deduplicated (within
a single crawl run) queue of candidate URLs for the Downloader to consume.
"""

from __future__ import annotations

from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem


class DedupeWithinRunPipeline:
    def __init__(self) -> None:
        self.seen_urls: set[str] = set()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        url = adapter["document_url"]
        if url in self.seen_urls:
            raise DropItem(f"Duplicate within this crawl run: {url}")
        self.seen_urls.add(url)
        return item
