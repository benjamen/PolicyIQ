import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.models import Base, EligibilityRule, GradedFact, Insurer, Policy, PolicyVersion, Product
from app.db.repository import load_product_profiles


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_policy_version(session, *, product_type="life_cover"):
    insurer = Insurer(name="TestCo", website_root="https://testco.test")
    session.add(insurer)
    session.flush()
    product = Product(insurer_id=insurer.id, product_type=product_type, name="Life Cover")
    session.add(product)
    session.flush()
    policy = Policy(product_id=product.id, name="Life Cover")
    session.add(policy)
    session.flush()
    pv = PolicyVersion(policy_id=policy.id, version_number=1, status="current")
    session.add(pv)
    session.flush()
    return pv


def test_hydrates_profile_from_graded_facts_and_eligibility(session):
    pv = _make_policy_version(session)
    session.add(EligibilityRule(policy_version_id=pv.id, age_min=18, age_max=65, smoker_status="any"))
    session.add(GradedFact(
        policy_version_id=pv.id, category="tpd_definition", raw_value="own_occupation",
        page=1, paragraph_ref="1.1", confidence=0.9,
    ))
    session.add(GradedFact(
        policy_version_id=pv.id, category="premium_structure",
        raw_value=json.dumps({"basis": "level", "guaranteed": True}),
        page=2, paragraph_ref="2.1", confidence=0.9,
    ))
    session.commit()

    profiles = load_product_profiles(session, product_type="life_cover")

    assert len(profiles) == 1
    profile = profiles[0]
    assert profile.insurer == "TestCo"
    assert profile.eligibility.age_min == 18
    assert profile.tpd_definition.basis.value == "own_occupation"
    assert profile.premium_structure.basis.value == "level"
    assert profile.premium_structure.guaranteed is True
    assert profile.trauma_condition_count is None  # never extracted - excluded, not zeroed


def test_malformed_graded_fact_is_skipped_not_a_500(session):
    """Real production bug (2026-07-30): a real Groq-extracted tpd_definition
    fact had raw_value="Paralysis (loss of everything)" - a real, correctly-
    cited phrase from the document, but not a valid TpdBasis member.
    TpdBasis(fact.raw_value) 500'd /api/v1/compare/life for every insurer,
    not just the one malformed fact. A malformed fact must be dropped and
    logged, not crash the whole response - matching the same "missing fact
    is excluded, not penalized" handling as a fact that was never
    extracted at all."""
    pv = _make_policy_version(session)
    session.add(EligibilityRule(policy_version_id=pv.id, age_min=18, age_max=65, smoker_status="any"))
    session.add(GradedFact(
        policy_version_id=pv.id, category="tpd_definition",
        raw_value="Paralysis (loss of everything)",  # not a real TpdBasis value
        page=1, paragraph_ref="1.1", confidence=0.9,
    ))
    session.add(GradedFact(
        policy_version_id=pv.id, category="trauma_conditions", raw_value="not-an-int",
        page=2, paragraph_ref="2.1", confidence=0.9,
    ))
    session.add(GradedFact(
        policy_version_id=pv.id, category="premium_structure", raw_value="not valid json at all",
        page=3, paragraph_ref="3.1", confidence=0.9,
    ))
    session.commit()

    profiles = load_product_profiles(session, product_type="life_cover")

    assert len(profiles) == 1
    profile = profiles[0]
    assert profile.tpd_definition is None
    assert profile.trauma_condition_count is None
    assert profile.premium_structure is None
    # The rest of the profile (eligibility, etc.) is still hydrated correctly.
    assert profile.eligibility.age_min == 18


def test_policy_version_without_general_eligibility_rule_is_excluded(session):
    pv = _make_policy_version(session)
    # No general EligibilityRule row at all for this policy_version.
    session.add(GradedFact(
        policy_version_id=pv.id, category="tpd_definition", raw_value="own_occupation",
        page=1, paragraph_ref="1.1", confidence=0.9,
    ))
    session.commit()

    profiles = load_product_profiles(session, product_type="life_cover")

    assert profiles == []


def test_zero_policy_versions_for_product_type_returns_empty_list(session):
    _make_policy_version(session, product_type="life_cover")
    session.commit()

    profiles = load_product_profiles(session, product_type="income_protection")

    assert profiles == []
