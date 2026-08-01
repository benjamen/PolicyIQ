"""Exercises GET /api/v1/documents/{document_id}/pages/{page} - the citation
"view source" endpoint. Keyed by (document_id, page) rather than a separate
section_id since every SourceRef already carries exactly that pair (see
app/domain/models.py's SourceRef.document_id docstring) - both the general
document-diff path (Benefit/Limit/Exclusion, which has a real section) and
the life comparison path (GradedFact/EligibilityRule, which never had a
section_id) can use the same lookup."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Document, Section
from app.db.session import get_db
from app.main import app

client = TestClient(app)


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


def test_returns_persisted_text_for_a_real_section():
    engine, TestSession = _make_session()
    with TestSession() as session:
        document = Document(
            policy_version_id="11111111-1111-1111-1111-111111111111",
            doc_type="wording", storage_key="tower/house/test.pdf",
            sha256_hash="a" * 64, source_url="https://example.com/test.pdf", page_count=1,
        )
        session.add(document)
        session.flush()
        session.add(Section(
            policy_version_id="11111111-1111-1111-1111-111111111111",
            document_id=document.id, page_start=4, page_end=4,
            text="Retaining walls (total) $25,000",
        ))
        session.commit()
        document_id = str(document.id)

    def override_get_db():
        with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        resp = client.get(f"/api/v1/documents/{document_id}/pages/4")
        assert resp.status_code == 200
        body = resp.json()
        assert body["document_id"] == document_id
        assert body["page"] == 4
        assert body["text"] == "Retaining walls (total) $25,000"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_404_when_no_section_matches_that_page():
    engine, TestSession = _make_session()
    with TestSession() as session:
        document = Document(
            policy_version_id="11111111-1111-1111-1111-111111111111",
            doc_type="wording", storage_key="tower/house/test.pdf",
            sha256_hash="a" * 64, source_url="https://example.com/test.pdf", page_count=1,
        )
        session.add(document)
        session.flush()
        session.add(Section(
            policy_version_id="11111111-1111-1111-1111-111111111111",
            document_id=document.id, page_start=4, page_end=4, text="real text",
        ))
        session.commit()
        document_id = str(document.id)

    def override_get_db():
        with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        resp = client.get(f"/api/v1/documents/{document_id}/pages/99")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_404_when_section_exists_but_predates_the_text_backfill():
    """A Section row can exist with text=None (either not yet backfilled, or
    ingested before df3a5db0641e_add_section_text_column.py) - must be a
    404, not a 200 with an empty/null string that looks like a confirmed-
    empty page."""
    engine, TestSession = _make_session()
    with TestSession() as session:
        document = Document(
            policy_version_id="11111111-1111-1111-1111-111111111111",
            doc_type="wording", storage_key="tower/house/test.pdf",
            sha256_hash="a" * 64, source_url="https://example.com/test.pdf", page_count=1,
        )
        session.add(document)
        session.flush()
        session.add(Section(
            policy_version_id="11111111-1111-1111-1111-111111111111",
            document_id=document.id, page_start=4, page_end=4, text=None,
        ))
        session.commit()
        document_id = str(document.id)

    def override_get_db():
        with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        resp = client.get(f"/api/v1/documents/{document_id}/pages/4")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_404_for_an_unknown_document_id():
    engine, TestSession = _make_session()

    def override_get_db():
        with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        resp = client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000/pages/1")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
