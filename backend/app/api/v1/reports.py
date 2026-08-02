"""Head-to-head report endpoint - the paid $49/mo differentiator.

Auth-gated via require_credit (checks sufficiency; deduction happens
after successful generation so failed requests never cost a credit).
Builds on the existing grading engine (app/services/grading.py) to
produce a per-criterion winner comparison between two insurers, with
page-level citations.

This is PolicyIQ's answer to Quote Monster's Research Monster tier
(docs/13-COMPETITIVE-STRATEGY.md): evidence-based, multi-criterion,
citation-backed - and no personal information stored.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import deduct_credit, require_credit
from app.db.models import User
from app.db.repository import load_product_profiles
from app.db.session import get_db
from app.domain.models import CompareFilters
from app.schemas.auth import CriterionResult, HeadToHeadRequest, HeadToHeadResponse
from app.services.grading import compare as run_compare

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/head-to-head", response_model=HeadToHeadResponse)
def generate_head_to_head(
    body: HeadToHeadRequest,
    user: User = Depends(require_credit),
    session: Session = Depends(get_db),
) -> HeadToHeadResponse:
    """Generate a head-to-head comparison between two insurers.

    Costs 1 credit (deducted only on success) unless the user has an
    active subscription. Returns per-criterion winners with source page
    citations.
    """
    # Load all profiles for this product type
    profiles = load_product_profiles(session, product_type=body.product_type)

    # Filter to the two requested insurers
    insurer_a_profiles = [p for p in profiles if p.insurer_name.lower() == body.insurer_a.lower()]
    insurer_b_profiles = [p for p in profiles if p.insurer_name.lower() == body.insurer_b.lower()]

    if not insurer_a_profiles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data found for insurer '{body.insurer_a}' in product type '{body.product_type}'",
        )
    if not insurer_b_profiles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data found for insurer '{body.insurer_b}' in product type '{body.product_type}'",
        )

    # Run grading for each insurer's profiles
    filters = CompareFilters(
        age=40,
        smoker_status="non_smoker",
        occupation_category="professional",
        product_type=body.product_type,
    )
    reports_a = run_compare(insurer_a_profiles, filters)
    reports_b = run_compare(insurer_b_profiles, filters)

    # Build per-criterion comparison from the grade reports
    criteria: list[CriterionResult] = []

    # Extract scores by criterion from both sides
    scores_a: dict[str, float] = {}
    scores_b: dict[str, float] = {}
    sources_a: dict[str, int | None] = {}
    sources_b: dict[str, int | None] = {}

    for report in reports_a:
        for criterion in report.criteria:
            scores_a[criterion.name] = criterion.score
            if criterion.sources:
                sources_a[criterion.name] = criterion.sources[0].page

    for report in reports_b:
        for criterion in report.criteria:
            scores_b[criterion.name] = criterion.score
            if criterion.sources:
                sources_b[criterion.name] = criterion.sources[0].page

    # Merge all criterion names
    all_criteria = sorted(set(list(scores_a.keys()) + list(scores_b.keys())))

    for name in all_criteria:
        sa = scores_a.get(name)
        sb = scores_b.get(name)
        if sa is not None and sb is not None:
            winner = "tie" if sa == sb else ("a" if sa > sb else "b")
        elif sa is not None:
            winner = "a"
        elif sb is not None:
            winner = "b"
        else:
            winner = None

        criteria.append(
            CriterionResult(
                criterion=name,
                insurer_a_value=f"{sa:.1f}" if sa is not None else None,
                insurer_b_value=f"{sb:.1f}" if sb is not None else None,
                winner=winner,
                source_page_a=sources_a.get(name),
                source_page_b=sources_b.get(name),
            )
        )

    # Deduct credit ONLY after successful generation
    deduct_credit(user, session, reference=f"{body.insurer_a}_vs_{body.insurer_b}_{body.product_type}")

    # Refresh user to get updated credit balance
    session.refresh(user)

    return HeadToHeadResponse(
        insurer_a=body.insurer_a,
        insurer_b=body.insurer_b,
        product_type=body.product_type,
        criteria=criteria,
        credits_remaining=user.credit_balance,
        generated_at=datetime.now(timezone.utc),
    )
