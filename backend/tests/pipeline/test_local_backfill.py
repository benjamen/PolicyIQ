import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Base, EligibilityRule
from app.pipeline.apply_reviewed_extractions import _load_extractions_by_section_hash, apply_extractions
from app.pipeline.downloader import HeadResult
from app.pipeline.dump_sections_for_review import dump_sections
from app.providers.llm import PrecomputedProvider
from app.storage.local_disk import LocalDiskStorage


class FakeFetcher:
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


def test_dump_then_apply_round_trip_persists_verified_facts(session, tmp_path, synthetic_pdf_bytes):
    """The whole point of the local backfill: Phase A (no LLM at all) dumps
    real section text; Phase B applies a hand-authored extraction through
    process_section() unchanged, so citation verification still runs for
    real against the real OCR'd text - same guarantee as the API path."""
    input_path = _write_jsonl(
        tmp_path / "chubb.jsonl",
        [
            {
                "insurer": "Chubb Life NZ",
                "source_page_url": "https://chubb.com/nz-en/policies",
                "document_url": "https://chubb.com/nz-en/pds.pdf",
                "link_text": "Product Disclosure Statement",
                "doc_type_guess": "pds",
                "in_scope": True,
            }
        ],
    )
    fetcher = FakeFetcher({"https://chubb.com/nz-en/pds.pdf": ("etag-v1", None, synthetic_pdf_bytes)})
    storage = LocalDiskStorage(tmp_path / "storage")
    sections_path = str(tmp_path / "chubb.sections.jsonl")

    dump_stats = dump_sections(
        input_path, sections_path, product_type="life_cover",
        session=session, fetcher=fetcher, storage=storage,
    )

    assert dump_stats["documents_downloaded"] == 1
    assert dump_stats["sections_dumped"] == 1

    with open(sections_path, encoding="utf-8") as f:
        dumped = json.loads(f.readline())
    assert "Total and Permanent Disability" in dumped["text"]

    extraction_json = json.dumps(
        {
            "graded_facts": [],
            "eligibility_rules": [
                {
                    "smoker_status": "any",
                    "age_min": 18,
                    "age_max": 65,
                    "restriction_type": "none",
                    "note": None,
                    "confidence": 0.95,
                    "source_quote": "This policy is available to applicants aged 18 to 65, smoker or non-smoker.",
                }
            ],
            "benefits": [],
            "limits": [],
            "exclusions": [],
            "definitions": [],
            "waiting_periods": [],
            "optional_benefits": [],
        }
    )
    extractions_path = str(tmp_path / "chubb.extractions.jsonl")
    _write_jsonl(extractions_path, [{"section_id": dumped["section_id"], "extraction_json": extraction_json}])

    extractions_by_hash = _load_extractions_by_section_hash(extractions_path, sections_path)
    provider = PrecomputedProvider(extractions_by_hash)

    apply_stats = apply_extractions(
        insurer_name="Chubb Life NZ", session=session, storage=storage, provider=provider,
    )

    assert apply_stats["documents_processed"] == 1
    assert apply_stats["documents_failed"] == 0
    assert apply_stats["sections_processed"] == 1
    assert apply_stats["sections_unauthored"] == 0
    assert apply_stats["facts_persisted"] == 1
    assert apply_stats["facts_rejected"] == 0

    rules = session.execute(select(EligibilityRule)).scalars().all()
    assert len(rules) == 1
    assert rules[0].age_min == 18
    assert rules[0].age_max == 65


def test_apply_surfaces_unauthored_sections_instead_of_silently_reporting_success(session, tmp_path, synthetic_pdf_bytes):
    """process_section() never raises on an extraction failure - a missing
    PrecomputedProvider entry comes back as a typed outcome.failure after
    extract_with_retry's internal retries are exhausted, not an exception.
    A caller that doesn't inspect the return value would report a clean
    run even though nothing was actually authored yet - this must be a
    visible, countable gap instead."""
    input_path = _write_jsonl(
        tmp_path / "mas.jsonl",
        [
            {
                "insurer": "MAS",
                "source_page_url": "https://mas.co.nz/policies",
                "document_url": "https://mas.co.nz/pds.pdf",
                "link_text": "PDS",
                "doc_type_guess": "pds",
                "in_scope": True,
            }
        ],
    )
    fetcher = FakeFetcher({"https://mas.co.nz/pds.pdf": ("etag-v1", None, synthetic_pdf_bytes)})
    storage = LocalDiskStorage(tmp_path / "storage")
    sections_path = str(tmp_path / "mas.sections.jsonl")

    dump_sections(input_path, sections_path, product_type="life_cover", session=session, fetcher=fetcher, storage=storage)

    provider = PrecomputedProvider({})  # nothing authored
    stats = apply_extractions(insurer_name="MAS", session=session, storage=storage, provider=provider)

    assert stats["documents_failed"] == 0  # the document itself processes fine
    assert stats["documents_processed"] == 1
    assert stats["sections_unauthored"] == 1  # but the gap is visible, not silent
    assert stats["facts_persisted"] == 0
