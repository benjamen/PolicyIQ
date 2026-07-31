from __future__ import annotations

from pydantic import BaseModel


class InsurerCoverageTypeOut(BaseModel):
    product_type: str
    offered: bool
    covered: bool


class InsurerCoverageOut(BaseModel):
    name: str
    website: str
    types: list[InsurerCoverageTypeOut]
    notes: str | None = None


class InsurerCoverageResponse(BaseModel):
    results: list[InsurerCoverageOut]
