"""Curated risk area taxonomy for NZ insurance comparison.

Static, human-maintained — same convention as nz_insurer_catalog.py and
workers/crawler/policyiq_crawler/registry.py. This is NOT scraped data;
it's the controlled vocabulary the LLM maps extracted facts INTO (never
invents new areas from). See docs/12-SCRAPING-ARCHITECTURE.md §1.1.

Hierarchy: top-level areas have parent_code=None; sub-areas reference
their parent's code. The DB migration seeds these via seed_risk_areas().

Coverage comparison queries join RISK_EVENT.risk_area_id against this
taxonomy — "show me every insurer's position on flood" becomes a
single indexed lookup on risk_area.code = 'flood'.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskAreaDef:
    code: str
    name: str
    parent_code: str | None = None
    description: str | None = None
    sort_order: int = 0


# The full taxonomy, ordered by sort_order within each parent group.
# ~90 nodes covering all consumer insurance verticals PolicyIQ tracks.
RISK_AREA_TAXONOMY: tuple[RiskAreaDef, ...] = (
    # ─── Property Damage ───────────────────────────────────────────────
    RiskAreaDef("property_damage", "Property Damage", None,
                "Damage to the insured structure and its contents", 100),
    RiskAreaDef("fire", "Fire & Explosion", "property_damage",
                "Damage caused by fire, explosion, or lightning strike", 101),
    RiskAreaDef("flood", "Flood", "property_damage",
                "Damage from overflowing water bodies, storm surge, or surface runoff", 102),
    RiskAreaDef("earthquake", "Earthquake & Natural Disaster", "property_damage",
                "Earthquake, volcanic eruption, tsunami, landslip, geothermal activity", 103),
    RiskAreaDef("storm", "Storm & Weather", "property_damage",
                "Wind, hail, rain ingress, and other weather-related damage", 104),
    RiskAreaDef("water_damage", "Escape of Water", "property_damage",
                "Burst pipes, appliance leaks, aquarium overflow — not flood", 105),
    RiskAreaDef("theft_property", "Theft & Burglary", "property_damage",
                "Forced entry, stolen contents, attempted break-in damage", 106),
    RiskAreaDef("malicious_damage", "Malicious Damage & Vandalism", "property_damage",
                "Deliberate destruction by third parties", 107),
    RiskAreaDef("impact_damage", "Impact Damage", "property_damage",
                "Vehicle impact, falling trees, aircraft debris", 108),
    RiskAreaDef("retaining_wall", "Retaining Wall & Land Stability", "property_damage",
                "Collapse or failure of retaining walls, subsidence, land creep", 109),
    RiskAreaDef("accidental_damage", "Accidental Damage", "property_damage",
                "Sudden, unintended damage not covered by a specific peril", 110),
    RiskAreaDef("glass_breakage", "Glass Breakage", "property_damage",
                "Windows, skylights, ceramic cooktops, shower screens", 111),

    # ─── Contents ──────────────────────────────────────────────────────
    RiskAreaDef("contents_damage", "Contents Damage & Loss", None,
                "Damage to or loss of personal belongings inside the home", 200),
    RiskAreaDef("contents_theft", "Contents Theft", "contents_damage",
                "Stolen personal items, including away-from-home cover", 201),
    RiskAreaDef("valuables", "Specified Valuables", "contents_damage",
                "Jewellery, art, collectibles — often sub-limited", 202),
    RiskAreaDef("electronics", "Electronics & Appliances", "contents_damage",
                "TVs, computers, whiteware — surge, mechanical breakdown", 203),
    RiskAreaDef("food_spoilage", "Food Spoilage", "contents_damage",
                "Fridge/freezer contents lost due to power failure or breakdown", 204),

    # ─── Liability ─────────────────────────────────────────────────────
    RiskAreaDef("liability", "Liability", None,
                "Legal liability for injury or damage to others", 300),
    RiskAreaDef("public_liability", "Public / Personal Liability", "liability",
                "Injury to visitors, damage to others' property", 301),
    RiskAreaDef("tenant_liability", "Tenant's Liability", "liability",
                "Damage to rental property caused by the tenant", 302),
    RiskAreaDef("employer_liability", "Employer's Liability", "liability",
                "Injury to domestic employees (cleaners, gardeners)", 303),
    RiskAreaDef("professional_indemnity", "Professional Indemnity", "liability",
                "Negligent advice or professional services", 304),

    # ─── Personal / Life ───────────────────────────────────────────────
    RiskAreaDef("personal_risk", "Personal Risk / Life", None,
                "Death, disability, and income protection events", 400),
    RiskAreaDef("death", "Death / Life Cover", "personal_risk",
                "Lump sum payment on death from any cause", 401),
    RiskAreaDef("tpd", "Total & Permanent Disability", "personal_risk",
                "Inability to ever work again (own/any occupation basis)", 402),
    RiskAreaDef("trauma", "Trauma / Critical Illness", "personal_risk",
                "Lump sum on diagnosis of a specified serious illness", 403),
    RiskAreaDef("income_protection", "Income Protection", "personal_risk",
                "Monthly benefit replacing lost income due to illness/injury", 404),
    RiskAreaDef("waiver_premium", "Waiver of Premium", "personal_risk",
                "Policy premiums waived during disability", 405),
    RiskAreaDef("funeral_benefit", "Funeral / Bereavement Benefit", "personal_risk",
                "Immediate payment for funeral costs", 406),
    RiskAreaDef("childrens_benefit", "Children's Benefit", "personal_risk",
                "Cover for dependent children (automatic or optional)", 407),

    # ─── Medical / Health ──────────────────────────────────────────────
    RiskAreaDef("medical", "Medical / Health", None,
                "Hospital, surgical, and diagnostic treatment cover", 500),
    RiskAreaDef("surgical", "Surgical / Hospital", "medical",
                "In-patient surgery, hospital accommodation, theatre fees", 501),
    RiskAreaDef("diagnostic", "Diagnostic & Imaging", "medical",
                "MRI, CT, ultrasound, blood tests, specialist consultations", 502),
    RiskAreaDef("cancer_treatment", "Cancer Treatment", "medical",
                "Chemotherapy, radiation, immunotherapy, targeted therapy", 503),
    RiskAreaDef("mental_health", "Mental Health", "medical",
                "Psychiatric admission, counselling, therapy sessions", 504),
    RiskAreaDef("dental", "Dental", "medical",
                "Routine dental, major dental, orthodontics", 505),
    RiskAreaDef("optical", "Optical / Vision", "medical",
                "Eye tests, glasses, contacts, laser surgery", 506),
    RiskAreaDef("physio", "Physiotherapy & Allied Health", "medical",
                "Physio, chiro, osteo, podiatry, acupuncture", 507),
    RiskAreaDef("maternity", "Maternity / Pregnancy", "medical",
                "Prenatal, delivery, postnatal care", 508),
    RiskAreaDef("prescription", "Prescription & Pharmacy", "medical",
                "Subsidised and non-subsidised medications", 509),

    # ─── Motor ─────────────────────────────────────────────────────────
    RiskAreaDef("motor", "Motor / Car", None,
                "Vehicle damage, theft, and third-party liability", 600),
    RiskAreaDef("collision", "Collision / Accident Damage", "motor",
                "Damage from collision with another vehicle or object", 601),
    RiskAreaDef("motor_theft", "Vehicle Theft", "motor",
                "Stolen vehicle, attempted theft damage", 602),
    RiskAreaDef("third_party", "Third-Party Property Damage", "motor",
                "Damage you cause to someone else's vehicle/property", 603),
    RiskAreaDef("windscreen", "Windscreen & Glass", "motor",
                "Chipped/cracked windscreen, window replacement", 604),
    RiskAreaDef("mechanical_breakdown", "Mechanical Breakdown", "motor",
                "Engine, transmission, electrical failure (if covered)", 605),
    RiskAreaDef("rental_car", "Rental / Courtesy Car", "motor",
                "Replacement vehicle while yours is being repaired", 606),
    RiskAreaDef("roadside", "Roadside Assistance", "motor",
                "Towing, flat battery, lockout, flat tyre", 607),

    # ─── Travel ────────────────────────────────────────────────────────
    RiskAreaDef("travel", "Travel", None,
                "Overseas and domestic travel-related events", 700),
    RiskAreaDef("travel_medical", "Overseas Medical", "travel",
                "Emergency medical treatment, hospitalisation abroad", 701),
    RiskAreaDef("cancellation", "Trip Cancellation / Curtailment", "travel",
                "Non-refundable costs if trip cancelled or cut short", 702),
    RiskAreaDef("baggage", "Baggage & Personal Effects", "travel",
                "Lost, stolen, or damaged luggage and belongings", 703),
    RiskAreaDef("travel_delay", "Travel Delay", "travel",
                "Accommodation/meals costs due to delayed transport", 704),
    RiskAreaDef("rental_excess", "Rental Vehicle Excess", "travel",
                "Excess on a hired car's insurance policy", 705),
    RiskAreaDef("repatriation", "Emergency Repatriation", "travel",
                "Medical evacuation, repatriation of remains", 706),

    # ─── Pet ───────────────────────────────────────────────────────────
    RiskAreaDef("pet", "Pet", None,
                "Veterinary treatment and related costs for pets", 800),
    RiskAreaDef("pet_illness", "Illness Treatment", "pet",
                "Vet visits, diagnostics, medication for illness", 801),
    RiskAreaDef("pet_injury", "Injury / Accident", "pet",
                "Emergency treatment for accidental injury", 802),
    RiskAreaDef("pet_surgery", "Surgery", "pet",
                "Operative procedures, anaesthetics, hospitalisation", 803),
    RiskAreaDef("pet_chronic", "Chronic / Ongoing Conditions", "pet",
                "Diabetes, arthritis, allergies — recurring treatment", 804),
    RiskAreaDef("pet_dental", "Dental (Pet)", "pet",
                "Extractions, scaling, oral surgery", 805),
    RiskAreaDef("pet_behavioural", "Behavioural Treatment", "pet",
                "Anxiety, aggression — specialist behaviourist", 806),
    RiskAreaDef("pet_euthanasia", "Euthanasia & Cremation", "pet",
                "End-of-life costs, cremation, burial", 807),

    # ─── Landlord / Rental ─────────────────────────────────────────────
    RiskAreaDef("landlord", "Landlord / Rental Property", None,
                "Risks specific to rental property ownership", 900),
    RiskAreaDef("rent_loss", "Loss of Rent", "landlord",
                "Rental income lost due to insured damage making property uninhabitable", 901),
    RiskAreaDef("tenant_damage", "Malicious Tenant Damage", "landlord",
                "Deliberate damage by tenants (meth contamination often separate)", 902),
    RiskAreaDef("legal_costs", "Legal / Eviction Costs", "landlord",
                "Tenancy Tribunal costs, eviction proceedings", 903),
    RiskAreaDef("meth_contamination", "Methamphetamine Contamination", "landlord",
                "Testing and remediation of P-lab contamination", 904),

    # ─── Boat / Marine ─────────────────────────────────────────────────
    RiskAreaDef("marine", "Boat / Marine", None,
                "Watercraft damage, liability, and related risks", 1000),
    RiskAreaDef("marine_damage", "Hull & Machinery Damage", "marine",
                "Physical damage to the vessel, engine, and fittings", 1001),
    RiskAreaDef("marine_sinking", "Sinking & Swamping", "marine",
                "Loss from sinking, capsizing, or swamping", 1002),
    RiskAreaDef("marine_liability", "Marine Third-Party Liability", "marine",
                "Damage to other vessels, moorings, or marina property", 1003),
    RiskAreaDef("marine_trailer", "Trailer & Launching", "marine",
                "Damage to boat trailer, launching/retrieval incidents", 1004),

    # ─── Business ──────────────────────────────────────────────────────
    RiskAreaDef("business", "Business / Commercial", None,
                "Commercial property, income, and liability risks", 1100),
    RiskAreaDef("business_property", "Business Property Damage", "business",
                "Buildings, stock, equipment, plant", 1101),
    RiskAreaDef("business_interruption", "Business Interruption", "business",
                "Lost revenue and extra costs during restoration period", 1102),
    RiskAreaDef("business_liability", "Commercial Liability", "business",
                "Public and products liability for business operations", 1103),
    RiskAreaDef("cyber", "Cyber / Data Breach", "business",
                "Data loss, ransomware, notification costs, liability", 1104),
)


def get_top_level_areas() -> tuple[RiskAreaDef, ...]:
    """Returns only root-level areas (parent_code is None)."""
    return tuple(a for a in RISK_AREA_TAXONOMY if a.parent_code is None)


def get_children(parent_code: str) -> tuple[RiskAreaDef, ...]:
    """Returns direct children of a given parent area code."""
    return tuple(a for a in RISK_AREA_TAXONOMY if a.parent_code == parent_code)


def get_area_by_code(code: str) -> RiskAreaDef | None:
    """Lookup a single area by its code."""
    return next((a for a in RISK_AREA_TAXONOMY if a.code == code), None)


ALL_AREA_CODES: frozenset[str] = frozenset(a.code for a in RISK_AREA_TAXONOMY)
