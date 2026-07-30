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
    InsurerSeed("AIA New Zealand", "https://www.aia.co.nz"),
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
    InsurerSeed("MAS (Medical Assurance Society)", "https://www.mas.co.nz"),
    InsurerSeed("Pinnacle Life", "https://www.pinnaclelife.co.nz"),
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

    return LIFE_INSURER_SEED
