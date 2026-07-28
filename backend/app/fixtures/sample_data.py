"""SYNTHETIC placeholder data - NOT extracted from any real document.

The crawler and extraction pipeline (docs/04 and docs/05) haven't run yet,
so there are no real, citation-verified ProductProfiles to serve. This
module exists only to exercise the API/grading pipeline end-to-end during
development.

Deliberately uses fictional insurer names ("Insurer Alpha/Beta/Gamma"),
not real NZ insurer names - inventing specific policy terms and attaching
them to a real company (AIA, Partners Life, etc.) is exactly the kind of
unsourced claim this whole platform exists to prevent, and a fixture is not
an exemption. See docs/09-LIFE-INSURANCE-SLICE.md for the real insurer
registry, which contains only verifiable company/website metadata, no
invented policy facts.

DELETE this module once app/db + the real crawler/extractor pipeline can
populate ProductProfiles from verified GradedFact/EligibilityRule rows.
"""

from __future__ import annotations

from app.domain.models import (
    EligibilityWindow,
    OccupationRestriction,
    PremiumBasis,
    PremiumStructure,
    ProductProfile,
    RestrictionType,
    SmokerStatus,
    SourceRef,
    TpdBasis,
    TpdDefinition,
)


def _src(insurer: str, doc: str, page: int, para: str, confidence: float) -> SourceRef:
    return SourceRef(insurer=insurer, document=doc, page=page, paragraph_ref=para, confidence=confidence)


def load_sample_profiles() -> list[ProductProfile]:
    alpha_doc = "Life Cover Policy Wording v3 (SYNTHETIC)"
    beta_doc = "LifeProtect Policy Document v5 (SYNTHETIC)"
    gamma_doc = "Life Shield Wording v2 (SYNTHETIC)"

    return [
        ProductProfile(
            insurer="Insurer Alpha",
            product_name="Life Cover",
            policy_version_id="fixture-alpha-life-v3",
            product_type="life_cover",
            eligibility=EligibilityWindow(age_min=16, age_max=75, smoker_status_available=SmokerStatus.ANY),
            occupation_restrictions=(
                OccupationRestriction(
                    occupation_category="Manual Trade",
                    restriction_type=RestrictionType.LOADING,
                    note="Loading applies for heavy manual occupations",
                    source=_src("Insurer Alpha", alpha_doc, 14, "6.2", 0.88),
                ),
            ),
            tpd_definition=TpdDefinition(
                basis=TpdBasis.OWN_OCCUPATION,
                source=_src("Insurer Alpha", alpha_doc, 9, "4.1", 0.93),
            ),
            trauma_condition_count=42,
            trauma_condition_source=_src("Insurer Alpha", alpha_doc, 22, "9.1", 0.91),
            premium_structure=PremiumStructure(
                basis=PremiumBasis.LEVEL,
                guaranteed=True,
                source=_src("Insurer Alpha", alpha_doc, 5, "2.3", 0.95),
            ),
            waiver_of_premium=True,
            waiver_of_premium_source=_src("Insurer Alpha", alpha_doc, 18, "7.4", 0.89),
            automatic_benefits_count=7,
            automatic_benefits_source=_src("Insurer Alpha", alpha_doc, 11, "5.1", 0.90),
        ),
        ProductProfile(
            insurer="Insurer Beta",
            product_name="LifeProtect",
            policy_version_id="fixture-beta-lifeprotect-v5",
            product_type="life_cover",
            eligibility=EligibilityWindow(age_min=18, age_max=70, smoker_status_available=SmokerStatus.ANY),
            occupation_restrictions=(
                OccupationRestriction(
                    occupation_category="Manual Trade",
                    restriction_type=RestrictionType.EXCLUSION,
                    note="Not offered to heavy manual occupation classes",
                    source=_src("Insurer Beta", beta_doc, 8, "3.4", 0.86),
                ),
            ),
            tpd_definition=TpdDefinition(
                basis=TpdBasis.MODIFIED_OWN_OCCUPATION,
                source=_src("Insurer Beta", beta_doc, 12, "5.2", 0.90),
            ),
            trauma_condition_count=33,
            trauma_condition_source=_src("Insurer Beta", beta_doc, 25, "8.6", 0.87),
            premium_structure=PremiumStructure(
                basis=PremiumBasis.STEPPED,
                guaranteed=False,
                source=_src("Insurer Beta", beta_doc, 6, "2.1", 0.92),
            ),
            waiver_of_premium=True,
            waiver_of_premium_source=_src("Insurer Beta", beta_doc, 19, "7.9", 0.85),
            automatic_benefits_count=4,
            automatic_benefits_source=_src("Insurer Beta", beta_doc, 13, "5.5", 0.88),
        ),
        ProductProfile(
            insurer="Insurer Gamma",
            product_name="Life Shield",
            policy_version_id="fixture-gamma-lifeshield-v2",
            product_type="life_cover",
            eligibility=EligibilityWindow(age_min=18, age_max=65, smoker_status_available=SmokerStatus.NON_SMOKER),
            occupation_restrictions=(),
            tpd_definition=None,  # not yet extracted - shows up as excluded, not zero
            trauma_condition_count=None,
            trauma_condition_source=None,
            premium_structure=PremiumStructure(
                basis=PremiumBasis.LEVEL,
                guaranteed=True,
                source=_src("Insurer Gamma", gamma_doc, 4, "2.2", 0.94),
            ),
            waiver_of_premium=None,
            waiver_of_premium_source=None,
            automatic_benefits_count=9,
            automatic_benefits_source=_src("Insurer Gamma", gamma_doc, 10, "4.4", 0.90),
        ),
    ]
