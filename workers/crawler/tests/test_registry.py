from policyiq_crawler.registry import DEFAULT_DOCUMENT_HUB_PATHS, discover_insurers


def test_seed_has_no_duplicate_names():
    names = [i.name for i in discover_insurers()]
    assert len(names) == len(set(names))


def test_seed_has_no_duplicate_domains():
    roots = [i.website_root for i in discover_insurers()]
    assert len(roots) == len(set(roots))


def test_every_seed_has_a_positive_request_delay():
    for insurer in discover_insurers():
        assert insurer.crawl_policy.request_delay_seconds > 0


def test_every_seed_has_document_hub_paths_to_probe():
    """No government registry cross-references insurance policy wordings
    (researched 2026-07-30, see docs/04-CRAWLER-STRATEGY.md) - each insurer's
    own site is the only source, so every seed needs at least a default set
    of documents-hub paths to try, not just homepage link-following."""
    assert len(DEFAULT_DOCUMENT_HUB_PATHS) > 0
    for path in DEFAULT_DOCUMENT_HUB_PATHS:
        assert path.startswith("/")
    for insurer in discover_insurers():
        assert len(insurer.crawl_policy.document_hub_paths) > 0
