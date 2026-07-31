from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.repository import load_insurer_coverage
from app.db.session import get_db
from app.schemas.insurers import InsurerCoverageOut, InsurerCoverageResponse, InsurerCoverageTypeOut

router = APIRouter(prefix="/insurers", tags=["insurers"])


@router.get("/coverage", response_model=InsurerCoverageResponse)
def get_insurer_coverage(session: Session = Depends(get_db)) -> InsurerCoverageResponse:
    """Real NZ insurers this project knows about (app/domain/
    nz_insurer_catalog.py, human-researched against RBNZ/ICNZ/FSC and each
    insurer's own site), cross-referenced against what's actually been
    ingested - never a proxy for "is this insurer real", only for "has
    this project got its documents yet"."""
    coverage = load_insurer_coverage(session)
    return InsurerCoverageResponse(
        results=[
            InsurerCoverageOut(
                name=c.name,
                website=c.website,
                notes=c.notes,
                types=[
                    InsurerCoverageTypeOut(product_type=t.product_type, offered=t.offered, covered=t.covered)
                    for t in c.types
                ],
            )
            for c in coverage
        ]
    )
