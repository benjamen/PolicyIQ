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


def test_out_of_scope_documents_are_counted_and_skipped_not_downloaded(
    session, tmp_path, synthetic_pdf_bytes
):
    """The crawler flags claim forms / old investment-fund archives as
    in_scope=False rather than dropping them (still visible in the crawl
    output) - run_ingest.py must skip them before spending any download/
    OCR/LLM time, while still counting them for visibility."""
    input_path = _write_jsonl(tmp_path / "asteron.jsonl", [
        {
            "insurer": "Asteron Life",
            "source_page_url": "https://asteronlife.co.nz/claims",
            "document_url": "https://asteronlife.co.nz/claim-form.pdf",
            "link_text": "Claim Form",
            "doc_type_guess": "form",
            "in_scope": False,
        },
        {
            "insurer": "Asteron Life",
            "source_page_url": "https://asteronlife.co.nz/life-cover",
            "document_url": "https://asteronlife.co.nz/pds.pdf",
            "link_text": "Download brochure",
            "doc_type_guess": "brochure",
            "in_scope": True,
        },
    ])
    # No entry for claim-form.pdf - FakeFetcher would KeyError if run_ingest
    # ever actually tried to fetch it, proving the skip is real.
    fetcher = FakeFetcher({"https://asteronlife.co.nz/pds.pdf": ("etag-v1", None, synthetic_pdf_bytes)})
    storage = LocalDiskStorage(tmp_path / "storage")

    stats = run_ingest(
        input_path, product_type="life_cover",
        session=session, fetcher=fetcher, storage=storage, provider=None,
    )

    assert stats.rows_seen == 2
    assert stats.documents_out_of_scope == 1
    assert stats.documents_downloaded == 1


def test_one_bad_document_does_not_sink_the_rest_of_the_batch(
    session, tmp_path, synthetic_pdf_bytes, monkeypatch
):
    """Regression test for a real failure hit during the first live crawl+
    ingest run (2026-07-29): run_ingest used to commit only once, at the very
    end - an OCR exception on the FIRST document crashed the whole process
    and discarded every other document's progress too, not just the failing
    one. Two documents, same insurer; the first's OCR step raises, the
    second must still be fully processed and committed."""
    input_path = _write_jsonl(tmp_path / "partners-life.jsonl", [
        {
            "insurer": "Partners Life",
            "source_page_url": "https://partnerslife.co.nz/trauma-cover",
            "document_url": "https://partnerslife.co.nz/corrupt.pdf",
            "link_text": "Download brochure",
            "doc_type_guess": "brochure",
        },
        {
            "insurer": "Partners Life",
            "source_page_url": "https://partnerslife.co.nz/life-cover",
            "document_url": "https://partnerslife.co.nz/pds.pdf",
            "link_text": "Download brochure",
            "doc_type_guess": "brochure",
        },
    ])
    fetcher = FakeFetcher({
        "https://partnerslife.co.nz/corrupt.pdf": ("etag-bad", None, b"not a real pdf at all"),
        "https://partnerslife.co.nz/pds.pdf": ("etag-good", None, synthetic_pdf_bytes),
    })
    storage = LocalDiskStorage(tmp_path / "storage")

    import app.pipeline.run_ingest as run_ingest_module

    real_route_ocr = run_ingest_module.route_ocr

    def flaky_route_ocr(content: bytes):
        if content == b"not a real pdf at all":
            raise ValueError("simulated OCR failure - not a real PDF")
        return real_route_ocr(content)

    monkeypatch.setattr(run_ingest_module, "route_ocr", flaky_route_ocr)

    stats = run_ingest(
        input_path, product_type="life_cover",
        session=session, fetcher=fetcher, storage=storage, provider=None,
    )

    assert stats.rows_seen == 2
    assert stats.documents_failed == 1
    assert stats.sections_built == 1  # only from the document that succeeded

    # The failed document leaves no partial/orphaned rows behind - the
    # rollback discards it cleanly. Only the successful document's data
    # is actually in the database.
    from app.db.models import Document
    documents = session.execute(select(Document)).scalars().all()
    assert len(documents) == 1
    assert documents[0].storage_key.endswith("pds.pdf")
    sections = session.execute(select(Section)).scalars().all()
    assert len(sections) == 1


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
