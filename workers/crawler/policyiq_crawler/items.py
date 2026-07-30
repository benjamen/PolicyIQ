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
    # Flagged, not dropped (docs/04-CRAWLER-STRATEGY.md's "route to review
    # rather than guess silently" principle applies here too): False for
    # doc types/paths this vertical slice doesn't need (claim forms, old
    # investment-fund archives - see registry.py's OUT_OF_SCOPE_DOC_TYPES/
    # excluded_path_substrings), so run_ingest.py can skip spending
    # download/OCR/LLM time on them while the crawl output still records
    # that they exist, for visibility.
    in_scope = scrapy.Field()
