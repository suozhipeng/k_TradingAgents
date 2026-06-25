"""Phase 37 — Ops & Audit Center schemas.

- ``TaskType`` — enum of supported task types
- ``TaskRun`` — a generic task run
- ``AuditEvent`` — an auditable action event
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    DATA_REFRESH = "data_refresh"
    RESEARCH = "research"
    BACKTEST = "backtest"
    REPORT = "report"
    TRADE = "trade"


class TaskRun(BaseModel):
    """A generic task run — used for tracking all long-running operations."""

    task_id: str = ""
    task_type: TaskType = TaskType.DATA_REFRESH
    status: str = "queued"
    progress: float = 0.0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[dict] = None
    result: Optional[dict] = None


class AuditEvent(BaseModel):
    """An auditable action event — covers all user/system actions."""

    event_id: str = ""
    actor: str = ""
    action: str = ""
    input_snapshot: dict = Field(default_factory=dict)
    output_snapshot: dict = Field(default_factory=dict)
    model: Optional[str] = None
    confirmation_required: bool = False
    confirmed_by: Optional[str] = None
    created_at: str = ""


__all__ = [
    "TaskType",
    "TaskRun",
    "AuditEvent",
]
