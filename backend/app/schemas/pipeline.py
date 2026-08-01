"""Pydantic schemas for pipeline run history."""
from __future__ import annotations

from pydantic import BaseModel


class PipelineRunOut(BaseModel):
    id: str
    run_type: str
    insurer_id: str | None = None
    insurer_name: str | None = None
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    documents_found: int = 0
    documents_new: int = 0
    extractions_ok: int = 0
    extractions_failed: int = 0
    error_summary: str | None = None
    triggered_by: str | None = None


class PipelineRunListResponse(BaseModel):
    runs: list[PipelineRunOut]
    total: int
