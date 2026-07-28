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
publish their own PDS/wording documents to crawl.

The seven below are the major underwriters actually named across multiple
independent market-overview sources as of mid-2026 (AIA, Partners Life,
Fidelity Life, and Asteron Life are repeatedly identified as holding the
bulk of in-force life policies; Chubb Life, MAS, and Pinnacle Life round out
the set requested for this slice). This list is a *starting seed*, not a
claim of completeness - `discover_insurers()` below is where RBNZ-register
cross-referencing gets wired in to grow it mechanically instead of by
further hand-curation.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CrawlPolicy:
    """Per-insurer crawl constraints - see docs/04-CRAWLER-STRATEGY.md.
    request_delay_seconds is a floor; Scrapy's AutoThrottle (see settings.py)
    may slow further under load, never speed up past this."""

    request_delay_seconds: float = 2.0
    allowed_paths: tuple[str, ...] = ("/",)
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
    InsurerSeed("Fidelity Life", "https://www.fidelitylife.co.nz"),
    InsurerSeed("Asteron Life", "https://www.asteronlife.co.nz"),
    InsurerSeed("Chubb Life NZ", "https://www.chubb.com/nz-en/"),
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
