"""Builds Section rows from a ParsedDocument. Phase 1: one Section per PDF
page - an explicit simplification, not real heading-detection (which needs
layout analysis beyond what this pass's OCR routing produces). Section is
the join point between document structure and every extracted-fact table
(docs/02-DATABASE-ERD.md's notes on why it exists)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models import Section
from app.ocr.types import ParsedDocument


def build_sections(
    session: Session, parsed_document: ParsedDocument, *, policy_version_id: uuid.UUID, document_id: uuid.UUID
) -> list[Section]:
    sections: list[Section] = []
    for page in parsed_document.pages:
        section = Section(
            policy_version_id=policy_version_id,
            document_id=document_id,
            heading=None,
            page_start=page.page_number,
            page_end=page.page_number,
            paragraph_ref=None,
        )
        session.add(section)
        sections.append(section)
    session.flush()
    return sections
