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


def test_aa_life_known_document_urls_are_all_on_a_trusted_domain():
    """AA Life's real documents live on www.aa.co.nz, not
    aainsurance.co.nz (its website_root); this seed also carries AA
    Insurance's general-insurance documents (assets.ctfassets.net) since
    both brands share the aainsurance.co.nz root domain - every
    known_document_urls entry must actually be covered by
    trusted_document_domains, or _is_in_scope() would flag them all as
    off-domain."""
    aa_life = next(i for i in discover_insurers() if i.name == "AA Life")
    assert "www.aa.co.nz" in aa_life.crawl_policy.trusted_document_domains
    assert "assets.ctfassets.net" in aa_life.crawl_policy.trusted_document_domains
    trusted = {aa_life.website_root.split("://")[1], *aa_life.crawl_policy.trusted_document_domains}
    for url in aa_life.crawl_policy.known_document_urls:
        assert any(url.startswith(f"https://{domain}/") for domain in trusted), url
