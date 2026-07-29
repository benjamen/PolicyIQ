import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Base, GradedFact, Insurer, Policy, PolicyVersion, Product, Section
from app.pipeline.downloader import HeadResult
from app.pipeline.run_ingest import run_ingest
from app.storage.local_disk import LocalDiskStorage


class FakeFetcher:
    """In-memory fetcher: url -> (etag, last_modified, bytes). No network."""

    def __init__(self, responses: dict[str, tuple[str | None, str | None, bytes]]):
        self._responses = responses

    def head(self, url: str) -> HeadResult:
        etag, last_modified, _content = self._responses[url]
        return HeadResult(status=200, etag=etag, last_modified=last_modified)

    def get(self, url: str) -> bytes:
        return self._responses[url][2]


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return str(path)


def test_first_run_creates_insurer_product_policy_and_sections_but_skips_extraction(
    session, tmp_path, synthetic_pdf_bytes
):
    input_path = _write_jsonl(tmp_path / "aia.jsonl", [
        {
            "insurer": "AIA New Zealand",
            "source_page_url": "https://aia.co.nz/policies",
            "document_url": "https://aia.co.nz/pds.pdf",
            "link_text": "Product Disclosure Statement",
            "doc_type_guess": "pds",
        }
    ])
    fetcher = FakeFetcher({"https://aia.co.nz/pds.pdf": ("etag-v1", None, synthetic_pdf_bytes)})
    storage = LocalDiskStorage(tmp_path / "storage")

    stats = run_ingest(
        input_path, product_type="life_cover",
        session=session, fetcher=fetcher, storage=storage, provider=None,
    )

    assert stats.rows_seen == 1
    assert stats.documents_downloaded == 1
    assert stats.documents_unchanged == 0
    assert stats.sections_built == 1
    assert stats.extraction_skipped_no_provider is True

    insurer = session.execute(select(Insurer).where(Insurer.name == "AIA New Zealand")).scalar_one()
    product = session.execute(select(Product).where(Product.insurer_id == insurer.id)).scalar_one()
    assert product.product_type == "life_cover"
    policy = session.execute(select(Policy).where(Policy.product_id == product.id)).scalar_one()
    policy_version = session.execute(
        select(PolicyVersion).where(PolicyVersion.policy_id == policy.id)
    ).scalar_one()
    assert policy_version.status == "current"
    assert session.execute(select(Section)).scalars().first() is not None
    # no provider configured -> nothing was ever extracted, not fabricated
    assert session.execute(select(GradedFact)).scalars().first() is None


def test_second_run_with_unchanged_etag_reuses_the_same_policy_version(
    session, tmp_path, synthetic_pdf_bytes
):
    input_path = _write_jsonl(tmp_path / "aia.jsonl", [
        {
            "insurer": "AIA New Zealand",
            "source_page_url": "https://aia.co.nz/policies",
            "document_url": "https://aia.co.nz/pds.pdf",
            "link_text": "Product Disclosure Statement",
            "doc_type_guess": "pds",
        }
    ])
    fetcher = FakeFetcher({"https://aia.co.nz/pds.pdf": ("etag-v1", None, synthetic_pdf_bytes)})
    storage = LocalDiskStorage(tmp_path / "storage")

    run_ingest(input_path, product_type="life_cover", session=session, fetcher=fetcher, storage=storage, provider=None)
    stats2 = run_ingest(input_path, product_type="life_cover", session=session, fetcher=fetcher, storage=storage, provider=None)

    assert stats2.documents_downloaded == 0
    assert stats2.documents_unchanged == 1
    assert session.execute(select(Insurer)).scalars().all().__len__() == 1
    assert session.execute(select(PolicyVersion)).scalars().all().__len__() == 1
