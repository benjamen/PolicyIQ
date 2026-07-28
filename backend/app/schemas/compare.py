from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models import SmokerStatus


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


class CriterionOut(BaseModel):
    score: float | None
    weight: float
    raw_value: str
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


class CompareResponse(BaseModel):
    filters: CompareRequest
    results: list[GradeReportOut]
    data_source: str
