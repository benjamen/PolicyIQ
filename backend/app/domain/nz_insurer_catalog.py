"""Static, human-researched catalog of real, currently-operating NZ
insurers across the eight consumer insurance types this project tracks
(life, house, contents, car, pet, health, travel, landlord, business,
boat) - researched 2026-08-01 against the RBNZ Register of Licensed
Insurers, ICNZ's member list, the FSC's member list, and direct
verification of each insurer's own site.

This is deliberately NOT a database table: it's a curated market map (which
real insurers exist, and what do they sell) that changes on the order of
months/years, same static-registry convention as the crawler's
workers/crawler/policyiq_crawler/registry.py - `name` here must match
`Insurer.name` in the DB exactly for app.db.repository.load_insurer_coverage
to cross-reference correctly.

"house" and "contents" are always listed as two independent market
offerings here, even for insurers whose real policy document happens to
bundle both into one combined wording (AMI, State) - the DB-level
distinction between "one combined document" and "two separate documents"
(Tower/Vero split into separate `house`/`contents` Products 2026-08-01;
AMI/State remain one `home_contents` Product since that's their one real,
genuinely-combined document) is a storage detail app.db.repository's
coverage check accounts for, not something the catalog needs to encode.

Deliberately excludes:
- Parent/holding entities without their own distinct retail documents (IAG,
  Suncorp, Resolution Life/Acenda Group) - only the retail-facing brand
  with real, separately-issued policy documents gets a row.
- Insurance brokers (Gallagher, PIC, Baileys) - they resell other
  companies' underwriting, not their own product, so they never have a
  policy wording of their own to compare.
- Reinsurers, commercial/specialty-only insurers (Munich Re, Swiss Re,
  General Re, QBE, Zurich, Allianz, AIG, Aioi Nissay Dowa, Chubb's general
  side, Lloyd's) - real ICNZ members, but not retail consumer providers.
- Youi: youi.co.nz redirects straight to youi.com.au (confirmed 2026-08-01)
  - no live, distinct NZ storefront found, despite older news coverage of
    a 2014 NZ market entry; not confident enough to list as currently real.
"""

from __future__ import annotations

from dataclasses import dataclass

# Every product_type this catalog can reference, in the order the frontend
# renders columns.
ALL_PRODUCT_TYPES: tuple[str, ...] = (
    "life_cover", "house", "contents", "car", "pet", "health",
    "travel", "landlord", "business", "boat",
)


@dataclass(frozen=True)
class CatalogEntry:
    name: str
    website: str
    types_offered: tuple[str, ...]  # subset of ALL_PRODUCT_TYPES
    notes: str | None = None


