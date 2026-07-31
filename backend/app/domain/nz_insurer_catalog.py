"""Static, human-researched catalog of real, currently-operating NZ
insurers across the three verticals this project compares (life, home &
contents, health) - researched 2026-08-01 against the RBNZ Register of
Licensed Insurers, ICNZ's member list, the FSC's member list, and direct
verification of each insurer's own site.

This is deliberately NOT a database table: it's a curated market map (which
real insurers exist, and what do they sell) that changes on the order of
months/years, same static-registry convention as the crawler's
workers/crawler/policyiq_crawler/registry.py - `name` here must match
`Insurer.name` in the DB exactly for app.db.repository.load_insurer_coverage
to cross-reference correctly.

Deliberately excludes:
- Parent/holding entities without their own distinct retail documents (IAG,
  Suncorp, Resolution Life/Acenda Group) - only the retail-facing brand
  with real, separately-issued policy documents gets a row, matching the
  crawler registry's existing "only addressable brands" convention.
- Reinsurers, commercial/specialty-only insurers (Munich Re, Swiss Re,
  General Re, QBE, Zurich, Allianz, AIG, Aioi Nissay Dowa, Chubb's general
  side, Lloyd's, credit/travel-only insurers) - real ICNZ members, but not
  retail life/home-contents/health providers this project's document-diff
  model applies to.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogEntry:
    name: str
    website: str
    types_offered: tuple[str, ...]  # subset of ("life_cover", "home_contents", "health")
    notes: str | None = None


NZ_INSURER_CATALOG: tuple[CatalogEntry, ...] = (
    # --- Life insurance ---
    CatalogEntry(
        "AIA New Zealand", "https://www.aia.co.nz", ("life_cover", "health"),
    ),
    CatalogEntry("Partners Life", "https://www.partnerslife.co.nz", ("life_cover",)),
    CatalogEntry(
        "Fidelity Life", "https://www.fidelitylife.co.nz", ("life_cover",),
        "NZ's largest locally-owned life insurer; also underwrites the former "
        "Westpac Life book (Westpac sold its NZ life insurance business to "
        "Fidelity Life; that book is serviced under Fidelity Life now, not a "
        "separately addressable 'Westpac Life' product).",
    ),
    CatalogEntry(
        "Asteron Life", "https://www.asteronlife.co.nz", ("life_cover",),
        "Sold by Suncorp to Resolution Life in 2025 (now part of the Nippon "
        "Life-owned Acenda Group) - remains open to new business under the "
        "unchanged 'Asteron Life' brand; a rebrand to 'Acenda Life' is "
        "planned for 2027, not yet in effect.",
    ),
    CatalogEntry(
        "Chubb Life NZ", "https://www.chubb.com/nz-en/", ("life_cover",),
        "Formerly Cigna Life Insurance New Zealand Limited, rebranded Chubb Life.",
    ),
    CatalogEntry(
        "MAS (Medical Assurance Society)", "https://www.mas.co.nz",
        ("life_cover", "home_contents"),
        "Membership-based mutual for NZ professionals; also sells house/car/"
        "contents insurance directly, not just life.",
    ),
    CatalogEntry("Pinnacle Life", "https://www.pinnaclelife.co.nz", ("life_cover",)),
    CatalogEntry(
        "AA Life", "https://www.aainsurance.co.nz", ("life_cover",),
        "White-label life product underwritten by Asteron Life, not an "
        "independent insurer - distinct DB/catalog row from 'AA Insurance' "
        "(the same organisation's separately-branded general insurance arm).",
    ),
    # --- General / home & contents insurance ---
    CatalogEntry("AMI", "https://www.ami.co.nz", ("home_contents",)),
    CatalogEntry("Tower", "https://www.tower.co.nz", ("home_contents",)),
    CatalogEntry("Vero", "https://www.vero.co.nz", ("home_contents",)),
    CatalogEntry("State", "https://www.state.co.nz", ("home_contents",)),
    CatalogEntry(
        "FMG", "https://www.fmg.co.nz", ("home_contents",),
        "Rural/farm-focused mutual insurer; real household contents policy "
        "wording linked directly on fmg.co.nz (found 2026-08-01, not yet crawled).",
    ),
    CatalogEntry(
        "AA Insurance", "https://www.aainsurance.co.nz", ("home_contents",),
        "Real ICNZ general-insurer member; its 'Policy documents' link "
        "(aainsurance.co.nz/manage-policy/policy-documents/...) is a "
        "login-gated customer portal, not a public PDS - no public document "
        "found as of 2026-07-31.",
    ),
    CatalogEntry(
        "NZI", "https://www.nzi.co.nz", ("home_contents",),
        "WAF-blocked for this project's honestly-identified crawler (Akamai "
        "403 on both robots.txt and its real document URLs), confirmed "
        "2026-07-31 - same category as AIA's main domain, no evasion attempted.",
    ),
    CatalogEntry(
        "Trade Me Insurance", "https://www.trademeinsurance.co.nz", ("home_contents",),
        "White-label home & contents product underwritten by Tower.",
    ),
    CatalogEntry(
        "Initio", "https://initio.co.nz", ("home_contents",),
        "NZ's first 100%-online property insurer (est. 2011); all policies "
        "underwritten by IAG New Zealand.",
    ),
    # --- Health insurance ---
    CatalogEntry("Southern Cross Health Society", "https://www.southerncross.co.nz", ("health",)),
    CatalogEntry("nib", "https://www.nib.co.nz", ("health",)),
    CatalogEntry(
        "UniMed", "https://unimed.co.nz", ("health",),
        "Absorbed Accuro's book and brand (accuro.co.nz now redirects "
        "entirely into a UniMed portal shell) - not a separately addressable "
        "insurer any more.",
    ),
)
