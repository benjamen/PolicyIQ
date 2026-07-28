import scrapy


class DiscoveredDocumentItem(scrapy.Item):
    """One candidate document URL found on an insurer's site. This is the
    Crawler stage's entire output (see docs/01-ARCHITECTURE.md service map)
    - fetching, hashing, and versioning happen downstream in the Downloader
    worker, not here, so a crawl run never itself decides what's "new"."""

    insurer = scrapy.Field()
    source_page_url = scrapy.Field()
    document_url = scrapy.Field()
    link_text = scrapy.Field()
    doc_type_guess = scrapy.Field()  # pds | wording | brochure | claims_guide | form | unknown
    discovered_at = scrapy.Field()
