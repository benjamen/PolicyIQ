from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.repository import get_section_text
from app.db.session import get_db
from app.schemas.documents import SectionTextOut

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}/pages/{page}", response_model=SectionTextOut)
def get_document_page_text(document_id: str, page: int, session: Session = Depends(get_db)) -> SectionTextOut:
    """Backs a citation's "view source" affordance - every SourceRef already
    carries (document_id, page), so the frontend needs nothing new to call
    this. 404 both when the section doesn't exist and when it exists but
    predates the text backfill (data/backfill_section_text.py) - fail
    closed rather than return an empty string that looks like a real,
    confirmed-empty page."""
    text = get_section_text(session, document_id=document_id, page=page)
    if text is None:
        raise HTTPException(status_code=404, detail="No source text available for this document page")
    return SectionTextOut(document_id=document_id, page=page, text=text)
