"""Risk-area taxonomy and risk-event endpoints.

Serves the curated taxonomy from app/domain/risk_area_taxonomy.py as a
tree structure. Risk events will be populated by the coverage-matrix
pipeline stage once the scraping architecture migration is applied.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domain.risk_area_taxonomy import (
    RISK_AREA_TAXONOMY,
    get_children,
    get_top_level_areas,
)
from app.schemas.risk_areas import (
    RiskAreaListResponse,
    RiskAreaOut,
    RiskAreaTreeOut,
    RiskEventListResponse,
    RiskEventOut,
)

router = APIRouter(tags=["risk-areas"])


@router.get("/risk-areas", response_model=RiskAreaListResponse)
def list_risk_areas() -> RiskAreaListResponse:
    """Return the full risk-area taxonomy as a tree (top-level areas
    with nested children). This is a static curated catalog - see
    app/domain/risk_area_taxonomy.py."""
    top_level = get_top_level_areas()
    areas = [
        RiskAreaTreeOut(
            code=area.code,
            name=area.name,
            description=area.description,
            sort_order=area.sort_order,
            children=[
                RiskAreaOut(
                    code=child.code,
                    name=child.name,
                    parent_code=child.parent_code,
                    description=child.description,
                    sort_order=child.sort_order,
                )
                for child in get_children(area.code)
            ],
        )
        for area in top_level
    ]
    return RiskAreaListResponse(areas=areas, total=len(RISK_AREA_TAXONOMY))


@router.get("/risk-events", response_model=RiskEventListResponse)
def list_risk_events(
    area_code: str | None = Query(None, description="Filter by risk area code"),
    session: Session = Depends(get_db),
) -> RiskEventListResponse:
    """Return risk events, optionally filtered by area_code.

    Risk events are populated by the coverage-matrix pipeline stage.
    If the risk_event table doesn't exist yet (migration not applied),
    returns an empty list - fail-closed."""
    try:
        query = "SELECT id, area_code, name, description FROM risk_event"
        params: dict = {}
        if area_code:
            query += " WHERE area_code = :area_code"
            params["area_code"] = area_code
        query += " ORDER BY area_code, name"

        rows = session.execute(text(query), params).fetchall()
        events = [
            RiskEventOut(
                id=str(row[0]),
                area_code=row[1],
                name=row[2],
                description=row[3],
                coverage=[],  # Coverage matrix join deferred to Phase C
            )
            for row in rows
        ]
    except Exception:
        # Table doesn't exist yet (migration not applied) - fail closed
        events = []

    return RiskEventListResponse(events=events, total=len(events))