NZ_INSURER_CATALOG: tuple[CatalogEntry, ...] = (
    # --- Life insurance ---
    CatalogEntry("AIA New Zealand", "https://www.aia.co.nz", ("life_cover", "health")),
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
        ("life_cover", "house", "contents", "car"),
        "Membership-based mutual for NZ professionals; sells house/contents/"
        "car insurance directly too, not just life.",
    ),
    CatalogEntry("Pinnacle Life", "https://www.pinnaclelife.co.nz", ("life_cover",)),
    CatalogEntry(
        "AA Life", "https://www.aainsurance.co.nz", ("life_cover",),
        "White-label life product underwritten by Asteron Life, not an "
        "independent insurer - distinct DB/catalog row from 'AA Insurance' "
        "(the same organisation's separately-branded general insurance arm).",
    ),
    # --- General / house, contents, car, landlord, business, boat ---
    CatalogEntry(
        "AMI", "https://www.ami.co.nz", ("house", "contents", "car", "landlord", "travel", "business"),
    ),
    CatalogEntry(
        "Tower", "https://www.tower.co.nz", ("house", "contents", "car", "landlord"),
        "Real house and contents wordings are two separate documents "
        "('house-plus'/'contents-plus') - tracked as independent products, "
        "not one combined 'home_contents' type.",
    ),
    CatalogEntry(
        "Vero", "https://www.vero.co.nz", ("house", "contents", "business", "travel", "boat"),
        "Real house and contents wordings are two separate documents - "
        "tracked as independent products. Also underwrites AA Insurance's "
        "car cover (a joint venture between Vero/Suncorp and the NZAA) - "
        "'car' is tracked under the retail-facing 'AA Insurance' brand, not "
        "here, since that's the consumer-facing product name.",
    ),
    CatalogEntry("State", "https://www.state.co.nz", ("house", "contents", "car", "business")),
    CatalogEntry(
        "FMG", "https://www.fmg.co.nz", ("house", "contents"),
        "Rural/farm-focused mutual insurer; real household contents policy "
        "wording linked directly on fmg.co.nz (found 2026-08-01, not yet crawled).",
    ),
    CatalogEntry(
        "AA Insurance", "https://www.aainsurance.co.nz",
        ("house", "contents", "car", "travel", "landlord", "business"),
        "Real ICNZ general-insurer member (a joint venture between Vero/"
        "Suncorp and the NZAA); its 'Policy documents' link "
        "(aainsurance.co.nz/manage-policy/policy-documents/...) is a "
        "login-gated customer portal, not a public PDS - no public document "
        "found as of 2026-07-31.",
    ),
    CatalogEntry(
        "NZI", "https://www.nzi.co.nz", ("house", "contents", "business"),
        "WAF-blocked for this project's honestly-identified crawler (Akamai "
        "403 on both robots.txt and its real document URLs), confirmed "
        "2026-07-31 - same category as AIA's main domain, no evasion attempted.",
    ),
    CatalogEntry(
        "Trade Me Insurance", "https://www.trademeinsurance.co.nz", ("house", "contents", "car"),
        "White-label home/contents/car product underwritten by Tower.",
    ),
    CatalogEntry(
        "Initio", "https://initio.co.nz", ("house", "contents", "car", "landlord"),
        "NZ's first 100%-online property insurer (est. 2011); all policies "
        "underwritten by IAG New Zealand.",
    ),
    # --- Health insurance ---
    CatalogEntry(
        "Southern Cross Health Society", "https://www.southerncross.co.nz",
        ("health", "travel", "pet"),
        "Pet cover is a separately-branded product at southerncrosspet.co.nz.",
    ),
    CatalogEntry("nib", "https://www.nib.co.nz", ("health",)),
    CatalogEntry(
        "UniMed", "https://unimed.co.nz", ("health",),
        "Absorbed Accuro's book and brand (accuro.co.nz now redirects "
        "entirely into a UniMed portal shell) - not a separately addressable "
        "insurer any more.",
    ),
    # --- Car + pet specialists ---
    CatalogEntry(
        "Cove", "https://www.coveinsurance.co.nz", ("car", "pet"),
        "100%-online NZ insurer; home & contents cover is publicly "
        "advertised as 'coming soon' as of 2026-08-01, not yet a real "
        "purchasable product.",
    ),
    CatalogEntry(
        "PD Insurance", "https://www.pdinsurance.co.nz", ("pet",),
        "Dog/cat insurance specialist; underwritten by Pacific International Insurance.",
    ),
    CatalogEntry("Petcover", "https://www.petcovergroup.com/nz/", ("pet",)),
    CatalogEntry("SPCA Pet Insurance", "https://www.spcapetinsurance.co.nz", ("pet",)),
    CatalogEntry("Pet-n-Sur", "https://www.petnsur.co.nz", ("pet",)),
    # --- Travel specialist ---
    CatalogEntry(
        "1Cover", "https://www.1cover.co.nz", ("travel",),
        "Underwritten by HDI Global Specialty SE's NZ branch.",
    ),
    # --- Boat/marine specialist ---
    CatalogEntry(
        "Nautilus Marine Insurance", "https://www.nautilusinsurance.co.nz", ("boat",),
        "Real, directly-downloadable policy document, but it's scanned/"
        "image-based and this project's OCR fallback times out on it "
        "(120s hard limit) - a local processing limitation, not a source-"
        "access problem. Not yet ingested.",
    ),
    # "Nautical Insurance" (nautical.co.nz) was researched and found NOT to
    # be an independent insurer - its own site states it's "an
    # underwriting agency of Vero Insurance New Zealand" with no policy
    # document of its own, same category as the brokers this catalog
    # already excludes (Gallagher, PIC, Baileys). Vero's real Marine
    # Pleasurecraft wording is the correct source for boat cover - see the
    # "boat" type on Vero's own entry above.
)
