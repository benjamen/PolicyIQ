from policyiq_crawler.registry import discover_insurers


def test_seed_has_no_duplicate_names():
    names = [i.name for i in discover_insurers()]
    assert len(names) == len(set(names))


def test_seed_has_no_duplicate_domains():
    roots = [i.website_root for i in discover_insurers()]
    assert len(roots) == len(set(roots))


def test_every_seed_has_a_positive_request_delay():
    for insurer in discover_insurers():
        assert insurer.crawl_policy.request_delay_seconds > 0
