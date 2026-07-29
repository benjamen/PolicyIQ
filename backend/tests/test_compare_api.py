"""Exercises POST /api/v1/compare/life end-to-end through FastAPI against a
seeded in-memory SQLite DB - app/fixtures/sample_data.py is gone (deleted
once the real pipeline could populate ProductProfiles for real; see
docs/09-LIFE-INSURANCE-SLICE.md). The three seeded products below
deliberately mirror the old fixture's shape (Alpha: fully extracted and
eligible; Beta: Manual Trade excluded; Gamma: several facts not yet
extracted) so the same eligibility/scoring assertions still mean something,
but now they're going through Document/Section-anchored DB rows and the
real repository layer (app/db/repository.py), not a hardcoded dataclass list.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    Base,
    Document,
    EligibilityRule,
    GradedFact,
    Insurer,
    OccupationCategory,
    Policy,
    PolicyVersion,
    Product,
)
from app.db.session import get_db
from app.main import app

client = TestClient(app)


def _seed_document(session: Session, policy_version_id, label: str) -> Document:
    doc = Document(
        policy_version_id=policy_version_id,
        doc_type="pds",
        storage_key=f"testco/life_cover/pds/000000000000-{label}.pdf",
        sha256_hash="0" * 64,
        source_url=f"https://example.test/{label}.pdf",
    )
    session.add(doc)
    session.flush()
    return doc


def _seed_alpha(session: Session, insurer_id) -> None:
    product = Product(insurer_id=insurer_id, product_type="life_cover", name="Life Cover")
    session.add(product)
    session.flush()
    policy = Policy(product_id=product.id, name="Life Cover")
    session.add(policy)
    session.flush()
    pv = PolicyVersion(policy_id=policy.id, version_number=1, status="current")
    session.add(pv)
    session.flush()
    doc = _seed_document(session, pv.id, "alpha-wording-v3")

    session.add(EligibilityRule(
        policy_version_id=pv.id, age_min=16, age_max=75, smoker_status="any",
        document_id=doc.id, page=1, paragraph_ref="1.1", confidence=0.9,
    ))
    manual_trade = OccupationCategory(insurer_id=insurer_id, code="Manual Trade", insurer_label="Manual Trade")
    session.add(manual_trade)
    session.flush()
    session.add(EligibilityRule(
        policy_version_id=pv.id, occupation_category_id=manual_trade.id, age_min=16, age_max=75,
        restriction_type="loading", note="Loading applies for heavy manual occupations",
        document_id=doc.id, page=14, paragraph_ref="6.2", confidence=0.88,
    ))

    facts = [
        ("tpd_definition", "own_occupation", 9, "4.1", 0.93),
        ("trauma_conditions", "42", 22, "9.1", 0.91),
        ("premium_structure", '{"basis": "level", "guaranteed": true}', 5, "2.3", 0.95),
        ("waiver_of_premium", "true", 18, "7.4", 0.89),
        ("automatic_benefits", "7", 11, "5.1", 0.90),
    ]
    for category, raw_value, page, para, confidence in facts:
        session.add(GradedFact(
            policy_version_id=pv.id, category=category, raw_value=raw_value,
            document_id=doc.id, page=page, paragraph_ref=para, confidence=confidence,
        ))


def _seed_beta(session: Session, insurer_id) -> None:
    product = Product(insurer_id=insurer_id, product_type="life_cover", name="LifeProtect")
    session.add(product)
    session.flush()
    policy = Policy(product_id=product.id, name="LifeProtect")
    session.add(policy)
    session.flush()
    pv = PolicyVersion(policy_id=policy.id, version_number=1, status="current")
    session.add(pv)
    session.flush()
    doc = _seed_document(session, pv.id, "beta-wording-v5")

    session.add(EligibilityRule(
        policy_version_id=pv.id, age_min=18, age_max=70, smoker_status="any",
        document_id=doc.id, page=1, paragraph_ref="1.1", confidence=0.9,
    ))
    manual_trade = OccupationCategory(insurer_id=insurer_id, code="Manual Trade", insurer_label="Manual Trade")
    session.add(manual_trade)
    session.flush()
    session.add(EligibilityRule(
        policy_version_id=pv.id, occupation_category_id=manual_trade.id, age_min=18, age_max=70,
        restriction_type="exclusion", note="Not offered to heavy manual occupation classes",
        document_id=doc.id, page=8, paragraph_ref="3.4", confidence=0.86,
    ))

    facts = [
        ("tpd_definition", "modified_own_occupation", 12, "5.2", 0.90),
        ("trauma_conditions", "33", 25, "8.6", 0.87),
        ("premium_structure", '{"basis": "stepped", "guaranteed": false}', 6, "2.1", 0.92),
        ("waiver_of_premium", "true", 19, "7.9", 0.85),
        ("automatic_benefits", "4", 13, "5.5", 0.88),
    ]
    for category, raw_value, page, para, confidence in facts:
        session.add(GradedFact(
            policy_version_id=pv.id, category=category, raw_value=raw_value,
            document_id=doc.id, page=page, paragraph_ref=para, confidence=confidence,
        ))


def _seed_gamma(session: Session, insurer_id) -> None:
    """Deliberately incomplete - tpd_definition/trauma/waiver never extracted,
    mirrors the old fixture's point that missing facts show up as excluded
    from the score, not zeroed."""
    product = Product(insurer_id=insurer_id, product_type="life_cover", name="Life Shield")
    session.add(product)
    session.flush()
    policy = Policy(product_id=product.id, name="Life Shield")
    session.add(policy)
    session.flush()
    pv = PolicyVersion(policy_id=policy.id, version_number=1, status="current")
    session.add(pv)
    session.flush()
    doc = _seed_document(session, pv.id, "gamma-wording-v2")

    session.add(EligibilityRule(
        policy_version_id=pv.id, age_min=18, age_max=65, smoker_status="non_smoker",
        document_id=doc.id, page=1, paragraph_ref="1.1", confidence=0.9,
    ))

    facts = [
        ("premium_structure", '{"basis": "level", "guaranteed": true}', 4, "2.2", 0.94),
        ("automatic_benefits", "9", 10, "4.4", 0.90),
    ]
    for category, raw_value, page, para, confidence in facts:
        session.add(GradedFact(
            policy_version_id=pv.id, category=category, raw_value=raw_value,
            document_id=doc.id, page=page, paragraph_ref=para, confidence=confidence,
        ))


@pytest.fixture
def seeded_client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    with TestSession() as session:
        alpha = Insurer(name="Insurer Alpha", website_root="https://alpha.test")
        beta = Insurer(name="Insurer Beta", website_root="https://beta.test")
        gamma = Insurer(name="Insurer Gamma", website_root="https://gamma.test")
        session.add_all([alpha, beta, gamma])
        session.flush()

        _seed_alpha(session, alpha.id)
        _seed_beta(session, beta.id)
        _seed_gamma(session, gamma.id)
        session.commit()

    def override_get_db():
        with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_compare_life_returns_graded_ranked_results(seeded_client):
    resp = seeded_client.post(
        "/api/v1/compare/life",
        json={
            "age": 35,
            "smoker_status": "non_smoker",
            "occupation_category": "Professional",
            "product_type": "life_cover",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_source"] == "extracted_verified"
    assert len(body["results"]) == 3

    insurers = [r["insurer"] for r in body["results"]]
    assert "Insurer Alpha" in insurers

    # results are sorted eligible-first, then by overall_score descending
    eligible_flags = [r["eligible"] for r in body["results"]]
    assert eligible_flags == sorted(eligible_flags, reverse=True)


def test_compare_excludes_products_ineligible_for_occupation(seeded_client):
    resp = seeded_client.post(
        "/api/v1/compare/life",
        json={
            "age": 35,
            "smoker_status": "non_smoker",
            "occupation_category": "Manual Trade",
            "product_type": "life_cover",
        },
    )
    body = resp.json()
    beta = next(r for r in body["results"] if r["insurer"] == "Insurer Beta")
    assert beta["eligible"] is False
    assert "excluded" in beta["ineligibility_reason"].lower()


def test_every_criterion_with_a_score_has_a_source_or_is_occupation_restrictions(seeded_client):
    resp = seeded_client.post(
        "/api/v1/compare/life",
        json={"age": 35, "smoker_status": "any", "occupation_category": "Professional", "product_type": "life_cover"},
    )
    for result in resp.json()["results"]:
        for name, criterion in result["criteria"].items():
            if criterion["score"] is not None and name != "occupation_restrictions":
                assert criterion["source"] is not None, f"{result['insurer']}.{name} scored with no source"


def test_missing_data_reflected_in_completeness_not_hidden(seeded_client):
    resp = seeded_client.post(
        "/api/v1/compare/life",
        json={"age": 35, "smoker_status": "any", "occupation_category": "Professional", "product_type": "life_cover"},
    )
    gamma = next(r for r in resp.json()["results"] if r["insurer"] == "Insurer Gamma")
    assert gamma["data_completeness"] < 1.0
    assert gamma["criteria"]["tpd_definition"]["score"] is None


@pytest.fixture
def empty_db_client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_no_data_returns_empty_results_not_an_error_or_fallback(empty_db_client):
    """Schema exists, zero rows - fail-closed per docs/01-ARCHITECTURE.md:
    this must be an honest empty list, never a silent fallback to fixture
    data (there is none left) or a 500."""
    resp = empty_db_client.post(
        "/api/v1/compare/life",
        json={"age": 35, "smoker_status": "any", "occupation_category": "Professional", "product_type": "life_cover"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] == []
    assert body["data_source"] == "extracted_verified"
