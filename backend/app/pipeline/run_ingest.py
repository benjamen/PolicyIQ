"""CLI orchestrator: crawler discovery JSONL -> download -> OCR -> sections
-> extraction. Ties together every pipeline stage built this pass into a
single run against one insurer's real crawl output.

Handoff from the crawler is a file (docs/04-CRAWLER-STRATEGY.md): Scrapy's
`-o` flag writes DiscoveredDocumentItem rows as JSON Lines
(`scrapy crawl policy_documents -a insurer="AIA New Zealand" -o discovered/aia.jsonl`).

Extraction uses whatever app.providers.llm.get_provider() returns for the
current environment (LLM_PROVIDER/LLM_KEY/LLM_MODEL - see .env.example). If
neither is set, extraction is skipped and reported rather than run with
MockLLMProvider (which only answers pre-canned test inputs and would crash
or fabricate a result against arbitrary real document text) - matching this
project's fail-closed principle (docs/01-ARCHITECTURE.md).
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Insurer, Policy, PolicyVersion, Product
from app.db.session import SessionLocal
from app.ocr.router import route_ocr
from app.pipeline.downloader import HeadResult, download_and_version
from app.pipeline.extraction import process_section
from app.pipeline.sections import build_sections
from app.providers.llm import LLMProvider, get_provider
from app.storage.base import StorageAdapter
from app.storage.local_disk import storage_from_env


class HttpxFetcher:
    """Real HTTP Fetcher (downloader.py's Fetcher Protocol), backed by httpx
    (already a dependency - no new package needed just for this CLI)."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def head(self, url: str) -> HeadResult:
        resp = httpx.head(url, timeout=self._timeout, follow_redirects=True)
        return HeadResult(
            status=resp.status_code,
            etag=resp.headers.get("etag"),
            last_modified=resp.headers.get("last-modified"),
        )

    def get(self, url: str) -> bytes:
        resp = httpx.get(url, timeout=self._timeout, follow_redirects=True)
        resp.raise_for_status()
        return resp.content


def _get_or_create_insurer(session: Session, name: str, website_root: str) -> Insurer:
    insurer = session.execute(select(Insurer).where(Insurer.name == name)).scalar_one_or_none()
    if insurer is None:
        insurer = Insurer(name=name, website_root=website_root)
        session.add(insurer)
        session.flush()
    return insurer


def _get_or_create_product(session: Session, insurer_id: uuid.UUID, product_type: str) -> Product:
    product = session.execute(
        select(Product).where(Product.insurer_id == insurer_id, Product.product_type == product_type)
    ).scalar_one_or_none()
    if product is None:
        product = Product(insurer_id=insurer_id, product_type=product_type, name=product_type)
        session.add(product)
        session.flush()
    return product


def _get_or_create_policy(session: Session, product_id: uuid.UUID, name: str) -> Policy:
    policy = session.execute(select(Policy).where(Policy.product_id == product_id)).scalar_one_or_none()
    if policy is None:
        policy = Policy(product_id=product_id, name=name)
        session.add(policy)
        session.flush()
    return policy


def _get_or_create_current_policy_version(session: Session, policy_id: uuid.UUID) -> PolicyVersion:
    version = session.execute(
        select(PolicyVersion).where(PolicyVersion.policy_id == policy_id, PolicyVersion.status == "current")
    ).scalar_one_or_none()
    if version is None:
        version = PolicyVersion(policy_id=policy_id, version_number=0, status="current")
        session.add(version)
        session.flush()
    return version


@dataclass
class IngestStats:
    rows_seen: int = 0
    documents_downloaded: int = 0
    documents_unchanged: int = 0
    sections_built: int = 0
    extraction_skipped_no_provider: bool = False


def run_ingest(
    input_path: str,
    *,
    product_type: str,
    session: Session,
    fetcher,
    storage: StorageAdapter,
    provider: LLMProvider | None,
) -> IngestStats:
    stats = IngestStats()

    with open(input_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            stats.rows_seen += 1

            insurer_name = row["insurer"]
            document_url = row["document_url"]
            doc_type = row.get("doc_type_guess") or "unknown"

            root_url = row.get("source_page_url") or document_url
            parts = urlsplit(root_url)
            website_root = f"{parts.scheme}://{parts.netloc}"

            insurer = _get_or_create_insurer(session, insurer_name, website_root)
            product = _get_or_create_product(session, insurer.id, product_type)
            policy = _get_or_create_policy(session, product.id, name=product_type)
            policy_version = _get_or_create_current_policy_version(session, policy.id)

            outcome = download_and_version(
                session, fetcher, storage,
                policy_version_id=policy_version.id,
                insurer_name=insurer_name,
                product_type=product_type,
                doc_type=doc_type,
                document_url=document_url,
            )

            if outcome.skipped_reason == "unchanged_etag":
                stats.documents_unchanged += 1
                continue
            stats.documents_downloaded += 1

            content = storage.get(outcome.document.storage_key)
            parsed_document = route_ocr(content)

            sections = build_sections(
                session, parsed_document,
                policy_version_id=policy_version.id, document_id=outcome.document.id,
            )
            stats.sections_built += len(sections)

            if provider is None:
                stats.extraction_skipped_no_provider = True
                continue

            for section in sections:
                process_section(
                    session, provider,
                    policy_version_id=policy_version.id, document_id=outcome.document.id,
                    section=section, parsed_document=parsed_document,
                )

    session.commit()
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", required=True,
        help="Path to a crawler JSONL output file (DiscoveredDocumentItem rows, one per line)",
    )
    parser.add_argument("--product-type", default="life_cover")
    args = parser.parse_args(argv)

    session = SessionLocal()
    storage = storage_from_env()
    fetcher = HttpxFetcher()
    provider = get_provider()

    try:
        stats = run_ingest(
            args.input, product_type=args.product_type,
            session=session, fetcher=fetcher, storage=storage, provider=provider,
        )
    finally:
        session.close()

    print(
        f"rows_seen={stats.rows_seen} documents_downloaded={stats.documents_downloaded} "
        f"documents_unchanged={stats.documents_unchanged} sections_built={stats.sections_built}"
    )
    if stats.extraction_skipped_no_provider:
        print("extraction skipped: LLM_PROVIDER/LLM_KEY not set (see .env.example, app/providers/llm.py)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
