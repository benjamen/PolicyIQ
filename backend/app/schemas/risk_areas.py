"""Pydantic schemas for the risk-area taxonomy and risk-event endpoints."""
from __future__ import annotations

from pydantic import BaseModel


class RiskAreaOut(BaseModel):
    code: str
    name: str
    parent_code: str | None = None
    description: str | None = None
    sort_order: int = 0


class RiskAreaTreeOut(BaseModel):
    """Top-level area with nested children."""
    code: str
    name: str
    description: str | None = None
    sort_order: int = 0
    children: list[RiskAreaOut] = []


class RiskAreaListResponse(BaseModel):
    areas: list[RiskAreaTreeOut]
    total: int


class CoverageByInsurer(BaseModel):
    insurer: str
    status: str  # covered | excluded | limited | sub_limited | silent


class RiskEventOut(BaseModel):
    id: str
    area_code: str
    name: str
    description: str | None = None
    coverage: list[CoverageByInsurer] = []


class RiskEventListResponse(BaseModel):
    events: list[RiskEventOut]
    total: int
