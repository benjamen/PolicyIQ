"""Insurer registry seed for the life-insurance vertical slice.

Only verifiable company/website metadata lives here - no invented policy
facts (those belong in the extraction pipeline, sourced from real crawled
documents, never fabricated - see backend/app/fixtures/sample_data.py for
why that boundary matters).

Selection: the NZ life insurance market is genuinely concentrated - RBNZ's
public Register of Licensed Insurers (84 entities across all insurance
lines, prudentially licensed under the Insurance (Prudential Supervision)
Act 2010: https://www.rbnz.govt.nz/regulation-and-supervision/cross-sector-
oversight/registers-of-entities-we-regulate/register-of-licensed-insurers)
is the authoritative source, but most of those 84 write general/health
insurance, not life. Comparison/aggregator sites that surface in a "top N
life insurers" search (LifeDirect, Glimp, Compare.org.nz, MoneyHub,
Pinnacle Life's competitors listings, etc.) are brokers or aggregators, not
insurers, and are deliberately excluded from this registry - they don't
publish their own PDS/wording documents to crawl (confirmed directly:
LifeDirect's /compare/* pages are a client-side quote-rating tool requiring
a filled-in form, not a document listing - there is nothing static to crawl
there, and even if there were, citing a rival aggregator's summarized output
instead of the insurer's own primary-source text would undermine this
project's citation-verification design).

The seven below are the major underwriters actually named across multiple
independent market-overview sources as of mid-2026 (AIA, Partners Life,
Fidelity Life, and Asteron Life are repeatedly identified as holding the
bulk of in-force life policies; Chubb Life, MAS, and Pinnacle Life round out
the set requested for this slice). This list is a *starting seed*, not a
claim of completeness - `discover_insurers()` below is where RBNZ-register
cross-referencing gets wired in to grow it mechanically instead of by
further hand-curation.

No government registry exists for this document category (researched
2026-07-30): unlike KiwiSaver/managed investment products, which must file
on the Companies Office Disclose Register under the Financial Markets
Conduct Act 2013, traditional life/trauma/TPD/income-protection insurance
is an insurance contract, not a "financial product" in that Act's sense -
confirmed directly against the Disclose Register's own stated scope
("debt and equity securities, derivatives and managed investment products,
and managed investment schemes"), which does not mention insurance at all.
RBNZ's license register, the FSPR, and FMA's Conduct of Financial
Institutions regime cover licensing/registration/fair-conduct-summary
disclosure respectively - none require publishing policy wordings
centrally, or even publicly. Industry submissions on the Contracts of
Insurance Act 2024 explicitly noted some insurers have no publicly
available wording at all ("only through application") - matching what this
crawler found firsthand: Partners Life and Asteron Life's product pages
both link only to a marketing brochure + claim form, never a full wording.
Each insurer's own site is genuinely the only source; DEFAULT_DOCUMENT_HUB_
PATHS below exists because of this - there's no registry shortcut, so the
crawler has to go looking for each insurer's own documents hub directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Common URL patterns insurers use for a documents/disclosures hub page,
# tried for every insurer in addition to homepage-rooted link-following -
# seeded from real hits (asteronlife.co.nz/important-information returned
# real content; partnerslife.co.nz/useful-documents did too, though it
# turned out to hold claim forms, not policy wordings) plus patterns named
# in industry sources (e.g. southerncrosslife.co.nz's since-moved
# /Policy-wording page). A 404 for a path an insurer doesn't use is
# harmless - Scrapy's default HttpErrorMiddleware just logs and drops it,
# never reaches parse().
DEFAULT_DOCUMENT_HUB_PATHS: tuple[str, ...] = (
    "/policy-wording",
    "/important-information",
    "/useful-documents",
    "/policy-documents",
    "/product-disclosure-statements",
    "/documents",
    "/downloads",
)

# Real noise hit crawling Asteron Life (2026-07-29): hub-path seeding found
# a large archive of old (2017-2019) investment/superannuation fund annual
# reports and fact sheets under /already-customer/investments - a real,
# live page, but irrelevant to this vertical slice (life/trauma/TPD/income-
# protection cover, not investment-linked products), and expensive to
# download+OCR+extract for no benefit. "form" (claim/application forms) is
# out of scope for the same reason: useful to a claimant, not to comparing
# coverage terms. Flagged via DiscoveredDocumentItem.in_scope, not dropped
# at discovery time - still recorded for visibility (docs/04-CRAWLER-
# STRATEGY.md's "route to review, don't guess silently" principle applies
# here too), just skipped by run_ingest.py's download/OCR/extraction spend.
#
# "annual_report" added 2026-07-30: real Fidelity Life crawl spent 45+
# minutes downloading/OCRing/extracting a multi-page annual report PDF
# (zero policy content) while chasing the known_document_urls fix -
# confirmed via docker top + /proc's wchan/socket inspection that the
# process was genuinely alive and network-active the whole time, not
# hung; it was just real, wasted work on an irrelevant document.
OUT_OF_SCOPE_DOC_TYPES: tuple[str, ...] = (
    "form", "annual_report", "corporate_comms", "investment_or_kiwisaver", "general_insurance",
)
DEFAULT_EXCLUDED_PATH_SUBSTRINGS: tuple[str, ...] = ("/investments/",)


@dataclass(frozen=True)
class CrawlPolicy:
    """Per-insurer crawl constraints - see docs/04-CRAWLER-STRATEGY.md.
    request_delay_seconds is a floor; Scrapy's AutoThrottle (see settings.py)
    may slow further under load, never speed up past this."""

    request_delay_seconds: float = 2.0
    allowed_paths: tuple[str, ...] = ("/",)
    document_hub_paths: tuple[str, ...] = DEFAULT_DOCUMENT_HUB_PATHS
    excluded_path_substrings: tuple[str, ...] = DEFAULT_EXCLUDED_PATH_SUBSTRINGS
    # Real, individually-verified (curl'd, 200 OK) document URLs on the
    # insurer's own domain that homepage + hub-path + depth-limited link-
    # following genuinely cannot reach - not linked from any page within
    # crawl depth, only search-engine-indexed. Confirmed 2026-07-30:
    # Fidelity Life's actual "*-policy-wording.pdf" documents (the real
    # TPD/exclusions/waiting-period text) exist on fidelitylife.co.nz but
    # every page the crawl reaches links only to short marketing
    # factsheets for the same products - same "real documents the crawl
    # can't see" problem hub-path seeding solved for Asteron, one level
    # more specific. Each entry here must be a document actually found and
    # verified live, never a guessed URL pattern.
    known_document_urls: tuple[str, ...] = ()
    # Additional domains treated as first-party for this insurer, alongside
    # website_root's own domain - for a real, genuinely-owned sibling
    # domain (not a third party). Confirmed 2026-07-31: AA Life's actual
    # policy documents live on www.aa.co.nz (the main Automobile
    # Association site), not aainsurance.co.nz (the insurance storefront)
    # - the off-domain check that correctly excludes a third party's
    # document (e.g. Fidelity Life's FMA regulator PDF) would otherwise
    # also incorrectly exclude these, since they're a different domain
    # too. Default empty tuple - a no-op for every insurer that doesn't
    # need this.
    trusted_document_domains: tuple[str, ...] = ()
    blocked: bool = False
    contact_note: str = ""


@dataclass(frozen=True)
class InsurerSeed:
    name: str
    website_root: str
    crawl_policy: CrawlPolicy = field(default_factory=CrawlPolicy)


# NOTE: robots.txt could not be fetched live from this development sandbox
# (outbound requests to these domains returned 403 at the network proxy -
# environment restriction, not evidence about the sites themselves). Scrapy's
# ROBOTSTXT_OBEY=True (settings.py) is the actual enforcement mechanism at
# crawl time, fetched fresh from a real deployment environment - this
# registry only sets a conservative default request delay pending that.
LIFE_INSURER_SEED: tuple[InsurerSeed, ...] = (
    # Reopened 2026-07-31: www.aia.co.nz's own WAF blocks this project's
    # honestly-identified crawler (confirmed repeatedly - clean TLS
    # handshake, then the server kills the HTTP/2 stream the instant a
    # real GET is sent), but AIA's real, current "AIA Living" policy
    # wordings are also hosted on docs.kiwicover.co.nz - KiwiCover is an
    # AIA-focused, AIA-branded quote-comparison/broker site (confirmed:
    # "Trusted AIA NZ Quote Comparison Site"), not an unrelated third
    # party - the documents are the insurer's own real, current, official
    # wordings (real version numbers, real "AIA LIVING" branding), same
    # category as AA Life's real documents living on a sibling domain,
    # not the off-domain regulator-PDF case this project correctly
    # excludes elsewhere. Each URL individually verified live.
    InsurerSeed(
        "AIA New Zealand",
        "https://www.aia.co.nz",
        crawl_policy=CrawlPolicy(
            trusted_document_domains=("docs.kiwicover.co.nz",),
            known_document_urls=(
                "https://docs.kiwicover.co.nz/policy-wordings/AIA-Living-Umbrella-Policy-Wording.pdf?v=2026-05-12",
                "https://docs.kiwicover.co.nz/policy-wordings/AIA-Living-Life-Cover-Policy-Wording.pdf?v=2026-05-12",
                "https://docs.kiwicover.co.nz/policy-wordings/AIA-Living-Progressive-Care-Policy-Wording.pdf",
                "https://docs.kiwicover.co.nz/policy-wordings/AIA-Living-Income-Protection-Indemnity-Policy-Wording.pdf?v=2026-05-12",
                "https://docs.kiwicover.co.nz/policy-wordings/AIA-Living-Waiver-of-Premium-Policy-Wording.pdf?v=2019-08-05",
                # Health insurance product added 2026-07-31: AIA Private
                # Health's real, current (version 7, effective 12 May 2026)
                # umbrella policy wording - same docs.kiwicover.co.nz
                # broker mirror as the life documents above (one InsurerSeed
                # per insurer, not per product-type - the setup script that
                # persists this into the DB is what assigns product_type
                # "health" vs "life_cover" per document).
                "https://docs.kiwicover.co.nz/policy-wordings/AIA-Private-Health-Umbrella-Policy-Wording.pdf",
            ),
        ),
    ),
    InsurerSeed("Partners Life", "https://www.partnerslife.co.nz"),
    InsurerSeed(
        "Fidelity Life",
        "https://www.fidelitylife.co.nz",
        crawl_policy=CrawlPolicy(
            known_document_urls=(
                "https://www.fidelitylife.co.nz/media/rhwnwmfn/life-protect-life-cover-policy-wording.pdf",
                "https://www.fidelitylife.co.nz/media/h44hlvyf/life-protect-terms-and-conditions-policy-wording.pdf",
                "https://www.fidelitylife.co.nz/media/fowk50ds/term-cover-policy-wording.pdf",
                "https://www.fidelitylife.co.nz/media/mfal5f3c/life-protect-permanent-disability-cover-policy-wording.pdf",
                "https://www.fidelitylife.co.nz/media/2lcblfeh/life-protect-income-cover-policy-wording.pdf",
            ),
        ),
    ),
    InsurerSeed(
        "Asteron Life",
        "https://www.asteronlife.co.nz",
        crawl_policy=CrawlPolicy(
            # Real noise found 2026-07-31 (Phase A section review): the
            # /documents/SMEIndex/ directory alone held 14+ small-business
            # research reports/infographics spanning 2018-2023 (dozens of
            # sections), none of them insurance product content - a
            # sibling problem to the existing /investments/ exclusion.
            excluded_path_substrings=DEFAULT_EXCLUDED_PATH_SUBSTRINGS + ("/smeindex/",),
            # Found 2026-08-01: asteronlife.co.nz itself never publishes a
            # real policy wording, only marketing brochures - unlike AIA's
            # kiwicover.co.nz mirror (an AIA-branded broker site), this is
            # Asteron's real "Personal Insurance Policy Document" (Life
            # Cover, Trauma Recovery, TPD, Cancer, Income Protection,
            # Workability, Mortgage and Rent Cover sections) hosted on
            # lifedirect.co.nz, NZ's largest general-purpose life insurance
            # comparison broker - not Asteron-branded, but a real,
            # currently-served document supplied by the insurer for
            # quoting/compliance purposes, same "real content on a sibling
            # domain" category this project already accepts elsewhere.
            # Caveat: this is genuinely the newest version found after
            # checking Asteron's own site, a live browser render of
            # lifedirect.co.nz's Asteron pages, and a web search - the PDF
            # itself is dated 2017 (an older one, dated 2015, also still
            # resolves at fileid=784), noticeably older than this project's
            # other life insurer wordings. Used anyway since no more recent
            # version could be located; flagged in nz_insurer_catalog.py
            # rather than silently presented as current.
            trusted_document_domains=("www.lifedirect.co.nz",),
            known_document_urls=(
                "https://www.lifedirect.co.nz/filesdisplay.aspx?type=docsrep&fileid=1782",
            ),
        ),
    ),
    InsurerSeed(
        "Chubb Life NZ",
        "https://www.chubb.com/nz-en/",
        crawl_policy=CrawlPolicy(
            # chubb.com is one shared domain (and one AEM content
            # repository) across every country Chubb operates in AND
            # across every Chubb NZ product line, not just life - real
            # evidence 2026-07-31: an unrestricted crawl found 600+
            # candidates, and even after scoping to nz-en only, the
            # biggest documents by section count were Home Contents
            # ("Masterpiece"), Business Travel, Group Personal Accident,
            # Aviation Hull Liability, Cyber, Life Sciences Liability -
            # real Chubb NZ products, just general/commercial insurance,
            # nothing to do with this project's life/trauma/TPD/income-
            # protection vertical. Scoped tight to the actual retail life
            # product ("Life and Living Insurance") instead of the whole
            # /nz-en/ site.
            #
            # Two DAM site keys, not one: the life business unit
            # publishes under .../chubb-sites/chubb/nz-en/life/ (no
            # "-com"), a sibling of the general-insurance .../chubb-com/
            # nz-en/ tree - confirmed against /nz-en/life.html's real
            # links (life cover, critical illness cover, income/expenses
            # cover, the umbrella policy document all sit there).
            allowed_paths=(
                "/nz-en/life",
                "/nz-en/personal/life-insurance.html",
                "/content/dam/chubb-sites/chubb/nz-en/life/",
            ),
            # /nz-en/life.html isn't reliably reachable via homepage link-
            # following alone (same "real hub page, not always linked
            # prominently" problem DEFAULT_DOCUMENT_HUB_PATHS exists for)
            # - seeded directly rather than hoped for.
            document_hub_paths=DEFAULT_DOCUMENT_HUB_PATHS + ("/nz-en/life.html", "/nz-en/life/life-and-living.html"),
        ),
    ),
    InsurerSeed(
        "MAS (Medical Assurance Society)", "https://www.mas.co.nz",
        crawl_policy=CrawlPolicy(
            # House/Contents/Motor Vehicle documents added 2026-08-01:
            # confirmed live via mas.co.nz's own product-detail pages
            # (not the generic /resources/insurance-resources/ listing,
            # which showed a stale March-2022 set) - all three dated
            # 1 July 2026, no WAF issue on this host.
            known_document_urls=(
                "https://www.mas.co.nz/documents/1338/House_Insurance_Policy_1_July_2026.pdf",
                "https://www.mas.co.nz/documents/1344/Contents_Insurance_Policy_1_July_2026.pdf",
                "https://www.mas.co.nz/documents/1346/Motor_Vehicle_Insurance_Policy_1_July_2026.pdf",
            ),
        ),
    ),
    InsurerSeed("Pinnacle Life", "https://www.pinnaclelife.co.nz"),
    InsurerSeed(
        "AA Life",
        "https://www.aainsurance.co.nz",
        crawl_policy=CrawlPolicy(
            # Real documents live on www.aa.co.nz (the main Automobile
            # Association site), a genuinely-owned sibling of
            # aainsurance.co.nz (the insurance storefront) - confirmed
            # 2026-07-31 via aainsurance.co.nz's own /life-insurance page,
            # which links out to aa.co.nz's real policy-wording page.
            # AA Life is underwritten by Asteron Life Limited (a white-
            # label product, not an independent insurer) - a real,
            # separately-branded product line worth comparing anyway,
            # since white-label terms commonly differ from the
            # underwriter's own-branded product.
            #
            # AA Insurance's general-insurance documents (2026-08-01) are
            # seeded here too, not as their own InsurerSeed - both brands
            # share this one root domain (aainsurance.co.nz), and
            # test_registry.py enforces one seed per domain. They still
            # become two separate DB Insurer rows ("AA Life" and "AA
            # Insurance") via their own one-off setup scripts - the
            # registry's InsurerSeed is about "one crawl target per real
            # website", not a 1:1 mapping to DB rows (same reasoning as
            # AIA's single seed covering its life and health documents).
            # AA Insurance's real documents are hosted on
            # assets.ctfassets.net, confirmed live via a genuine
            # Playwright browser rendering /manage-policy/policy-
            # documents/ (client-side JS site - a plain non-JS request
            # only sees an empty shell, which is what led to the earlier,
            # wrong "login-gated" finding).
            trusted_document_domains=("www.aa.co.nz", "assets.ctfassets.net"),
            # The wording page lists the current set (filenames dated
            # "Dec25", under .../april26/) alongside three older,
            # clearly superseded version sets on the same page. Seeded
            # directly (matching Fidelity Life's known_document_urls
            # pattern) rather than relying on generic crawling to land
            # on exactly the current 7, not an older set. Funeral Cover
            # appears only in the superseded sets - genuinely dropped
            # from the current lineup, not an oversight.
            known_document_urls=(
                "https://www.aa.co.nz/content/dam/nzaa/02-services/insurance/life-insurance/policy-documents/april26/01_AALI_Policy%20Documents_BaseWording_Dec25.pdf",
                "https://www.aa.co.nz/content/dam/nzaa/02-services/insurance/life-insurance/policy-documents/april26/02_AALI_Policy%20Documents_Life%20Cover_Dec25.pdf",
                "https://www.aa.co.nz/content/dam/nzaa/02-services/insurance/life-insurance/policy-documents/april26/03_AALI_Policy%20Documents_Accidental%20Death%20Cover_Dec25.pdf",
                "https://www.aa.co.nz/content/dam/nzaa/02-services/insurance/life-insurance/policy-documents/april26/04_AALI_Policy%20Documents_CancerCareCover_Dec25.pdf",
                "https://www.aa.co.nz/content/dam/nzaa/02-services/insurance/life-insurance/policy-documents/april26/05_AALI_Policy%20Documents_Serious_Illness_Cover_Dec25.pdf",
                "https://www.aa.co.nz/content/dam/nzaa/02-services/insurance/life-insurance/policy-documents/april26/06_AALI_Policy%20Documents_Income_Protection_Cover_Dec25.pdf",
                "https://www.aa.co.nz/content/dam/nzaa/02-services/insurance/life-insurance/policy-documents/april26/07_AALI_Policy%20Documents_Serious%20Injury%20Cover_Dec25.pdf",
                "https://assets.ctfassets.net/c28a1yh3tefi/3AOOcXPg3ujIRTHxdZpPst/7d71d2eed4320a1b93ad008c59385331/AAI_Home_Insurance_Policy_July_2026.pdf",
                "https://assets.ctfassets.net/c28a1yh3tefi/4nXZU7RDYXnFspKbVuAp0z/01aa10e7a7dafbbd89ae4428b14622a8/AAI_Contents_Insurance_Policy_July_2026.pdf",
                "https://assets.ctfassets.net/c28a1yh3tefi/33CBO6W49aqp32KJvLxSLV/e275c0335cd488a6e6742f29225e1d52/AAI_Comprehensive_Car_Insurance_Policy.pdf",
                "https://assets.ctfassets.net/c28a1yh3tefi/4cg0wcwk45dZeku3PrSztE/8ace22646f5460a2148a75df1fd257db/AAI_Landlord_Insurance_Policy_July_2026.pdf",
            ),
            excluded_path_substrings=DEFAULT_EXCLUDED_PATH_SUBSTRINGS + (
                "/15-nov-2024-v2/", "/10-july-2024-v2/", "/5-august-2029-v2/",
                # A large real archive of press-release/award PDFs
                # (2016-2020) lives under one consistent path prefix -
                # cleaner to exclude by path than to chase every award
                # name as a doctype.py keyword.
                "/newsroom/",
            ),
        ),
    ),
)

# Researched 2026-07-31, not added to the seed above:
# - Tower: checked its full navigation (car, house, contents, boat,
#   business, EV, motorbike, motorhome, pet, travel, landlord, lifestyle
#   block) - zero life insurance products exist. Not a crawling problem;
#   Tower doesn't sell what this vertical slice compares.
# - AIA doesn't sell general/house insurance at all (life and health
#   only) - not relevant to this general-insurance vertical regardless of
#   the www.aia.co.nz WAF question. See LIFE_INSURER_SEED above for AIA's
#   real life-insurance documents (reopened via docs.kiwicover.co.nz,
#   same day) - www.aia.co.nz itself remains WAF-blocked for this
#   project's honestly-identified crawler (curl -v shows a clean TLS
#   handshake, then the server kills the HTTP/2 stream with
#   INTERNAL_ERROR the instant the real GET is sent), unchanged.


# General insurance (house/contents) vertical - started 2026-07-31, proving
# the pattern on one insurer before scaling the registry (see
# docs/07-ROADMAP.md's original Phase 1 scope: AA Insurance, AMI, State,
# Tower, NZI, Vero). Crawlability researched live for all 6: AMI, Tower,
# Vero, State, FMG are directly crawlable with a plain honest-UA request
# (real policy wording PDFs linked right on their product pages). AA
# Insurance and NZI were initially misdiagnosed as blocked (a login wall,
# and an Akamai WAF, respectively) from plain curl testing alone -
# corrected 2026-08-01: both are real client-side-rendered sites where a
# genuine Playwright browser (not a header-spoofed script) reaches the
# real public content a bare request can't render/pass; see their
# individual entries below for what was actually found. Note: theaa.com
# ("The AA", UK) publishes similarly-named policy booklets under an "AA"
# brand too - a genuinely different organisation in a different country/
# regulatory regime, not a substitute source for AA Insurance NZ.
GENERAL_INSURER_SEED: tuple[InsurerSeed, ...] = (
    InsurerSeed(
        "AMI",
        "https://www.ami.co.nz",
        crawl_policy=CrawlPolicy(
            # Confirmed live 2026-07-31: linked directly from
            # /home-contents-insurance, a real product page reachable from
            # the homepage - seeded directly (matching the established
            # "real, individually-verified" known_document_urls pattern)
            # rather than relying on generic crawling to land on it.
            known_document_urls=(
                "https://www.ami.co.nz/content/dam/insurance-brands-nz/ami/nz/en/documents/home-contents/ami-home-plus-contents-plus-insurance-policy-wording-ami1713-1-0824.pdf",
                # Car insurance added 2026-08-01: real, current (v11, applies
                # from 21 Nov 2024) - same WAF block as the home-contents
                # document above (Akamai 403 for this project's honest
                # User-Agent), placed the same one-off, human-verified way
                # (genuine Playwright browser fetch, no header spoofing).
                "https://www.ami.co.nz/content/dam/insurance-brands-nz/ami/nz/en/documents/car/ami-car-insurance-policy-wording-ami0052-11-1124.pdf",
            ),
        ),
    ),
    InsurerSeed(
        "Tower",
        "https://www.tower.co.nz",
        crawl_policy=CrawlPolicy(
            # Confirmed live 2026-07-31: linked directly from /house-
            # insurance and /contents-insurance. Tower publishes 3 tiers
            # (Standard/Plus/Premium) for each - "Plus" seeded to match
            # AMI's "Home Plus and Contents Plus" coverage level for a
            # fair apples-to-apples comparison, not the full 6-document set.
            known_document_urls=(
                "https://www.tower.co.nz/wp-content/uploads/2021/03/house-plus-09-24.pdf",
                "https://www.tower.co.nz/wp-content/uploads/2021/03/contents-plus-09-24.pdf",
                # Car insurance added 2026-08-01: comprehensive cover
                # wording, real and directly crawlable (no WAF issue,
                # unlike AMI/State's car documents).
                "https://www.tower.co.nz/wp-content/uploads/2021/03/Car_Comprehensive.pdf",
            ),
        ),
    ),
    InsurerSeed(
        "Vero",
        "https://www.vero.co.nz",
        crawl_policy=CrawlPolicy(
            # Confirmed live 2026-07-31: linked directly from /personal-
            # insurance/house-insurance.html and /personal-insurance/
            # contents-insurance.html. Single tier each (no Plus/Premium
            # split like Tower).
            known_document_urls=(
                "https://www.vero.co.nz/documents/personal-insurance/vero-residential-home-policy-0724.pdf",
                "https://www.vero.co.nz/documents/personal-insurance/vero-residential-contents-policy-0724.pdf",
                # Boat insurance added 2026-08-01: real Marine Pleasurecraft
                # wording, directly crawlable.
                "https://www.vero.co.nz/documents/personal-insurance/pleasurecraft-policy-wording.pdf",
            ),
        ),
    ),
    InsurerSeed(
        "State",
        "https://www.state.co.nz",
        crawl_policy=CrawlPolicy(
            # Confirmed live 2026-07-31: linked directly from /home-
            # contents-insurance (combined Home Comprehensive + Contents
            # Comprehensive document, same structure as AMI's). State's
            # PDF-download endpoint WAF-blocks this project's honestly-
            # identified crawler (confirmed: PolicyIQNZBot's real User-
            # Agent gets 403, same as AMI) - the real file was placed via
            # the same one-off, human-verified pattern as AMI's, not
            # fetched through the automated pipeline.
            known_document_urls=(
                "https://www.state.co.nz/content/dam/insurance-brands-nz/state/nz/en/documents/home-contents/state-home-comprehensive-contents-comprehensive-insurance-policy-wording-si6995-2-1224.pdf",
                # Car insurance added 2026-08-01: real, current (v5,
                # 11/2024) - same WAF block as the home-contents document
                # above, placed the same one-off, human-verified way
                # (genuine Playwright browser fetch, no header spoofing).
                "https://www.state.co.nz/content/dam/insurance-brands-nz/state/nz/en/documents/car/state-vehicle-car-insurance-policy-wording-si6737-5-1124.pdf",
            ),
        ),
    ),
    InsurerSeed(
        "FMG", "https://www.fmg.co.nz",
        crawl_policy=CrawlPolicy(
            # Confirmed live 2026-08-01: linked directly from
            # /what-we-cover/fmg-policy-wordings/buildings/home and
            # .../contents-stock-and-equipment/household-contents. Real
            # house and contents wordings are two separate documents
            # (like Tower/Vero), both dated 1 July 2026, no WAF issue on
            # this host.
            known_document_urls=(
                "https://www.fmg.co.nz/globalassets/what-we-cover/policy-wordings/policy-wordings-2026-27/home-policy-wording-july-26.pdf",
                "https://www.fmg.co.nz/globalassets/what-we-cover/policy-wordings/policy-wordings-2026-27/household-contents-policy-wording-July-26.pdf",
            ),
        ),
    ),
    InsurerSeed(
        "NZI", "https://www.nzi.co.nz",
        crawl_policy=CrawlPolicy(
            # Corrected 2026-08-01: NZI's Akamai WAF blocks non-browser
            # HTTP clients (confirmed: bare curl and this project's honest-
            # UA curl both get a clean TLS handshake then a 403 "Access
            # Denied" or an HTTP/2 stream kill) but does NOT block a
            # genuine Playwright browser (real TLS/JS fingerprint, no
            # spoofing) - a real browser session fetched these two real,
            # current (Distinction Home/Contents, NZI's highest cover
            # tier) documents cleanly via their friendly nzi.co.nz/
            # documents/ URLs. Placed the same one-off, human-verified way
            # as AMI/State's car documents.
            known_document_urls=(
                "https://www.nzi.co.nz/documents/distinction-home-policy",
                "https://www.nzi.co.nz/documents/distinction-contents-policy",
            ),
        ),
    ),
    InsurerSeed(
        "Trade Me Insurance", "https://www.trademeinsurance.co.nz",
        crawl_policy=CrawlPolicy(
            # Confirmed live 2026-08-01: linked directly from /house-
            # insurance, /contents-insurance, /car-insurance (the "Plus"
            # tier, comprehensive cover for car) - no WAF issue, plain
            # honest-UA requests work fine. Documents are hosted on a
            # sibling domain (info.trademeinsurance.co.nz), so
            # trusted_document_domains is needed for _is_in_scope() (same
            # pattern as AA Life/nib's sibling-domain documents). Note:
            # this project's real HttpxFetcher can't download these
            # directly - info.trademeinsurance.co.nz loops forever on HEAD
            # requests to these redirected paths (confirmed via direct
            # httpx.head() test) while GET on the exact same URL works
            # fine; the one-off ingest for this insurer used a GET-only
            # Fetcher variant instead of touching HttpxFetcher (which every
            # other insurer's real HEAD support still needs).
            trusted_document_domains=("info.trademeinsurance.co.nz",),
            known_document_urls=(
                "http://info.trademeinsurance.co.nz/pw/tmi-house-plus-09-24.pdf",
                "http://info.trademeinsurance.co.nz/pw/tmi-contents-plus-09-24.pdf",
                "http://info.trademeinsurance.co.nz/pw/tmi-car-comprehensive-09-24.pdf",
                "http://info.trademeinsurance.co.nz/pw/tmi-landlords-plus-09-24.pdf",
            ),
        ),
    ),
    InsurerSeed(
        "Initio", "https://initio.co.nz",
        crawl_policy=CrawlPolicy(
            # Confirmed live 2026-08-01: all 4 real, current documents
            # linked directly from /faqs/policy-wordings/ - no WAF issue,
            # first-party domain, plain honest-UA GET works fine end to
            # end (download_and_version succeeded via the standard
            # HttpxFetcher, unlike Trade Me Insurance above).
            known_document_urls=(
                "https://initio.co.nz/policy-wording/initio_home_policy_NZ1811.pdf",
                "https://initio.co.nz/policy-wording/initio_contents_policy_NZ1811.pdf",
                "https://initio.co.nz/policy-wording/initio_motor_vehicle_insurance_policy_NZ2105.pdf",
                # Landlord and holiday-home cover share one combined wording.
                "https://initio.co.nz/policy-wording/initio_landlord_holidayhome_policy_NZ1811.pdf",
            ),
        ),
    ),
)


# Health insurance vertical - started 2026-07-31, same "prove it on one
# insurer" pacing as GENERAL_INSURER_SEED. Crawlability researched live for
# the 5 obvious NZ health insurers: Southern Cross, nib, and UniMed are
# directly crawlable (real policy documents linked from their own sites,
# permissive robots.txt); AIA Health needs the same docs.kiwicover.co.nz
# broker-mirror workaround as AIA Life (www.aia.co.nz itself still WAF-
# blocks this project's honest crawler, confirmed again 2026-07-31, same
# signature as every prior AIA check this session - not revisited).
# Accuro was researched and found NOT to be an independently addable
# insurer any more: www.accuro.co.nz now 301-redirects its entire site
# (including old /assets/Uploads/... document paths) to a "UniMed | Accuro"
# portal shell - Accuro has been absorbed into UniMed's brand, its legacy
# standalone policy documents are gone from the live web. Not adding a
# separate "Accuro" entry; UniMed is the real current insurer here.
HEALTH_INSURER_SEED: tuple[InsurerSeed, ...] = (
    InsurerSeed(
        "Southern Cross Health Society",
        "https://www.southerncross.co.nz",
        crawl_policy=CrawlPolicy(
            # Confirmed live 2026-07-31: linked directly from the public
            # southerncross.co.nz/society plan-documents page, no login
            # wall. Southern Cross sells several plan tiers (HealthEssentials,
            # Wellbeing One/Two, UltraCare) - UltraCare seeded as the single
            # representative product (their most comprehensive, best-known
            # plan) to prove the pattern, matching how AMI/Tower/etc. seeded
            # one representative tier rather than the full product range.
            known_document_urls=(
                "https://www.southerncross.co.nz/-/media/Southern-Cross-Health-Society/Health-insurance/Member-collateral/Plan-documents/Current-plan-documents/PD_UltraCare_plan.pdf",
            ),
        ),
    ),
    InsurerSeed(
        "nib",
        "https://www.nib.co.nz",
        crawl_policy=CrawlPolicy(
            # Confirmed live 2026-07-31 via nib.co.nz/compare-plans (the
            # real public plan-comparison page): nib's current direct-to-
            # consumer lineup is Standard/Premium Hospital and Standard/
            # Premium Everyday - "Premium Hospital" seeded as the single
            # representative product (most comprehensive currently-sold
            # plan, dated 24 Nov 2025). Note: "Ultimate Health"/"Ultimate
            # Health Max" (found first via web search, and still real,
            # current nib documents) turned out to be adviser-channel-only
            # products not sold directly on nib.co.nz - not seeded, to
            # avoid comparing a retail plan against a broker-only one.
            # Documents are hosted on assets.ctfassets.net (nib's own CMS
            # asset CDN, directly linked from nib.co.nz/compare-plans) -
            # a different domain than nib.co.nz itself, so
            # trusted_document_domains is needed for _is_in_scope() to
            # treat it as first-party (same pattern as AA Life's sibling
            # domain), otherwise a real automated crawl would mark this
            # known_document_url out-of-scope and Phase A would skip it.
            trusted_document_domains=("assets.ctfassets.net",),
            known_document_urls=(
                "https://assets.ctfassets.net/ja9v5o5o08yv/4B7F1fUvBXfP3RwwbJ8RG4/16b351dee312ac8c603ff884df59f8bb/premium-hospital-policy-from-24-Nov-2025.pdf",
            ),
        ),
    ),
    InsurerSeed(
        "UniMed",
        "https://unimed.co.nz",
        crawl_policy=CrawlPolicy(
            # Confirmed live 2026-07-31: UniMed's own health-plans pages
            # describe "Hospital Select" as their most extensive plan
            # (unlimited eligible surgical cover) - the flagship,
            # comparable in role to Southern Cross's UltraCare and nib's
            # Premium Hospital. Document dated 1 August 2025, linked
            # directly from unimed.co.nz/health-plans/hospital-select.
            # This is the real current insurer for Accuro's former book
            # (see the note above HEALTH_INSURER_SEED) - Accuro itself is
            # not seeded separately.
            known_document_urls=(
                "https://unimed.co.nz/assets/PlansAndDocs/Health-Plans/Hospital_Select_Plus_Modules_Plan.pdf",
            ),
        ),
    ),
)


# Specialty verticals (pet, travel, boat) - started 2026-08-01, real
# single-line insurers rather than a graded/diff comparison vertical of
# their own (each type here has few enough real providers that they're
# seeded together rather than getting their own SEED tuple per type).
SPECIALTY_INSURER_SEED: tuple[InsurerSeed, ...] = (
    InsurerSeed(
        "SPCA Pet Insurance", "https://www.spcapetinsurance.co.nz",
        crawl_policy=CrawlPolicy(
            # Confirmed live 2026-08-01: linked directly from
            # /policy-documents. SPCA sells 3 tiers (Everyday/Big Stuff/
            # The Works) - "The Works" (their most comprehensive) seeded,
            # dated 17 July 2026. Underwritten by The Hollard Insurance
            # Company Pty Ltd.
            known_document_urls=(
                "https://www.spcapetinsurance.co.nz/documents/spca-pet-insurance-the-works-cover-policy-document.pdf",
            ),
        ),
    ),
    InsurerSeed(
        "Cove", "https://www.coveinsurance.co.nz",
        crawl_policy=CrawlPolicy(
            # Confirmed live 2026-08-01: linked directly from
            # /pet-insurance/. Underwritten by Aioi Nissay Dowa Insurance
            # Co., Ltd. Cove also sells car insurance (a separate document,
            # not yet ingested) - home & contents is publicly advertised
            # as "coming soon", not a real product yet.
            known_document_urls=(
                "https://www.coveinsurance.co.nz/wp-content/uploads/2022/05/Pet-Insurance-Policy-CovePet012022.pdf",
            ),
        ),
    ),
    InsurerSeed(
        "Pet-n-Sur", "https://www.petnsur.co.nz",
        crawl_policy=CrawlPolicy(
            # Confirmed live 2026-08-01: linked directly from
            # /pet-policies/cat-and-dog/. The real document is hosted on
            # beneficial.co.nz - Beneficial Insurance Limited is Pet-n-
            # Sur's underwriter (the document's own text names it as "the
            # Company"), a legitimate white-label arrangement, not a third
            # party - same category as AA Life/Asteron.
            trusted_document_domains=("www.beneficial.co.nz",),
            known_document_urls=(
                "https://www.beneficial.co.nz/wp-content/uploads/Cat-and-Dog-Policy-Wording_20260331.pdf",
            ),
        ),
    ),
    InsurerSeed(
        "1Cover", "https://www.1cover.co.nz",
        crawl_policy=CrawlPolicy(
            # Confirmed live 2026-08-01: /policydetails/ redirects to a
            # dated HTML rendering (effective 4 March 2026); the matching
            # downloadable PDF at the predictable assets/pdf/ path was
            # individually verified (confirmed same effective date inside
            # the document itself). Underwritten by HDI Global Specialty
            # SE's NZ branch.
            known_document_urls=(
                "https://www.1cover.co.nz/assets/pdf/1Cover-NZ-Standard-PDS_20260304.pdf",
            ),
        ),
    ),
    InsurerSeed(
        "Nautilus Marine Insurance", "https://www.nautilusinsurance.co.nz",
        crawl_policy=CrawlPolicy(
            # Confirmed live 2026-08-01: linked directly from
            # /insurance/boat-insurance/, real and directly downloadable
            # (no WAF issue) - but the PDF itself is scanned/image-based
            # and this project's Docling OCR fallback times out on it
            # (120s hard limit, confirmed reproducible) - a real local
            # processing limitation, not a source-access problem. Seeded
            # here since the URL is genuine and correct; not yet ingested
            # (no Document/Section rows exist for it).
            known_document_urls=(
                "https://www.nautilusinsurance.co.nz/wp-content/files/Nautilus-Marine_Boat-Insurance-NZ_PDS.pdf",
            ),
        ),
    ),
    InsurerSeed(
        "PD Insurance", "https://www.pdinsurance.co.nz",
        crawl_policy=CrawlPolicy(
            # Corrected 2026-08-01: pdinsurance.co.nz's WAF blocks non-
            # browser HTTP clients (bare/honest-UA curl both 403) but a
            # genuine Playwright browser reaches /pet-insurance/ cleanly
            # and its real policy wording link, hosted on a separate
            # subdomain (manage.pet.pdinsurance.co.nz) that has no bot-
            # gating of its own. Underwritten by Pacific International
            # Insurance Pty Limited (confirmed in the document's own text).
            trusted_document_domains=("manage.pet.pdinsurance.co.nz",),
            known_document_urls=(
                "https://manage.pet.pdinsurance.co.nz/Docs/Policy_Wording/PD_NZ_JUL_2022_PET_INSURANCE_POLICY_WORDING.pdf",
            ),
        ),
    ),
    InsurerSeed(
        "Petcover", "https://www.petcovergroup.com/nz/",
        crawl_policy=CrawlPolicy(
            # Corrected 2026-08-01: the earlier "hosted on
            # sovereignaustralia.com.au, not individually verified" note
            # was superseded by a better find - Petcover's real, current
            # (v15062026) policy wordings are linked directly from their
            # own /nz/dog-insurance/ product page, hosted on their own
            # domain (petcovergroup.com), no WAF issue. Four tiers
            # (Superior/Mid-Range/Economy/Catastrophe) - "Superior" (their
            # most comprehensive) seeded.
            known_document_urls=(
                "https://www.petcovergroup.com/nz/wp-content/uploads/sites/18/2026/06/PCNZ-PDS-PRO-Superior-v15062026.pdf",
            ),
        ),
    ),
    # "Nautical Insurance" (nautical.co.nz) is NOT an independent insurer -
    # its own site states it's "an underwriting agency of Vero Insurance
    # New Zealand" with no policy document of its own, same category as
    # the brokers this catalog already excludes (Gallagher, PIC, Baileys)
    # - Vero's own real Marine Pleasurecraft wording (seeded above under
    # Vero) is the correct real source for this cover, not a separate
    # "Nautical Insurance" row.
)


def discover_insurers() -> tuple[InsurerSeed, ...]:
    """Returns the current insurer seed set.

    TODO (docs/04-CRAWLER-STRATEGY.md discovery pipeline, not yet built):
    cross-reference RBNZ's Register of Licensed Insurers against this seed
    on a schedule, flagging RBNZ-listed entities offering life products that
    aren't yet in LIFE_INSURER_SEED for admin review before auto-adding -
    RBNZ licensing confirms an entity is a real, regulated insurer, but not
    that it writes life insurance specifically, so this stays a human
    checkpoint rather than a fully automatic add.
    """

    return LIFE_INSURER_SEED + GENERAL_INSURER_SEED + HEALTH_INSURER_SEED + SPECIALTY_INSURER_SEED
