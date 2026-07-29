"""The Downloader (docs/04-CRAWLER-STRATEGY.md's "Download & version
detection" stage) - fetch, hash, version-diff, store. The crawler
(workers/crawler/) only discovers candidate URLs; nothing before this pass
ever fetched, hashed, or persisted a document.

Handoff from the crawler is a file, not a queue: Scrapy's built-in `-o`
flag (`scrapy crawl policy_documents ... -o discovered/aia.jsonl`) writes
DiscoveredDocumentItem rows as JSON Lines - no Celery/queue infra exists
yet to make anything fancier worthwhile, and a JSONL file is trivially
inspectable/versionable as a test fixture.

Lives under backend/app/ rather than a new workers/downloader/ package
(per this pass's design decisions) - it needs backend/app/db/models.py
directly, and there's no queue to make "worker" a real distinction yet.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, PolicyVersion
from app.storage.base import StorageAdapter
from app.storage.keys import build_storage_key


@dataclass(frozen=True)
class HeadResult:
    status: int
    etag: str | None
    last_modified: str | None


class Fetcher(Protocol):
    def head(self, url: str) -> HeadResult:
        ...

    def get(self, url: str) -> bytes:
        ...


@dataclass(frozen=True)
class DownloadOutcome:
    document: Document | None
    is_new: bool
    is_changed: bool
    skipped_reason: str | None  # "unchanged_etag" | "duplicate_hash" | None


def download_and_version(
    session: Session,
    fetcher: Fetcher,
    storage: StorageAdapter,
    *,
    policy_version_id,
    insurer_name: str,
    product_type: str,
    doc_type: str,
    document_url: str,
    filename: str | None = None,
) -> DownloadOutcome:
    filename = filename or document_url.rsplit("/", 1)[-1] or "document.pdf"

    existing = session.execute(
        select(Document).where(
            Document.policy_version_id == policy_version_id,
            Document.source_url == document_url,
        )
    ).scalar_one_or_none()

    head = fetcher.head(document_url)

    if existing is not None:
        unchanged = (head.etag is not None and head.etag == existing.etag) or (
            head.last_modified is not None and head.last_modified == existing.last_modified
        )
        if unchanged:
            return DownloadOutcome(
                document=existing, is_new=False, is_changed=False, skipped_reason="unchanged_etag"
            )

    content = fetcher.get(document_url)
    sha256_hex = hashlib.sha256(content).hexdigest()

    duplicate = session.execute(
        select(Document).where(Document.sha256_hash == sha256_hex)
    ).scalars().first()

    if duplicate is not None:
        storage_key = duplicate.storage_key
        skipped_reason = "duplicate_hash"
    else:
        storage_key = build_storage_key(
            insurer=insurer_name,
            product_type=product_type,
            doc_type=doc_type,
            sha256_hex=sha256_hex,
            filename=filename,
        )
        skipped_reason = None

    storage.put(storage_key, content)

    document = Document(
        policy_version_id=policy_version_id,
        doc_type=doc_type,
        storage_key=storage_key,
        sha256_hash=sha256_hex,
        etag=head.etag,
        last_modified=head.last_modified,
        source_url=document_url,
    )
    session.add(document)

    policy_version = session.get(PolicyVersion, policy_version_id)
    if policy_version is not None:
        policy_version.version_number += 1

    session.flush()

    return DownloadOutcome(
        document=document,
        is_new=duplicate is None,
        is_changed=existing is not None,
        skipped_reason=skipped_reason,
    )
