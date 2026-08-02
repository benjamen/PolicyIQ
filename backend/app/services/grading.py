"""Deterministic grading engine for life insurance product comparison.

Deliberately not an LLM call. The extraction pipeline (docs/05-AI-EXTRACTION-
STRATEGY.md) is where LLM judgment and citation-verification belong; once a
fact is extracted and verified, turning it into a comparable score is a plain
function of that fact, and stays that way so a grade is reproducible and
explainable without inference cost or additional hallucination surface -
"why did this get 74/100" should always be answerable by pointing at the
weights and the extracted facts below, not by re-asking a model.

A criterion with no extracted fact is EXCLUDED from the weighted average
(data_completeness reflects this), never silently scored as 0 or 100 - an
insurer whose PDS hasn't been fully processed yet must not look worse (or
better) than one that has.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import (
    CompareFilters,
    PremiumBasis,
    ProductProfile,
    RestrictionType,
    SmokerStatus,
    SourceRef,
    TpdBasis,
)

DEFAULT_WEIGHTS: dict[str, float] = {
    "tpd_definition": 0.25,
    "trauma_conditions": 0.20,
    "occupation_restrictions": 0.20,
    "premium_structure": 0.15,
    "waiver_of_premium": 0.10,
    "automatic_benefits": 0.10,
}

_TPD_SCORES: dict[TpdBasis, float] = {
    TpdBasis.OWN_OCCUPATION: 100.0,
    TpdBasis.MODIFIED_OWN_OCCUPATION: 70.0,
    TpdBasis.ANY_OCCUPATION: 45.0,
    TpdBasis.ACTIVITIES_OF_DAILY_LIVING: 25.0,
}

# Plain-English explanation of each TPD definition's strength, surfaced in the
# UI as the "why" behind the tpd_definition score.
_TPD_RATIONALE: dict[TpdBasis, str] = {
    TpdBasis.OWN_OCCUPATION: "Pays out if you can't do your own specific job - the strongest, most claimant-friendly TPD definition.",
    TpdBasis.MODIFIED_OWN_OCCUPATION: "Pays out if you can't do your own job, subject to stated conditions - strong, but narrower than pure own-occupation.",
    TpdBasis.ANY_OCCUPATION: "Pays out only if you can't do any job you're suited to by experience - a much stricter threshold.",
    TpdBasis.ACTIVITIES_OF_DAILY_LIVING: "Pays out only if you can't perform basic daily-living activities unaided - the strictest definition.",
}

# Typical NZ market range for trauma/critical-illness condition-list length,
# used to normalize count -> 0-100. Revisit once the gold eval set (docs/05)
# gives us real observed min/max instead of an estimate.
_TRAUMA_COUNT_FLOOR = 15
_TRAUMA_COUNT_CEILING = 50

_AUTOMATIC_BENEFITS_CEILING = 10


@dataclass(frozen=True)
class CriterionResult:
    score: float | None  # None => excluded from data_completeness/overall
    weight: float
    raw_value: str
    source: SourceRef | None
    # Plain-English explanation of WHY this score was assigned - the rule
    # applied to the extracted fact. Lets the UI answer "why 74/100" without
    # re-deriving it (see module docstring: grades must stay explainable).
    rationale: str


@dataclass(frozen=True)
class GradeReport:
    insurer: str
    product_name: str
    policy_version_id: str
    eligible: bool
    ineligibility_reason: str | None
    overall_score: float | None
    data_completeness: float  # fraction of weighted criteria that had data
    criteria: dict[str, CriterionResult]


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def check_eligibility(profile: ProductProfile, filters: CompareFilters) -> tuple[bool, str | None]:
    window = profile.eligibility
    # window.eligibility_published=False means age_min=0/age_max=120 is a
    # wide placeholder (repository.py), not a real extracted range - never
    # treat it as a real age exclusion. Real occupation/smoker exclusions
    # below are unaffected; they only fire when actually extracted.
    if window.eligibility_published and not (window.age_min <= filters.age <= window.age_max):
        return False, f"Age {filters.age} outside product's {window.age_min}-{window.age_max} range"

    if (
        window.smoker_status_available != SmokerStatus.ANY
        and filters.smoker_status != SmokerStatus.ANY
        and window.smoker_status_available != filters.smoker_status
    ):
        return False, f"Product not offered for smoker status '{filters.smoker_status.value}'"

    for restriction in profile.occupation_restrictions:
        if (
            restriction.occupation_category.lower() == filters.occupation_category.lower()
            and restriction.restriction_type == RestrictionType.EXCLUSION
        ):
            return False, f"Occupation category '{filters.occupation_category}' excluded: {restriction.note}"

    if not window.eligibility_published:
        return True, (
            "Eligibility age range not published by this insurer - shown as eligible by "
            "default; confirm directly with the insurer"
        )

    return True, None


def score_tpd_definition(profile: ProductProfile) -> CriterionResult:
    tpd = profile.tpd_definition
    if tpd is None:
        raw_value = "not published - no TPD cover offered" if not profile.tpd_offered else "not extracted"
        rationale = (
            "This product doesn't offer TPD cover, so there's nothing to score - excluded, not penalised."
            if not profile.tpd_offered
            else "No TPD definition could be extracted from this policy yet - excluded from the score rather than treated as zero."
        )
        return CriterionResult(None, DEFAULT_WEIGHTS["tpd_definition"], raw_value, None, rationale)
    score = _TPD_SCORES[tpd.basis]
    return CriterionResult(
        score=score,
        weight=DEFAULT_WEIGHTS["tpd_definition"],
        raw_value=tpd.basis.value,
        source=tpd.source,
        rationale=f"{_TPD_RATIONALE[tpd.basis]} Scored {score:.0f}/100.",
    )


def score_trauma_conditions(profile: ProductProfile) -> CriterionResult:
    count = profile.trauma_condition_count
    if count is None:
        return CriterionResult(
            None,
            DEFAULT_WEIGHTS["trauma_conditions"],
            "not extracted",
            None,
            "Trauma condition count hasn't been extracted from this policy yet - excluded from the score.",
        )
    span = _TRAUMA_COUNT_CEILING - _TRAUMA_COUNT_FLOOR
    normalized = (count - _TRAUMA_COUNT_FLOOR) / span * 100.0
    score = _clamp(normalized)
    return CriterionResult(
        score=score,
        weight=DEFAULT_WEIGHTS["trauma_conditions"],
        raw_value=f"{count} conditions",
        source=profile.trauma_condition_source,
        rationale=(
            f"Covers {count} trauma / critical-illness conditions. Measured against the typical NZ "
            f"market range of {_TRAUMA_COUNT_FLOOR}-{_TRAUMA_COUNT_CEILING}, that normalises to {score:.0f}/100."
        ),
    )


def score_occupation_restrictions(profile: ProductProfile, occupation_category: str) -> CriterionResult:
    match = next(
        (
            r
            for r in profile.occupation_restrictions
            if r.occupation_category.lower() == occupation_category.lower()
        ),
        None,
    )
    if match is None:
        return CriterionResult(
            score=100.0,
            weight=DEFAULT_WEIGHTS["occupation_restrictions"],
            raw_value="no restriction on file",
            source=None,
            rationale=(
                f"No occupation restriction is recorded for '{occupation_category}', so we treat it as "
                "unrestricted (100/100) - confirm directly with the insurer."
            ),
        )
    score = {RestrictionType.NONE: 100.0, RestrictionType.LOADING: 55.0, RestrictionType.EXCLUSION: 0.0}[
        match.restriction_type
    ]
    rationale = {
        RestrictionType.NONE: f"The insurer records no restriction for '{occupation_category}' - full marks (100/100).",
        RestrictionType.LOADING: f"Cover is available for '{occupation_category}' but with a premium loading - you'd pay more, so this scores 55/100.",
        RestrictionType.EXCLUSION: f"'{occupation_category}' is excluded from cover - no payout for this occupation class (0/100).",
    }[match.restriction_type]
    return CriterionResult(
        score=score,
        weight=DEFAULT_WEIGHTS["occupation_restrictions"],
        raw_value=f"{match.restriction_type.value}: {match.note}",
        source=match.source,
        rationale=rationale,
    )


def score_premium_structure(profile: ProductProfile) -> CriterionResult:
    ps = profile.premium_structure
    if ps is None:
        return CriterionResult(
            None,
            DEFAULT_WEIGHTS["premium_structure"],
            "not extracted",
            None,
            "Premium structure hasn't been extracted from this policy yet - excluded from the score.",
        )
    basis_score = 50.0 if ps.basis == PremiumBasis.LEVEL else 30.0
    guarantee_score = 50.0 if ps.guaranteed else 10.0
    basis_label = (
        "Level premiums (don't rise with age)" if ps.basis == PremiumBasis.LEVEL else "Stepped premiums (rise with age)"
    )
    guarantee_label = "guaranteed (insurer can't change them)" if ps.guaranteed else "reviewable (insurer can adjust them)"
    score = basis_score + guarantee_score
    return CriterionResult(
        score=score,
        weight=DEFAULT_WEIGHTS["premium_structure"],
        raw_value=f"{ps.basis.value}, {'guaranteed' if ps.guaranteed else 'reviewable'}",
        source=ps.source,
        rationale=f"{basis_label}: {basis_score:.0f}/50 + {guarantee_label}: {guarantee_score:.0f}/50 = {score:.0f}/100.",
    )


def score_waiver_of_premium(profile: ProductProfile) -> CriterionResult:
    if profile.waiver_of_premium is None:
        return CriterionResult(
            None,
            DEFAULT_WEIGHTS["waiver_of_premium"],
            "not extracted",
            None,
            "Waiver of premium hasn't been extracted from this policy yet - excluded from the score.",
        )
    included = profile.waiver_of_premium
    return CriterionResult(
        score=100.0 if included else 0.0,
        weight=DEFAULT_WEIGHTS["waiver_of_premium"],
        raw_value="included" if included else "not included",
        source=profile.waiver_of_premium_source,
        rationale=(
            "Waiver of premium is included - your cover continues without payments while you're on claim (100/100)."
            if included
            else "No waiver of premium - you keep paying premiums while on claim (0/100)."
        ),
    )


def score_automatic_benefits(profile: ProductProfile) -> CriterionResult:
    count = profile.automatic_benefits_count
    if count is None:
        return CriterionResult(
            None,
            DEFAULT_WEIGHTS["automatic_benefits"],
            "not extracted",
            None,
            "Automatic benefits haven't been extracted from this policy yet - excluded from the score.",
        )
    normalized = count / _AUTOMATIC_BENEFITS_CEILING * 100.0
    score = _clamp(normalized)
    return CriterionResult(
        score=score,
        weight=DEFAULT_WEIGHTS["automatic_benefits"],
        raw_value=f"{count} automatic benefits",
        source=profile.automatic_benefits_source,
        rationale=(
            f"{count} automatic benefits are included out of a market ceiling of "
            f"{_AUTOMATIC_BENEFITS_CEILING} - normalised to {score:.0f}/100."
        ),
    )


def grade_product(profile: ProductProfile, filters: CompareFilters) -> GradeReport:
    eligible, reason = check_eligibility(profile, filters)

    criteria = {
        "tpd_definition": score_tpd_definition(profile),
        "trauma_conditions": score_trauma_conditions(profile),
        "occupation_restrictions": score_occupation_restrictions(profile, filters.occupation_category),
        "premium_structure": score_premium_structure(profile),
        "waiver_of_premium": score_waiver_of_premium(profile),
        "automatic_benefits": score_automatic_benefits(profile),
    }

    scored = {k: v for k, v in criteria.items() if v.score is not None}
    total_weight = sum(DEFAULT_WEIGHTS.values())
    data_completeness = sum(v.weight for v in scored.values()) / total_weight if total_weight else 0.0

    overall_score: float | None = None
    if scored:
        weight_sum = sum(v.weight for v in scored.values())
        overall_score = sum(v.score * v.weight for v in scored.values()) / weight_sum

    return GradeReport(
        insurer=profile.insurer,
        product_name=profile.product_name,
        policy_version_id=profile.policy_version_id,
        eligible=eligible,
        ineligibility_reason=reason,
        overall_score=overall_score,
        data_completeness=data_completeness,
        criteria=criteria,
    )


def compare(
    profiles: list[ProductProfile],
    filters: CompareFilters,
) -> list[GradeReport]:
    """Grade every profile matching filters.product_type, ranked by overall
    score. Ineligible products are included (not dropped) so the caller can
    show why a product didn't qualify rather than silently hiding it -
    hiding a disqualified product is itself an unsourced claim ("this
    doesn't apply to you") the UI shouldn't make without showing the
    reason."""
    candidates = [p for p in profiles if p.product_type == filters.product_type]
    reports = [grade_product(p, filters) for p in candidates]
    reports.sort(
        key=lambda r: (r.eligible, r.overall_score if r.overall_score is not None else -1.0),
        reverse=True,
    )
    return reports
