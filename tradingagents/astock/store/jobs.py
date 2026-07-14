"""In-process data job tracking for AStock database operations.

Upgraded with retry support, priority ordering, and optional event persistence
via AStockStore's ingestion_job_events table.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class DataJob:
    """Mutable status record for a background data operation.

    Parameters
    ----------
    job_id : str
        Unique job identifier.
    kind : str
        Job type name (e.g. ``'kline_import'``, ``'quality_audit'``).
    status : str
        One of ``queued``, ``running``, ``succeeded``, ``failed``, ``cancelled``.
    total : int
        Expected total work units.
    completed : int
        Completed work units.
    message : str
        Human-readable status message.
    result : dict
        Structured result payload.
    error : str or None
        Error message if failed.
    priority : int
        Higher = scheduled first (default 0).
    max_retries : int
        Max retries on transient failure (default 0).
    retry_count : int
        Current retry attempt number.
    created_at : float
        Unix timestamp of creation.
    updated_at : float
        Unix timestamp of last change.
    """

    job_id: str
    kind: str
    status: str = "queued"
    total: int = 0
    completed: int = 0
    message: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    priority: int = 0
    max_retries: int = 0
    retry_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def progress(self) -> float:
        if self.total <= 0:
            return 0.0
        return round(min(self.completed / self.total, 1.0), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "status": self.status,
            "total": self.total,
            "completed": self.completed,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "priority": self.priority,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class DataJobManager:
    """Thread-backed job manager with priority scheduling and retry support.

    Parameters
    ----------
    max_workers : int
        Max concurrent worker threads (default 2).
    store : optional
        An ``AStockStore`` instance that will receive persistent job events.
        When set, each job status transition writes an event to
        ``data_ingestion_job_events``.
    """

    def __init__(
        self,
        max_workers: int = 4,
        max_queued: int = 100,
        store: Any = None,  # AStockStore (avoid circular import at class level)
    ) -> None:
        workers = max(1, int(max_workers))
        # Keep one lane available for interactive refreshes.  A long-running
        # backfill must not occupy every worker and make the UI wait behind it.
        self._interactive_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="astock-interactive")
        self._bulk_executor = ThreadPoolExecutor(max_workers=max(1, workers - 1), thread_name_prefix="astock-bulk")
        self._jobs: dict[str, DataJob] = {}
        self._lock = threading.Lock()
        self._store = store
        # ``ThreadPoolExecutor`` itself has an unbounded work queue.  Reserve
        # capacity for currently running workers plus a bounded waiting room.
        self._admission = threading.BoundedSemaphore(workers + max(0, int(max_queued)))

    # ── submit ─────────────────────────────────────────────────────────

    def submit(
        self,
        kind: str,
        fn: Callable[[Callable[..., None]], dict[str, Any]],
        *,
        total: int = 0,
        message: str = "",
        priority: int = 0,
        max_retries: int = 0,
    ) -> DataJob:
        """Create and queue a new job.

        Parameters
        ----------
        kind : str
            Job kind / type.
        fn : callable
            The worker function. Receives a ``progress(**updates)`` callable
            as its only argument.
        total : int
            Expected total work units (for progress tracking).
        message : str
            Initial status message.
        priority : int
            Higher = scheduled first (default 0).
        max_retries : int
            Auto-retry on transient failure (default 0).

        Returns
        -------
        DataJob
            The job record (reference; status updates are mutable).
        """
        if not self._admission.acquire(blocking=False):
            raise RuntimeError("data job queue is full; retry after active jobs finish")
        job = DataJob(
            job_id=uuid.uuid4().hex,
            kind=kind,
            total=max(int(total or 0), 0),
            message=message,
            priority=priority,
            max_retries=max_retries,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        self._persist_event(job, "queued")
        executor = self._interactive_executor if priority > 0 else self._bulk_executor
        try:
            executor.submit(self._run_limited, job.job_id, fn)
        except Exception:
            self._admission.release()
            raise
        return job

    def shutdown(self, *, wait: bool = False) -> None:
        """Release both execution lanes during controlled application shutdown."""
        self._interactive_executor.shutdown(wait=wait, cancel_futures=True)
        self._bulk_executor.shutdown(wait=wait, cancel_futures=True)

    # ── accessors ──────────────────────────────────────────────────────

    def get(self, job_id: str) -> DataJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(
        self,
        *,
        kind: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[DataJob]:
        """List jobs with optional filtering, newest-first."""
        with self._lock:
            items = list(self._jobs.values())
        if kind:
            items = [j for j in items if j.kind == kind]
        if status:
            items = [j for j in items if j.status == status]
        items.sort(key=lambda j: (j.priority, j.created_at), reverse=True)
        return items[:limit]

    def cancel(self, job_id: str) -> bool:
        """Cancel a queued/running job."""
        job = self.get(job_id)
        if job is None:
            return False
        with self._lock:
            if job.status in ("queued", "running"):
                job.status = "cancelled"
                job.updated_at = time.time()
        self._persist_event(job, "cancelled")
        return True

    def list_kinds(self) -> list[str]:
        """Return distinct job kind names."""
        with self._lock:
            kinds = sorted({j.kind for j in self._jobs.values()})
        return kinds

    # ── internal ───────────────────────────────────────────────────────

    def _run_limited(
        self, job_id: str, fn: Callable[[Callable[..., None]], dict[str, Any]]
    ) -> None:
        try:
            self._run(job_id, fn)
        finally:
            self._admission.release()

    def _update(self, job_id: str, **updates: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for key, value in updates.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            job.updated_at = time.time()

    def _persist_event(self, job: DataJob, event_status: str) -> None:
        """Write a job status transition event to the store if configured."""
        if self._store is None:
            return
        try:
            self._store.store_ingestion_job_event({
                "job_id": job.job_id,
                "status": event_status,
                "processed_rows": job.completed,
                "message": job.message,
                "error_message": job.error,
                "metadata_json": (
                    f'{{"kind":"{job.kind}","priority":{job.priority},'
                    f'"retry_count":{job.retry_count}}}'
                ),
            })
        except Exception as exc:
            logger.warning("Failed to persist job event for %s: %s", job.job_id, exc)

    def _run(
        self, job_id: str, fn: Callable[[Callable[..., None]], dict[str, Any]]
    ) -> None:
        self._update(job_id, status="running", retry_count=0)

        def progress(**updates: Any) -> None:
            self._update(job_id, **updates)

        job = self.get(job_id)
        max_retries = job.max_retries if job else 0
        retry_delays = [5, 15, 30, 60, 120]

        for attempt in range(max_retries + 1):
            if attempt > 0:
                delay = retry_delays[min(attempt - 1, len(retry_delays) - 1)]
                logger.info(
                    "Job %s retry %d/%d in %ds",
                    job_id, attempt, max_retries, delay,
                )
                time.sleep(delay)
                self._update(job_id, status="running", retry_count=attempt)
                current = self.get(job_id)
                if current:
                    self._persist_event(current, "retrying")

            try:
                result = fn(progress)
                completed_job = self.get(job_id)
                self._update(
                    job_id,
                    status="succeeded",
                    completed=completed_job.total if completed_job else 0,
                    result=result or {},
                    message="completed",
                    error=None,
                )
                succeeded_job = self.get(job_id)
                if succeeded_job:
                    self._persist_event(succeeded_job, "succeeded")
                return
            except Exception as exc:
                if attempt < max_retries:
                    logger.warning(
                        "Job %s attempt %d failed, retrying: %s",
                        job_id, attempt + 1, exc,
                    )
                    continue
                failed_job = self.get(job_id)
                if failed_job:
                    self._update(
                        failed_job.job_id,
                        status="failed",
                        error=str(exc),
                        message=f"failed after {max_retries + 1} attempt(s)",
                    )
                    self._persist_event(failed_job, "failed")
                logger.error("Job %s failed after %d attempts: %s", job_id, max_retries + 1, exc)
                return
