"""Phase 37 — Ops & Audit Center schemas.

- ``TaskType`` — enum of supported task types
- ``TaskStatus`` — strict lifecycle enum for TaskRun with valid transitions
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


class TaskStatus(str, Enum):
    """Strict lifecycle states for TaskRun with allowed transitions.

    Valid transitions::

        queued -> running -> success
                   running -> failed
                   running -> cancelled
        queued -> cancelled

    Disallowed transitions (e.g. success -> running) will raise ValueError.
    """

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def _transitions(cls) -> dict["TaskStatus", frozenset["TaskStatus"]]:
        return {
            cls.QUEUED: frozenset({cls.RUNNING, cls.CANCELLED}),
            cls.RUNNING: frozenset({cls.SUCCESS, cls.FAILED, cls.CANCELLED}),
            cls.SUCCESS: frozenset(),
            cls.FAILED: frozenset(),
            cls.CANCELLED: frozenset(),
        }

    def can_transition_to(self, target: "TaskStatus") -> bool:
        """Return True if ``target`` is a valid next state from ``self``."""
        return target in self._transitions().get(self, frozenset())

    @classmethod
    def validate_transition(cls, current: "TaskStatus", target: "TaskStatus") -> None:
        """Raise ValueError if the transition is invalid."""
        if not current.can_transition_to(target):
            raise ValueError(
                f"Invalid TaskStatus transition: {current.value!r} -> {target.value!r}. "
                f"Allowed from {current.value}: {sorted(t.value for t in cls._transitions()[current]) or 'none (terminal)'}"
            )


class TaskRun(BaseModel):
    """A generic task run — used for tracking all long-running operations."""

    task_id: str = ""
    task_type: TaskType = TaskType.DATA_REFRESH
    status: TaskStatus = TaskStatus.QUEUED
    progress: float = 0.0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[dict] = None
    result: Optional[dict] = None

    def update_status(self, target: TaskStatus) -> None:
        """Transition to *target* status with validation."""
        self.status.validate_transition(self.status, target)
        prev = self.status
        self.status = target
        now = __import__("datetime").datetime.utcnow().isoformat()
        if target == TaskStatus.RUNNING and prev != TaskStatus.RUNNING:
            self.started_at = now
        if target in (TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED):
            self.finished_at = now



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
    "TaskStatus",
    "TaskRun",
    "AuditEvent",
]
