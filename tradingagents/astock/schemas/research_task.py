"""Phase 33 — AI Research Center schemas.

- ``ResearchTaskStatus`` — task lifecycle enum
- ``ResearchTask`` — a single research execution
- ``ResearchAudit`` — audit trail for a research output
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ResearchTaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResearchTask(BaseModel):
    """An AI research task — represents a single research execution."""

    task_id: str = ""
    symbol: str = ""
    mode: str = "live_research"
    status: ResearchTaskStatus = ResearchTaskStatus.QUEUED
    prompt_version: str = ""
    provider: str = ""
    model: str = ""
    snapshot: dict = Field(default_factory=dict)
    result: Optional[dict] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class ResearchAudit(BaseModel):
    """Audit trail for a single research output."""

    audit_id: str = ""
    task_id: str = ""
    symbol: str = ""
    model: str = ""
    prompt_text: str = ""
    prompt_version: str = ""
    input_snapshot: dict = Field(default_factory=dict)
    output_summary: str = ""
    citations: list[str] = Field(default_factory=list)
    advisory: bool = True
    generated_at: str = ""


__all__ = [
    "ResearchTaskStatus",
    "ResearchTask",
    "ResearchAudit",
]
