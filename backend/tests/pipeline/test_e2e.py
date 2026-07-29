"""End-to-end, fully offline: a synthetic PDF -> OCR routing -> section
building -> mock-LLM extraction -> citation verification -> DB rows ->
repository hydration -> grading -> a real HTTP request through FastAPI.

No live crawl, no real LLM call, no real network - proves the pipeline's
wiring is correct, not that any particular insurer's real PDS extracts
correctly (that needs a real LLM key and real documents, both explicitly
out of scope this pass).
"""

from __future__ import annotations

import json

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Benefit, Document, Insurer, Policy, PolicyVersion, Product
from app.db.repository import load_product_profiles
from app.db.session import get_db
from app.domain.models import CompareFilters, SmokerStatus
from app.main import app
from app.ocr.router import route_ocr
from app.pipeline.extraction import process_section
from app.pipeline.sections import build_sections
from app.providers.llm import MockLLMProvider
from app.services.grading import compare as run_compare

_TPD_TEXT = (
    "Total and Permanent Disability means the life insured is unable to perform their own "
    "occupation. This policy is available to applicants aged 18 to 65, smoker or non-smoker."
)
_TRAUMA_TEXT = (
    "This policy covers 40 specified trauma conditions including cancer, heart attack, and stroke."
)

_PAGE1_RESPONSE = json.dumps({
    "graded_facts": [
        {
            "category": "tpd_definition",
            "raw_value": "own_occupation",
            "confidence": 0.9,
            "source_quote": "Total and Permanent Disability means the life insured is unable to perform their own occupation",
        }
    ],
    "eligibility_rules": [
        {
            "occupation_category": None,
            "smoker_status": "any",
            "age_min": 18,
            "age_max": 65,
            "restriction_type": "none",
            "note": None,
            "confidence": 0.9,
            "source_quote": "This policy is available to applicants aged 18 to 65, smoker or non-smoker",
        }
    ],
    "benefits": [], "limits": [], "exclusions": [], "definitions": [], "waiting_periods": [], "optional_benefits": [],
})

_PAGE2_RESPONSE = json.dumps({
    "graded_facts": [
        {
            "category": "trauma_conditions",
            "raw_value": "40",
            "confidence": 0.85,
            "source_quote": "This policy covers 40 specified trauma conditions including cancer, heart attack, and stroke",
        }
    ],
    "eligibility_rules": [],
    # Deliberately fabricated - this exact sentence does not appear anywhere in the
    # source PDF. Proves verify_citation() actually rejects unsupported claims
    # instead of rubber-stamping whatever the model returns.
    "benefits": [
        {
            "name": "Free overseas travel cover",
            "description": None,
            "monetary_limit": None,
            "percentage_limit": None,
            "is_automatic": True,
            "confidence": 0.7,
            "source_quote": "Free overseas travel insurance included automatically",
        }
    ],
    "limits": [], "exclusions": [], "definitions": [], "waiting_periods": [], "optional_benefits": [],
})


def _build_synthetic_pdf() -> bytes:
    # insert_text() silently drops whatever doesn't fit on the line (it does not
    # wrap) - long enough sentences get truncated mid-quote. insert_textbox()
    # wraps within a rect instead, so the full text always lands on the page.
    doc = fitz.open()
    rect = fitz.Rect(72, 72, 523, 770)
    page1 = doc.new_page()
    page1.insert_textbox(rect, _TPD_TEXT, fontsize=10)
    page2 = doc.new_page()
    page2.insert_textbox(rect, _TRAUMA_TEXT, fontsize=10)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return eng


def test_full_pipeline_produces_citation_verified_data_end_to_end(engine):
    Session_ = sessionmaker(bind=engine)

    with Session_() as session:
        # ---- 1. OCR: real PyMuPDF extraction on a real (synthetic) PDF, no network ----
        pdf_bytes = _build_synthetic_pdf()
        parsed_document = route_ocr(pdf_bytes)
        assert parsed_document.backend_used == "pymupdf"  # native text layer, Docling never invoked
        assert len(parsed_document.pages) == 2

        # ---- 2. Seed Insurer/Product/Policy/PolicyVersion/Document ----
        insurer = Insurer(name="Insurer Testco", website_root="https://testco.test")
        session.add(insurer)
        session.flush()
        product = Product(insurer_id=insurer.id, product_type="life_cover", name="Life Cover")
        session.add(product)
        session.flush()
        policy = Policy(product_id=product.id, name="Life Cover")
        session.add(policy)
        session.flush()
        policy_version = PolicyVersion(policy_id=policy.id, version_number=1, status="current")
        session.add(policy_version)
        session.flush()
        document = Document(
            policy_version_id=policy_version.id, doc_type="pds",
            storage_key="testco/life_cover/pds/000000000000-synthetic.pdf",
            sha256_hash="0" * 64, source_url="https://testco.test/synthetic.pdf",
        )
        session.add(document)
        session.flush()

        # ---- 3. Sections: one per page (Phase-1 simplification) ----
        sections = build_sections(
            session, parsed_document, policy_version_id=policy_version.id, document_id=document.id
        )
        assert len(sections) == 2

        # ---- 4. Extraction + citation verification, per section ----
        provider = MockLLMProvider(canned=[
            ("Total and Permanent Disability", _PAGE1_RESPONSE),
            ("trauma conditions", _PAGE2_RESPONSE),
        ])
        outcomes = [
            process_section(
                session, provider,
                policy_version_id=policy_version.id, document_id=document.id,
                section=section, parsed_document=parsed_document,
            )
            for section in sections
        ]
        session.commit()

        # tpd_definition + eligibility_rule from page 1, trauma_conditions from page 2 - all verified
        assert sum(o.persisted_counts.get("graded_facts", 0) for o in outcomes) == 2
        assert sum(o.persisted_counts.get("eligibility_rules", 0) for o in outcomes) == 1
        # the fabricated benefit quote on page 2 was rejected, not persisted
        assert sum(o.rejected_counts.get("benefits", 0) for o in outcomes) == 1
        assert sum(o.persisted_counts.get("benefits", 0) for o in outcomes) == 0
        assert session.execute(select(Benefit)).scalars().first() is None

        # ---- 5. Repository hydration ----
        profiles = load_product_profiles(session, product_type="life_cover")
        assert len(profiles) == 1
        profile = profiles[0]
        assert profile.insurer == "Insurer Testco"
        assert profile.tpd_definition.basis.value == "own_occupation"
        assert profile.trauma_condition_count == 40
        assert profile.eligibility.age_min == 18
        assert profile.eligibility.age_max == 65

        # ---- 6. Grading engine (existing, untouched) ----
        filters = CompareFilters(age=30, smoker_status=SmokerStatus.NON_SMOKER, occupation_category="Professional", product_type="life_cover")
        reports = run_compare(profiles, filters)
        assert len(reports) == 1
        assert reports[0].eligible is True
        assert reports[0].criteria["tpd_definition"].score == 100.0  # own_occupation is the top TPD score

    # ---- 7. Through FastAPI, not just direct function calls ----
    def override_get_db():
        with Session_() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/compare/life",
            json={"age": 30, "smoker_status": "non_smoker", "occupation_category": "Professional", "product_type": "life_cover"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data_source"] == "extracted_verified"
        assert len(body["results"]) == 1
        assert body["results"][0]["insurer"] == "Insurer Testco"
        assert body["results"][0]["criteria"]["tpd_definition"]["raw_value"] == "own_occupation"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
