import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, Document, Insurer, Policy, PolicyVersion, Product
from app.pipeline.downloader import HeadResult, download_and_version
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


@pytest.fixture
def policy_version_id(session):
    insurer = Insurer(name="AIA New Zealand", website_root="https://aia.co.nz")
    session.add(insurer)
    session.flush()
    product = Product(insurer_id=insurer.id, product_type="life_cover", name="Life Cover")
    session.add(product)
    session.flush()
    policy = Policy(product_id=product.id, name="Life Cover Policy")
    session.add(policy)
    session.flush()
    pv = PolicyVersion(policy_id=policy.id, version_number=1)
    session.add(pv)
    session.flush()
    return pv.id


def test_first_download_creates_document_and_bumps_version(session, tmp_path, policy_version_id):
    storage = LocalDiskStorage(tmp_path)
    fetcher = FakeFetcher({"https://aia.co.nz/pds.pdf": ("etag-v1", None, b"pdf content v1")})

    outcome = download_and_version(
        session, fetcher, storage,
        policy_version_id=policy_version_id, insurer_name="AIA New Zealand",
        product_type="life_cover", doc_type="pds", document_url="https://aia.co.nz/pds.pdf",
    )

    assert outcome.is_new is True
    assert outcome.is_changed is False
    assert outcome.skipped_reason is None
    assert outcome.document.etag == "etag-v1"
    assert storage.get(outcome.document.storage_key) == b"pdf content v1"
    assert session.get(PolicyVersion, policy_version_id).version_number == 2


def test_unchanged_etag_is_skipped(session, tmp_path, policy_version_id):
    storage = LocalDiskStorage(tmp_path)
    url = "https://aia.co.nz/pds.pdf"
    fetcher = FakeFetcher({url: ("etag-v1", None, b"pdf content v1")})

    first = download_and_version(
        session, fetcher, storage,
        policy_version_id=policy_version_id, insurer_name="AIA New Zealand",
        product_type="life_cover", doc_type="pds", document_url=url,
    )
    session.commit()

    second = download_and_version(
        session, fetcher, storage,
        policy_version_id=policy_version_id, insurer_name="AIA New Zealand",
        product_type="life_cover", doc_type="pds", document_url=url,
    )

    assert second.skipped_reason == "unchanged_etag"
    assert second.document.id == first.document.id


def test_changed_etag_creates_new_document_and_bumps_version_again(session, tmp_path, policy_version_id):
    storage = LocalDiskStorage(tmp_path)
    url = "https://aia.co.nz/pds.pdf"
    fetcher = FakeFetcher({url: ("etag-v1", None, b"pdf content v1")})

    download_and_version(
        session, fetcher, storage,
        policy_version_id=policy_version_id, insurer_name="AIA New Zealand",
        product_type="life_cover", doc_type="pds", document_url=url,
    )
    session.commit()
    version_after_first = session.get(PolicyVersion, policy_version_id).version_number

    fetcher_v2 = FakeFetcher({url: ("etag-v2", None, b"pdf content v2 - changed")})
    outcome = download_and_version(
        session, fetcher_v2, storage,
        policy_version_id=policy_version_id, insurer_name="AIA New Zealand",
        product_type="life_cover", doc_type="pds", document_url=url,
    )

    assert outcome.is_changed is True
    assert outcome.skipped_reason is None
    assert session.get(PolicyVersion, policy_version_id).version_number == version_after_first + 1


def test_identical_bytes_at_different_url_reuses_storage_key(session, tmp_path, policy_version_id):
    storage = LocalDiskStorage(tmp_path)
    url_a = "https://aia.co.nz/pds-mirror-a.pdf"
    url_b = "https://aia.co.nz/pds-mirror-b.pdf"
    same_bytes = b"identical pdf content served from two urls"

    fetcher = FakeFetcher({
        url_a: ("etag-a", None, same_bytes),
        url_b: ("etag-b", None, same_bytes),
    })

    first = download_and_version(
        session, fetcher, storage,
        policy_version_id=policy_version_id, insurer_name="AIA New Zealand",
        product_type="life_cover", doc_type="pds", document_url=url_a,
    )
    session.commit()

    second = download_and_version(
        session, fetcher, storage,
        policy_version_id=policy_version_id, insurer_name="AIA New Zealand",
        product_type="life_cover", doc_type="pds", document_url=url_b,
    )

    assert second.skipped_reason == "duplicate_hash"
    assert second.document.storage_key == first.document.storage_key
    assert second.document.id != first.document.id  # separate Document row for the separate URL
