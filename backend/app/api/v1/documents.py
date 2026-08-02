from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, Insurer, Policy, PolicyVersion, Product
from app.db.repository import get_section_text
from app.db.session import get_db
from app.schemas.documents import DocumentRecordOut, SectionTextOut

router = APIRouter(prefix="/documents", tags=["documents"])


def _title_from_storage_key(storage_key: str) -> str:
    """Derive a human-readable title from a content-addressed storage_key.

    storage_key scheme: <insurer>/<product>/<type>/<12-hex-hash>-<slug>.pdf
    We take the filename, strip the extension and the leading hash prefix,
    then turn dash/underscore separators into spaces."""
    filename = storage_key.rsplit("/", 1)[-1]
    name = filename.rsplit(".", 1)[0]
    parts = name.split("-", 1)
    if len(parts) == 2 and len(parts[0]) == 12 and all(ch in "0123456789abcdef" for ch in parts[0]):
        name = parts[1]
    return name.replace("-", " ").replace("_", " ").strip()


@router.get("", response_model=list[DocumentRecordOut])
def list_documents(session: Session = Depends(get_db)) -> list[DocumentRecordOut]:
    """List every downloaded document with its insurer/product context for
    the Documents & Brochures view. Ordered newest-first. Fail-closed: an
    empty DB simply returns an empty list."""
    rows = session.execute(
        select(Document, Insurer.name, Product.product_type)
        .join(PolicyVersion, Document.policy_version_id == PolicyVersion.id)
        .join(Policy, PolicyVersion.policy_id == Policy.id)
        .join(Product, Policy.product_id == Product.id)
        .join(Insurer, Product.insurer_id == Insurer.id)
        .order_by(Document.downloaded_at.desc())
    ).all()

    return [
        DocumentRecordOut(
            id=str(doc.id),
            insurer=insurer_name,
            product_type=product_type,
            title=_title_from_storage_key(doc.storage_key),
            source_url=doc.source_url,
            sha256=doc.sha256_hash,
            downloaded_at=doc.downloaded_at.isoformat(),
            page_count=doc.page_count,
            is_brochure=doc.doc_type == "brochure",
        )
        for doc, insurer_name, product_type in rows
    ]


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
