"""Domain types for the life-insurance comparison slice.

These are plain dataclasses, not ORM models — the grading engine
(app/services/grading.py) operates on these so it stays testable without a
database. app/db/models.py maps the same fields onto SQLAlchemy tables for
persistence; app/api/v1/compare.py is the only place that should translate
between the two.

Every extracted fact carries a SourceRef. This isn't optional metadata — a
GradedAttribute with no SourceRef is a claim with no evidence, which is the
one thing this platform is built not to produce (see docs/00-CHALLENGE.md
and docs/05-AI-EXTRACTION-STRATEGY.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SmokerStatus(str, Enum):
    SMOKER = "smoker"
    NON_SMOKER = "non_smoker"
    ANY = "any"


class TpdBasis(str, Enum):
    OWN_OCCUPATION = "own_occupation"
    MODIFIED_OWN_OCCUPATION = "modified_own_occupation"
    ANY_OCCUPATION = "any_occupation"
    ACTIVITIES_OF_DAILY_LIVING = "activities_of_daily_living"


class RestrictionType(str, Enum):
    NONE = "none"
    LOADING = "loading"
    EXCLUSION = "exclusion"


class PremiumBasis(str, Enum):
    LEVEL = "level"
    STEPPED = "stepped"


@dataclass(frozen=True)
class SourceRef:
    """Provenance for a single extracted fact. Mirrors Section/page/paragraph
    in docs/02-DATABASE-ERD.md — kept denormalized here since the grading
    engine shouldn't need to join back to the document store to explain a
    score."""

    insurer: str
    document: str
    page: int
    paragraph_ref: str
    confidence: float


@dataclass(frozen=True)
class TpdDefinition:
    basis: TpdBasis
    source: SourceRef


@dataclass(frozen=True)
class OccupationRestriction:
    occupation_category: str
    restriction_type: RestrictionType
    note: str
    source: SourceRef


@dataclass(frozen=True)
class PremiumStructure:
    basis: PremiumBasis
    guaranteed: bool
    source: SourceRef


@dataclass(frozen=True)
class EligibilityWindow:
    age_min: int
    age_max: int
    smoker_status_available: SmokerStatus = SmokerStatus.ANY
    # False when no general EligibilityRule was extracted for this
    # PolicyVersion (age_min/age_max are then a wide 0-120 placeholder,
    # never a guessed real range) - see repository.py's
    # load_product_profiles() and grading.py's check_eligibility(). Real
    # gap found 2026-07-31: three insurers' own sites/documents genuinely
    # don't state a general applicant age range anywhere public (verified
    # directly - Chubb does state one, "18 to 70", and gets a real rule
    # instead). compare()'s own docstring already establishes the
    # principle this exists to honour: "hiding a disqualified product is
    # itself an unsourced claim... the UI shouldn't make without showing
    # the reason" - the same applies to hiding an *eligible* product
    # before compare() ever sees it.
    eligibility_published: bool = True


@dataclass(frozen=True)
class ProductProfile:
    """Everything the grading engine needs about one insurer's product for
    one policy version. Built from extracted facts (Phase 1: document-derived
    only, per the user's decision to skip live quote scraping — see
    docs/09-LIFE-INSURANCE-SLICE.md)."""

    insurer: str
    product_name: str
    policy_version_id: str
    product_type: str  # e.g. "life_cover", "trauma", "tpd", "income_protection"
    eligibility: EligibilityWindow
    occupation_restrictions: tuple[OccupationRestriction, ...] = field(default_factory=tuple)
    tpd_definition: TpdDefinition | None = None
    trauma_condition_count: int | None = None
    trauma_condition_source: SourceRef | None = None
    premium_structure: PremiumStructure | None = None
    waiver_of_premium: bool | None = None
    waiver_of_premium_source: SourceRef | None = None
    automatic_benefits_count: int | None = None
    automatic_benefits_source: SourceRef | None = None


@dataclass(frozen=True)
class CompareFilters:
    age: int
    smoker_status: SmokerStatus
    occupation_category: str
    product_type: str
