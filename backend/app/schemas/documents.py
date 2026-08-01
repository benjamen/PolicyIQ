from __future__ import annotations

from pydantic import BaseModel


class SectionTextOut(BaseModel):
    document_id: str
    page: int
    text: str
