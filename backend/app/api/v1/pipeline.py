"""Pipeline run history endpoint.

Serves the pipeline_run table created by migration a1b2c3d4e5f6.
If the table doesn't exist yet, returns an empty list (fail-closed).
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.pipeline import PipelineRunListResponse, PipelineRunOut

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/runs", response_model=PipelineRunListResponse)
def list_pipeline_runs(
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db),
) -> PipelineRunListResponse:
    """Return recent pipeline runs, newest first.

    The stats_json column stores a JSON blob with documents_found,
    documents_new, extractions_ok, extractions_failed - we parse it
    here to flatten into the response schema."""
    try:
        rows = session.execute(
            text(
                "SELECT pr.id, pr.run_type, pr.insurer_id, i.name, pr.status, "
                "pr.started_at, pr.completed_at, pr.stats_json, pr.error_summary, pr.triggered_by "
                "FROM pipeline_run pr "
                "LEFT JOIN insurer i ON pr.insurer_id = i.id "
                "ORDER BY pr.started_at DESC "
                "LIMIT :limit"
            ),
            {"limit": limit},
        ).fetchall()

        runs = []
        for row in rows:
            stats = {}
            if row[7]:
                try:
                    stats = json.loads(row[7])
                except (json.JSONDecodeError, TypeError):
                    pass

            def _iso(val):
                """SQLite returns datetimes as strings via text() - handle both."""
                if val is None:
                    return None
                if hasattr(val, "isoformat"):
                    return val.isoformat()
                return str(val)

            runs.append(
                PipelineRunOut(
                    id=str(row[0]),
                    run_type=row[1],
                    insurer_id=str(row[2]) if row[2] else None,
                    insurer_name=row[3],
                    status=row[4],
                    started_at=_iso(row[5]),
                    completed_at=_iso(row[6]),
                    documents_found=stats.get("documents_found", 0),
                    documents_new=stats.get("documents_new", 0),
                    extractions_ok=stats.get("extractions_ok", 0),
                    extractions_failed=stats.get("extractions_failed", 0),
                    error_summary=row[8],
                    triggered_by=row[9],
                )
            )
    except Exception:
        # Table doesn't exist yet (migration not applied) - fail closed
        runs = []

    return PipelineRunListResponse(runs=runs, total=len(runs))
