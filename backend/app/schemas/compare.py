from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.domain.models import SmokerStatus


class DataSource(str, Enum):
    """See docs/11-DATA-CONNECTION.md. Both values are kept even though
    nothing emits SYNTHETIC_FIXTURE anymore (app/fixtures/sample_data.py was
    deleted once this pipeline existed) - the UI's status-pill component
    documents both, so the closed set stays complete."""

    SYNTHETIC_FIXTURE = "synthetic_fixture"
    EXTRACTED_VERIFIED = "extracted_verified"


class CompareRequest(BaseModel):
    age: int = Field(ge=0, le=120)
    smoker_status: SmokerStatus
    occupation_category: str
    product_type: str = "life_cover"


class SourceRefOut(BaseModel):
    insurer: str
    document: str
    page: int
    paragraph_ref: str
    confidence: float
    document_id: str | None = None


class CriterionOut(BaseModel):
    score: float | None
    weight: float
    raw_value: str
    source: SourceRefOut | None


class GeneralInsuranceFactOut(BaseModel):
    category: str
    name: str
    detail: str | None
    source: SourceRefOut | None


class GradeReportOut(BaseModel):
    insurer: str
    product_name: str
    policy_version_id: str
    eligible: bool
    ineligibility_reason: str | None
    overall_score: float | None
    data_completeness: float
    criteria: dict[str, CriterionOut]
    # Not a scored criterion - informational, same shape as general
    # insurance's exclusions (see ProductProfile.exclusions' docstring for
    # why no new storage mechanism was needed for these).
    exclusions: list[GeneralInsuranceFactOut] = []


class CompareResponse(BaseModel):
    filters: CompareRequest
    results: list[GradeReportOut]
    data_source: DataSource


class GeneralProductProfileOut(BaseModel):
    insurer: str
    product_name: str
    policy_version_id: str
    facts: list[GeneralInsuranceFactOut]


class CompareGeneralRequest(BaseModel):
    product_type: str = "home_contents"


class CompareGeneralResponse(BaseModel):
    filters: CompareGeneralRequest
    results: list[GeneralProductProfileOut]
    data_source: DataSource
