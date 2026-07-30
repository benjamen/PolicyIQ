"""Phase A of a one-off local backfill (2026-07-30): NVIDIA NIM's free-tier
RPM limit throttled a large real batch hard (Asteron Life's 102 in-scope
documents only got ~17 through in a 2-hour window before timing out - see
groq-rate-limit-backoff/policyiq-ops wiki for the same problem on Groq).
Rather than fight a rate-limited free tier for the rest of the backlog,
this dumps every in-scope section's real OCR'd text to a review file for
someone (a person, or Claude Code working through it directly in a
session) to author SectionExtraction JSON against by hand - no API call.

Runs the exact same crawl-output -> download -> OCR -> section pipeline as
run_ingest.py (reusing its real building blocks, not duplicating them),
but stops before extraction and persists the Section rows for
apply_reviewed_extractions.py (Phase B) to attach facts to afterward via
PrecomputedProvider, through process_section() completely unchanged - see
that module for why this can't just re-call run_ingest() directly (its
download-triggers-everything loop structure would skip already-downloaded
documents as "unchanged" and never reach extraction for them again).

Safe to re-run against the same insurer: download_and_version's etag/
sha256 check means already-downloaded documents (either from an earlier
automated NVIDIA/Groq run, or an earlier invocation of this script) are
skipped exactly like run_ingest.py does, so this only ever does new work
for documents that aren't already fully in the database.
"""

from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import urlsplit

import httpx
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.ocr.router import route_ocr
from app.pipeline.downloader import HeadResult, download_and_version
from app.pipeline.run_ingest import (
    _get_or_create_current_policy_version,
    _get_or_create_insurer,
    _get_or_create_policy,
    _get_or_create_product,
)
from app.pipeline.sections import build_sections
from app.storage.base import StorageAdapter
from app.storage.local_disk import storage_from_env


class HttpxFetcher:
    """Same as run_ingest.py's - duplicated rather than imported since
    run_ingest.py doesn't export it as a reusable top-level name outside
    its own CLI wiring (it's constructed inline in main())."""

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


def dump_sections(
    input_path: str,
    output_path: str,
    *,
    product_type: str,
    session: Session,
    fetcher,
    storage: StorageAdapter,
) -> dict[str, int]:
    stats = {
        "rows_seen": 0,
        "documents_downloaded": 0,
        "documents_unchanged": 0,
        "documents_failed": 0,
        "documents_out_of_scope": 0,
        "sections_dumped": 0,
    }

    with open(input_path, encoding="utf-8") as f, open(output_path, "w", encoding="utf-8") as out:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            stats["rows_seen"] += 1
            document_url = row["document_url"]

            if row.get("in_scope", True) is False:
                stats["documents_out_of_scope"] += 1
                continue

            try:
                insurer_name = row["insurer"]
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
                    stats["documents_unchanged"] += 1
                    session.commit()
                    continue
                stats["documents_downloaded"] += 1

                content = storage.get(outcome.document.storage_key)
                parsed_document = route_ocr(content)

                sections = build_sections(
                    session, parsed_document,
                    policy_version_id=policy_version.id, document_id=outcome.document.id,
                )
                session.commit()

                for section in sections:
                    page = parsed_document.page(section.page_start)
                    section_text = page.text if page else ""
                    if not section_text.strip():
                        continue
                    out.write(
                        json.dumps(
                            {
                                "insurer": insurer_name,
                                "document_url": document_url,
                                "section_id": str(section.id),
                                "page": section.page_start,
                                "text": section_text,
                            }
                        )
                        + "\n"
                    )
                    stats["sections_dumped"] += 1

            except Exception as exc:  # noqa: BLE001 - same per-document isolation as run_ingest.py
                session.rollback()
                stats["documents_failed"] += 1
                print(f"FAILED: {document_url}: {exc}")

    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Crawler JSONL output (same as run_ingest.py --input)")
    parser.add_argument("--output", required=True, help="Where to write the section-review JSONL")
    parser.add_argument("--product-type", default="life_cover")
    args = parser.parse_args(argv)

    session = SessionLocal()
    storage = storage_from_env()
    fetcher = HttpxFetcher()

    try:
        stats = dump_sections(
            args.input, args.output, product_type=args.product_type,
            session=session, fetcher=fetcher, storage=storage,
        )
    finally:
        session.close()

    print(
        f"rows_seen={stats['rows_seen']} documents_downloaded={stats['documents_downloaded']} "
        f"documents_unchanged={stats['documents_unchanged']} documents_failed={stats['documents_failed']} "
        f"documents_out_of_scope={stats['documents_out_of_scope']} sections_dumped={stats['sections_dumped']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
