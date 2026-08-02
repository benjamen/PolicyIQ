from __future__ import annotations

from pydantic import BaseModel


class SectionTextOut(BaseModel):
    document_id: str
    page: int
    text: str


class DocumentRecordOut(BaseModel):
    """One downloaded document with its insurer/product context, shaped for
    the Documents & Brochures table. `title` is derived from the storage_key
    filename (hash prefix stripped); `is_brochure` distinguishes marketing
    brochures from policy wordings."""

    id: str
    insurer: str
    product_type: str
    title: str
    source_url: str
    sha256: str
    downloaded_at: str
    page_count: int | None
    is_brochure: bool
