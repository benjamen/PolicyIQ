from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.repository import load_product_profiles
from app.db.session import get_db
from app.domain.models import CompareFilters
from app.schemas.compare import (
    CompareRequest,
    CompareResponse,
    CriterionOut,
    DataSource,
    GradeReportOut,
    SourceRefOut,
)
from app.services.grading import compare as run_compare

router = APIRouter(prefix="/compare", tags=["compare"])


@router.post("/life", response_model=CompareResponse)
def compare_life_insurance(request: CompareRequest, session: Session = Depends(get_db)) -> CompareResponse:
    """Grade life insurance products against each other for a given
    age/smoker-status/occupation-category/product-type combination.

    Document-derived only (see docs/09-LIFE-INSURANCE-SLICE.md): this
    returns policy structure and eligibility comparisons, never a premium
    quote, and never recommendation language - `response_mode` on this
    endpoint is implicitly "informational" per the compliance boundary in
    docs/01-ARCHITECTURE.md.

    Backed by real, citation-verified ProductProfiles from the repository
    layer (app/db/repository.py) - see docs/04/05-*-STRATEGY.md for the
    crawler/extraction pipeline that populates them. Fail-closed: if no
    verified data exists yet for these filters, `results` is an empty
    list, never a silent fallback to placeholder data.
    """
    filters = CompareFilters(
        age=request.age,
        smoker_status=request.smoker_status,
        occupation_category=request.occupation_category,
        product_type=request.product_type,
    )
    profiles = load_product_profiles(session, product_type=request.product_type)
    reports = run_compare(profiles, filters)

    results = [
        GradeReportOut(
            insurer=r.insurer,
            product_name=r.product_name,
            policy_version_id=r.policy_version_id,
            eligible=r.eligible,
            ineligibility_reason=r.ineligibility_reason,
            overall_score=r.overall_score,
            data_completeness=r.data_completeness,
            criteria={
                name: CriterionOut(
                    score=c.score,
                    weight=c.weight,
                    raw_value=c.raw_value,
                    source=SourceRefOut(**c.source.__dict__) if c.source else None,
                )
                for name, c in r.criteria.items()
            },
        )
        for r in reports
    ]

    return CompareResponse(
        filters=request,
        results=results,
        data_source=DataSource.EXTRACTED_VERIFIED,
    )
