from app.domain.models import (
    CompareFilters,
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
from app.services.grading import check_eligibility, compare, grade_product

SRC = SourceRef(insurer="TestCo", document="Policy Wording v1", page=1, paragraph_ref="1.1", confidence=0.95)


def make_profile(**overrides) -> ProductProfile:
    defaults = dict(
        insurer="TestCo",
        product_name="Life Cover",
        policy_version_id="pv-1",
        product_type="life_cover",
        eligibility=EligibilityWindow(age_min=18, age_max=65, smoker_status_available=SmokerStatus.ANY),
        occupation_restrictions=(),
        tpd_definition=TpdDefinition(basis=TpdBasis.OWN_OCCUPATION, source=SRC),
        trauma_condition_count=40,
        trauma_condition_source=SRC,
        premium_structure=PremiumStructure(basis=PremiumBasis.LEVEL, guaranteed=True, source=SRC),
        waiver_of_premium=True,
        waiver_of_premium_source=SRC,
        automatic_benefits_count=8,
        automatic_benefits_source=SRC,
    )
    defaults.update(overrides)
    return ProductProfile(**defaults)


def make_filters(**overrides) -> CompareFilters:
    defaults = dict(age=35, smoker_status=SmokerStatus.NON_SMOKER, occupation_category="Professional", product_type="life_cover")
    defaults.update(overrides)
    return CompareFilters(**defaults)


class TestEligibility:
    def test_within_age_range_is_eligible(self):
        eligible, reason = check_eligibility(make_profile(), make_filters(age=35))
        assert eligible is True
        assert reason is None

    def test_below_age_min_is_ineligible(self):
        profile = make_profile(eligibility=EligibilityWindow(age_min=40, age_max=65))
        eligible, reason = check_eligibility(profile, make_filters(age=25))
        assert eligible is False
        assert "outside" in reason

    def test_unpublished_eligibility_defaults_to_eligible_with_advisory_reason(self):
        """Real finding 2026-07-31: three insurers genuinely don't publish
        a general applicant age range anywhere public. The 0-120
        placeholder window (repository.py) must never act as a real age
        filter - any age passes - but the caller should still learn that
        eligibility here is unconfirmed, not silently identical to a real
        published 'no restriction' answer."""
        profile = make_profile(eligibility=EligibilityWindow(age_min=0, age_max=120, eligibility_published=False))
        eligible, reason = check_eligibility(profile, make_filters(age=90))
        assert eligible is True
        assert reason is not None
        assert "not published" in reason

    def test_unpublished_eligibility_does_not_mask_a_real_occupation_exclusion(self):
        profile = make_profile(
            eligibility=EligibilityWindow(age_min=0, age_max=120, eligibility_published=False),
            occupation_restrictions=(
                OccupationRestriction(
                    occupation_category="Professional",
                    restriction_type=RestrictionType.EXCLUSION,
                    note="Not offered to this occupation class",
                    source=SRC,
                ),
            ),
        )
        eligible, reason = check_eligibility(profile, make_filters())
        assert eligible is False
        assert "excluded" in reason

    def test_occupation_exclusion_makes_ineligible(self):
        profile = make_profile(
            occupation_restrictions=(
                OccupationRestriction(
                    occupation_category="Professional",
                    restriction_type=RestrictionType.EXCLUSION,
                    note="Not offered to this occupation class",
                    source=SRC,
                ),
            )
        )
        eligible, reason = check_eligibility(profile, make_filters(occupation_category="Professional"))
        assert eligible is False
        assert "excluded" in reason.lower()

    def test_occupation_exclusion_for_other_category_does_not_block(self):
        profile = make_profile(
            occupation_restrictions=(
                OccupationRestriction(
                    occupation_category="Manual Trade",
                    restriction_type=RestrictionType.EXCLUSION,
                    note="Not offered",
                    source=SRC,
                ),
            )
        )
        eligible, _ = check_eligibility(profile, make_filters(occupation_category="Professional"))
        assert eligible is True


class TestGrading:
    def test_own_occupation_tpd_scores_higher_than_any_occupation(self):
        own = grade_product(make_profile(), make_filters())
        any_occ = grade_product(
            make_profile(tpd_definition=TpdDefinition(basis=TpdBasis.ANY_OCCUPATION, source=SRC)),
            make_filters(),
        )
        assert own.criteria["tpd_definition"].score > any_occ.criteria["tpd_definition"].score
        assert own.overall_score > any_occ.overall_score

    def test_missing_fact_excluded_not_penalized(self):
        report = grade_product(make_profile(tpd_definition=None), make_filters())
        assert report.criteria["tpd_definition"].score is None
        assert report.data_completeness < 1.0
        # overall score still computed from the remaining criteria, not zeroed out
        assert report.overall_score is not None
        assert report.overall_score > 0

    def test_confirmed_no_tpd_product_reads_not_published_not_not_extracted(self):
        """Real gap found 2026-07-31: AA Life and Chubb Life NZ's product
        lineups genuinely have no TPD cover at all (confirmed by reading
        every one of their real policy documents) - "not extracted" would
        misleadingly imply a pipeline gap rather than a confirmed absence."""
        report = grade_product(make_profile(tpd_definition=None, tpd_offered=False), make_filters())
        assert report.criteria["tpd_definition"].score is None
        assert report.criteria["tpd_definition"].raw_value == "not published - no TPD cover offered"

    def test_not_yet_checked_tpd_still_reads_not_extracted(self):
        report = grade_product(make_profile(tpd_definition=None, tpd_offered=True), make_filters())
        assert report.criteria["tpd_definition"].raw_value == "not extracted"

    def test_every_scored_criterion_carries_a_source(self):
        report = grade_product(make_profile(), make_filters())
        for name, result in report.criteria.items():
            if result.score is not None and name != "occupation_restrictions":
                assert result.source is not None, f"{name} has a score but no source"

    def test_occupation_loading_scores_between_none_and_exclusion(self):
        profile = make_profile(
            occupation_restrictions=(
                OccupationRestriction(
                    occupation_category="Professional",
                    restriction_type=RestrictionType.LOADING,
                    note="15% loading applies",
                    source=SRC,
                ),
            )
        )
        report = grade_product(profile, make_filters(occupation_category="Professional"))
        assert 0 < report.criteria["occupation_restrictions"].score < 100


class TestCompare:
    def test_ineligible_products_ranked_below_eligible(self):
        eligible_profile = make_profile(policy_version_id="pv-eligible")
        ineligible_profile = make_profile(
            policy_version_id="pv-ineligible",
            eligibility=EligibilityWindow(age_min=60, age_max=70),
        )
        reports = compare([eligible_profile, ineligible_profile], make_filters(age=35))
        assert reports[0].policy_version_id == "pv-eligible"
        assert reports[0].eligible is True
        assert reports[-1].eligible is False

    def test_only_matching_product_type_is_compared(self):
        life = make_profile(product_type="life_cover")
        trauma = make_profile(product_type="trauma", policy_version_id="pv-trauma")
        reports = compare([life, trauma], make_filters(product_type="life_cover"))
        assert len(reports) == 1
        assert reports[0].policy_version_id == life.policy_version_id

    def test_higher_scoring_product_ranks_first(self):
        strong = make_profile(policy_version_id="pv-strong")
        weak = make_profile(
            policy_version_id="pv-weak",
            tpd_definition=TpdDefinition(basis=TpdBasis.ACTIVITIES_OF_DAILY_LIVING, source=SRC),
            trauma_condition_count=16,
            waiver_of_premium=False,
        )
        reports = compare([strong, weak], make_filters())
        assert reports[0].policy_version_id == "pv-strong"
