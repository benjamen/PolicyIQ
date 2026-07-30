"""Phase B of the local backfill (see dump_sections_for_review.py for
Phase A and the full rationale). Takes an authored extractions file -
JSONL of `{"section_id": ..., "extraction_json": <raw SectionExtraction
JSON string>}`, one per section dump_sections_for_review.py produced -
and feeds each through process_section() completely unchanged, via
PrecomputedProvider, so every existing guarantee (verified source_quote
against the real OCR'd page text, page/paragraph_ref from the real
Section row) applies exactly as it does for the Groq/NVIDIA API path.

Deliberately does NOT re-call run_ingest()'s download-triggers-everything
loop: that loop treats an already-downloaded (etag-unchanged) document as
"nothing to do" and would skip every document Phase A already downloaded
without ever reaching extraction. Instead, this queries the Document/
Section rows Phase A already persisted directly, re-derives parsed_document
by re-running route_ocr() against the same stored bytes (OCR is pure - same
bytes in, same ParsedDocument out, needed again here only because it isn't
persisted anywhere, just the Sections it produced), and calls
process_section() once per existing Section row.
"""

from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, Insurer, Policy, PolicyVersion, Product, Section
from app.db.session import SessionLocal
from app.ocr.router import route_ocr
from app.pipeline.extraction import process_section
from app.providers.llm import PrecomputedProvider
from app.storage.base import StorageAdapter
from app.storage.local_disk import storage_from_env


def _load_extractions_by_section_hash(extractions_path: str, sections_path: str) -> dict[str, str]:
    """Authored extractions are keyed by section_id (human/Claude-friendly
    while authoring); PrecomputedProvider looks up by a hash of the exact
    section_text (the only thing extract() receives - see llm.py). Cross-
    reference the two files to build the hash-keyed dict the provider
    actually needs."""
    text_by_section_id: dict[str, str] = {}
    with open(sections_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            text_by_section_id[row["section_id"]] = row["text"]

    extractions_by_hash: dict[str, str] = {}
    with open(extractions_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            section_id = row["section_id"]
            if section_id not in text_by_section_id:
                raise ValueError(f"apply_reviewed_extractions: section_id {section_id} not found in {sections_path}")
            key = PrecomputedProvider.section_key(text_by_section_id[section_id])
            extractions_by_hash[key] = row["extraction_json"]

    return extractions_by_hash


def apply_extractions(
    *,
    insurer_name: str,
    session: Session,
    storage: StorageAdapter,
    provider: PrecomputedProvider,
) -> dict[str, int]:
    stats = {
        "documents_processed": 0,
        "documents_failed": 0,
        "sections_processed": 0,
        "sections_unauthored": 0,
        "facts_persisted": 0,
        "facts_rejected": 0,
    }

    documents = session.execute(
        select(Document)
        .join(PolicyVersion, PolicyVersion.id == Document.policy_version_id)
        .join(Policy, Policy.id == PolicyVersion.policy_id)
        .join(Product, Product.id == Policy.product_id)
        .join(Insurer, Insurer.id == Product.insurer_id)
        .where(Insurer.name == insurer_name)
    ).scalars().all()

    for document in documents:
        try:
            content = storage.get(document.storage_key)
            parsed_document = route_ocr(content)

            sections = session.execute(
                select(Section)
                .where(Section.document_id == document.id)
                .order_by(Section.page_start)
            ).scalars().all()

            for section in sections:
                # process_section() never raises on an extraction failure -
                # a bad/missing PrecomputedProvider entry comes back as a
                # typed SectionExtractionOutcome.failure, not an exception
                # (retried internally by extract_with_retry first) - so
                # this must inspect the return value or a whole document's
                # worth of gaps would silently look like a clean run.
                outcome = process_section(
                    session, provider,
                    policy_version_id=document.policy_version_id, document_id=document.id,
                    section=section, parsed_document=parsed_document,
                )
                stats["sections_processed"] += 1
                if outcome.failure is not None:
                    stats["sections_unauthored"] += 1
                    print(f"UNAUTHORED: {document.source_url} section {section.id} (page {section.page_start})")
                stats["facts_persisted"] += sum(outcome.persisted_counts.values())
                stats["facts_rejected"] += sum(outcome.rejected_counts.values())

            session.commit()
            stats["documents_processed"] += 1
        except Exception as exc:  # noqa: BLE001 - same per-document isolation as run_ingest.py
            session.rollback()
            stats["documents_failed"] += 1
            print(f"FAILED: {document.source_url}: {exc}")

    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--insurer", required=True, help='Exact insurer name, e.g. "Chubb Life NZ"')
    parser.add_argument("--sections", required=True, help="Phase A's section-review JSONL")
    parser.add_argument("--extractions", required=True, help="Authored extractions JSONL: section_id + extraction_json")
    args = parser.parse_args(argv)

    session = SessionLocal()
    storage = storage_from_env()

    try:
        extractions_by_hash = _load_extractions_by_section_hash(args.extractions, args.sections)
        provider = PrecomputedProvider(extractions_by_hash)
        stats = apply_extractions(insurer_name=args.insurer, session=session, storage=storage, provider=provider)
    finally:
        session.close()

    print(
        f"documents_processed={stats['documents_processed']} documents_failed={stats['documents_failed']} "
        f"sections_processed={stats['sections_processed']} sections_unauthored={stats['sections_unauthored']} "
        f"facts_persisted={stats['facts_persisted']} facts_rejected={stats['facts_rejected']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
