"""Exercises GET /api/v1/insurers/coverage - cross-references the static
market catalog (app/domain/nz_insurer_catalog.py) against real DB rows.
"offered" comes purely from the catalog; "covered" must only ever be true
when a real Document exists, never from an Insurer/Product row alone
(those exist as soon as a one-off setup script runs, before any document
is attached - see app/db/repository.py's docstring for why that
distinction matters)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Document, Insurer, Policy, PolicyVersion, Product, Section
from app.db.session import get_db
from app.domain.nz_insurer_catalog import NZ_INSURER_CATALOG
from app.main import app

client = TestClient(app)


def test_coverage_on_empty_db_lists_every_catalog_insurer_as_not_covered():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        resp = client.get("/api/v1/insurers/coverage")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["results"]) == len(NZ_INSURER_CATALOG)
        for row in body["results"]:
            assert all(t["covered"] is False for t in row["types"])
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_coverage_reflects_a_real_document_but_not_an_insurer_row_alone():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    with TestSession() as session:
        # AMI: full chain down to a real Document -> should show covered=True.
        ami = Insurer(name="AMI", website_root="https://www.ami.co.nz")
        session.add(ami)
        session.flush()
        ami_product = Product(insurer_id=ami.id, product_type="home_contents", name="Home & Contents")
        session.add(ami_product)
        session.flush()
        ami_policy = Policy(product_id=ami_product.id, name="Home & Contents")
        session.add(ami_policy)
        session.flush()
        ami_pv = PolicyVersion(policy_id=ami_policy.id, version_number=1, status="current")
        session.add(ami_pv)
        session.flush()
        session.add(Document(
            policy_version_id=ami_pv.id, doc_type="wording", storage_key="ami/test.pdf",
            sha256_hash="a" * 64, source_url="https://www.ami.co.nz/test.pdf", page_count=1,
        ))

        # Tower: Insurer + Product row exist, but no Document at all yet -> must stay covered=False.
        tower = Insurer(name="Tower", website_root="https://www.tower.co.nz")
        session.add(tower)
        session.flush()
        session.add(Product(insurer_id=tower.id, product_type="home_contents", name="Home & Contents"))

        session.commit()

    def override_get_db():
        with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        resp = client.get("/api/v1/insurers/coverage")
        assert resp.status_code == 200
        by_name = {row["name"]: row for row in resp.json()["results"]}

        ami_types = {t["product_type"]: t for t in by_name["AMI"]["types"]}
        assert ami_types["home_contents"]["offered"] is True
        assert ami_types["home_contents"]["covered"] is True

        tower_types = {t["product_type"]: t for t in by_name["Tower"]["types"]}
        assert tower_types["home_contents"]["offered"] is True
        assert tower_types["home_contents"]["covered"] is False

        # A type an insurer doesn't sell should never appear as covered even
        # if it happens to have unrelated data - AMI doesn't sell life_cover.
        assert ami_types["life_cover"]["offered"] is False
        assert ami_types["life_cover"]["covered"] is False
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_every_catalog_entry_offers_at_least_one_type():
    for entry in NZ_INSURER_CATALOG:
        assert len(entry.types_offered) > 0, f"{entry.name} offers nothing"
        for t in entry.types_offered:
            assert t in ("life_cover", "home_contents", "health"), f"{entry.name} has unknown type {t}"


def test_no_duplicate_catalog_names():
    names = [entry.name for entry in NZ_INSURER_CATALOG]
    assert len(names) == len(set(names))
