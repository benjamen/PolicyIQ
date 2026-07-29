"""Output shape both OCR backends (pymupdf_backend.py, docling_backend.py)
produce - page-anchored text blocks with coordinates, feeding Section
creation (app/pipeline/sections.py) per docs/05-AI-EXTRACTION-STRATEGY.md."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TextBlock:
    text: str
    bbox: tuple[float, float, float, float]
    paragraph_ref: str


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text_blocks: tuple[TextBlock, ...]
    native_text_coverage: float  # 0.0-1.0: fraction of this page that came from a native text layer

    @property
    def text(self) -> str:
        return "\n".join(block.text for block in self.text_blocks)


@dataclass(frozen=True)
class ParsedDocument:
    pages: tuple[ParsedPage, ...]
    backend_used: Literal["pymupdf", "docling"]

    def page(self, page_number: int) -> ParsedPage | None:
        return next((p for p in self.pages if p.page_number == page_number), None)
