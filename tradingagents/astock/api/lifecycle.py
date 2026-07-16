"""Controlled shutdown for AStock Flask application resources."""

from __future__ import annotations

import atexit
from concurrent.futures import ThreadPoolExecutor
import logging
import math
import signal
import threading
import time
from typing import Any

from flask import Flask

logger = logging.getLogger(__name__)

_LOCK_EXTENSION_KEY = "astock_shutdown_lock"
_COMPLETE_CONFIG_KEY = "ASTOCK_SHUTDOWN_COMPLETE"
_ATEXIT_EXTENSION_KEY = "astock_atexit_registered"
_STORE_DEFERRED_CONFIG_KEY = "ASTOCK_SHUTDOWN_STORE_DEFERRED"
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 5.0
_REQUEST_GATE_EXTENSION_KEY = "astock_request_gate"


class RequestGate:
    """Small per-app gate that drains in-flight Flask requests on shutdown."""

    def __init__(self) -> None:
        self._condition = threading.Condition(threading.Lock())
        self._active = 0
        self._closing = False

    def enter(self) -> bool:
        """Admit a request unless shutdown has already begun."""
        with self._condition:
            if self._closing:
                return False
            self._active += 1
            return True

    def leave(self) -> None:
        with self._condition:
            if self._active:
                self._active -= 1
            self._condition.notify_all()

    def begin_shutdown(self, deadline: float) -> bool:
        """Reject new requests and wait for admitted requests to finish."""
        with self._condition:
            self._closing = True
            while self._active:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(timeout=remaining)
            return True


def request_gate(app: Flask) -> RequestGate:
    """Return the app-owned request gate, creating it for embedded apps."""
    gate = app.extensions.get(_REQUEST_GATE_EXTENSION_KEY)
    if not isinstance(gate, RequestGate):
        gate = RequestGate()
        app.extensions[_REQUEST_GATE_EXTENSION_KEY] = gate
    return gate


def _shutdown_deadline(app: Flask) -> float:
    """Return one finite monotonic deadline for the complete close phase."""
    raw_timeout = app.config.get(
        "ASTOCK_SHUTDOWN_TIMEOUT_SECONDS", DEFAULT_SHUTDOWN_TIMEOUT_SECONDS
    )
    try:
        timeout = float(raw_timeout)
    except (TypeError, ValueError):
        timeout = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS
    if not math.isfinite(timeout):
        timeout = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS
    return time.monotonic() + max(0.0, timeout)


def _request_executor_shutdown(executor: Any) -> None:
    """Cancel queued work without waiting for an uncooperative worker."""
    shutdown = getattr(executor, "shutdown", None)
    if not callable(shutdown):
        return
    try:
        shutdown(wait=False, cancel_futures=True)
    except TypeError:
        # Keep compatibility with small test doubles and older executors.
        shutdown(wait=False)


def _live_executor_threads(executor: ThreadPoolExecutor) -> list[threading.Thread] | None:
    """Return live pool threads, or ``None`` when executor state is unknown."""
    threads = getattr(executor, "_threads", None)
    if threads is None:
        return None
    try:
        return [thread for thread in threads if thread.is_alive()]
    except (AttributeError, TypeError):
        return None


def _drain_background_work(
    executors: list[Any], futures: list[Any], deadline: float, label: str
) -> bool:
    """Bounded-drain known app workers and report whether store close is safe.

    Python cannot forcibly stop a thread that is blocked in a provider call.
    We therefore request cancellation, wait only until the shared deadline,
    and let the caller keep the store open if a worker is still active.
    """
    for executor in executors:
        _request_executor_shutdown(executor)

    real_executors = [
        executor
        for executor in executors
        if isinstance(executor, ThreadPoolExecutor)
    ]
    if len(real_executors) != len(executors):
        logger.warning("Cannot determine whether %s executor has live workers", label)
        return False
    while True:
        active = False
        for executor in real_executors:
            live_threads = _live_executor_threads(executor)
            if live_threads is None:
                logger.warning("Cannot determine whether %s executor has live workers", label)
                return False
            active = active or bool(live_threads)

        for future in futures:
            done = getattr(future, "done", None)
            if not callable(done):
                logger.warning("Cannot determine whether %s future has completed", label)
                return False
            active = active or not done()
        if not active:
            return True

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            logger.warning(
                "AStock %s shutdown deadline exceeded; keeping store open while workers drain",
                label,
            )
            return False
        time.sleep(min(0.01, remaining))


def _stop_scheduler(scheduler: Any, deadline: float) -> bool:
    """Stop a scheduler and drain its app-owned symbol worker pool."""
    if scheduler is None:
        return True
    drained = True
    stop = getattr(scheduler, "stop", None)
    try:
        if callable(stop):
            stop()
    finally:
        wait_for_idle = getattr(scheduler, "wait_for_idle", None)
        if callable(wait_for_idle):
            try:
                if wait_for_idle(timeout=max(0.0, deadline - time.monotonic())) is False:
                    drained = False
            except Exception:
                logger.exception("Failed to drain active scheduler cycles")
                drained = False
        # PaperTradeScheduler currently shuts this pool down with
        # ``wait=False`` so its HTTP-facing stop route remains responsive.
        # Application shutdown is the point at which it is safe to wait for
        # those workers before the shared store is closed.
        executors = getattr(scheduler, "_symbol_executors", None)
        if not isinstance(executors, (list, tuple)):
            executor = getattr(scheduler, "_symbol_executor", None)
            # Small scheduler test doubles often expose arbitrary attributes
            # through MagicMock. Only a real executor can be safely drained;
            # unknown legacy objects are not an ownership signal.
            executors = [executor] if isinstance(executor, ThreadPoolExecutor) else []
        if executors:
            drained = _drain_background_work(list(executors), [], deadline, "scheduler") and drained
    return drained


def _stop_data_jobs(manager: Any, deadline: float) -> bool:
    """Cancel known jobs and wait for their workers before store teardown."""
    if manager is None:
        return True
    drained = True
    list_jobs = getattr(manager, "list", None)
    cancel = getattr(manager, "cancel", None)
    shutdown = getattr(manager, "shutdown", None)
    try:
        if callable(list_jobs) and callable(cancel):
            try:
                jobs = list_jobs(limit=100_000)
            except TypeError:
                jobs = list_jobs()
            for job in jobs or ():
                if getattr(job, "status", None) in {"queued", "running"}:
                    cancel(getattr(job, "job_id", ""))
    finally:
        if callable(shutdown):
            shutdown(wait=False)
        executors = [
            getattr(manager, "_interactive_executor", None),
            getattr(manager, "_bulk_executor", None),
        ]
        executors = [executor for executor in executors if executor is not None]
        futures = []
        manager_futures = getattr(manager, "_futures", None)
        if isinstance(manager_futures, dict):
            futures = list(manager_futures.values())
        drained = _drain_background_work(executors, futures, deadline, "data job") and drained
    return drained


def _stop_notification_runtime(runtime: Any, deadline: float) -> bool:
    """Stop notifications and do not close the store behind a live consumer."""
    if runtime is None:
        return True

    # NotificationRuntime.stop_consumer() has a fixed three-second join.  Use
    # its event/thread directly when available so the application-wide
    # shutdown deadline remains authoritative.
    thread = getattr(runtime, "consumer_thread", None)
    if isinstance(thread, threading.Thread):
        stop_event = getattr(runtime, "consumer_stop", None)
        set_stop = getattr(stop_event, "set", None)
        if callable(set_stop):
            set_stop()
        thread.join(timeout=max(0.0, deadline - time.monotonic()))
        if thread.is_alive():
            logger.warning(
                "AStock notification consumer did not stop before shutdown deadline; keeping store open"
            )
            return False
        if getattr(runtime, "consumer_thread", None) is thread:
            runtime.consumer_thread = None
        return True

    stop = getattr(runtime, "stop_consumer", None)
    if callable(stop):
        stop()
    return True


def shutdown_app_resources(app: Flask) -> bool:
    """Stop application-owned workers and close the store exactly once.

    The scheduler is stopped before data jobs and the data store, preserving
    its ability to persist job state.  Cleanup is best-effort: one failed
    resource must not prevent subsequent resources from being released.  If a
    worker ignores cancellation past the configured deadline, the store is
    deliberately left open to prevent a use-after-close.
    """
    lock = app.extensions.setdefault(_LOCK_EXTENSION_KEY, threading.Lock())
    with lock:
        if app.config.get(_COMPLETE_CONFIG_KEY, False):
            return False
        deadline = _shutdown_deadline(app)
        resources_drained = request_gate(app).begin_shutdown(deadline)

        resources: tuple[tuple[str, Any, Any], ...] = (
            ("scheduler", app.config.get("SCHEDULER"), lambda resource: _stop_scheduler(resource, deadline)),
            # NotificationRuntime consumes the process EventBus on a daemon
            # thread and may hold the app store through its injected facade.
            # Stop it before the store is closed.
            ("notification consumer", app.config.get("NOTIFICATION_RUNTIME"), lambda resource: _stop_notification_runtime(resource, deadline)),
            ("data job manager", app.config.get("DATA_JOB_MANAGER"), lambda resource: _stop_data_jobs(resource, deadline)),
        )
        for name, resource, cleanup in resources:
            if resource is None:
                continue
            try:
                if cleanup(resource) is False:
                    resources_drained = False
            except Exception:
                logger.exception("Failed to close AStock %s", name)
                resources_drained = False

        store = app.config.get("STORE")
        store_closed = store is None
        if store is not None and resources_drained:
            try:
                store.close()
                store_closed = True
            except Exception:
                logger.exception("Failed to close AStock store")
        elif store is not None:
            app.config[_STORE_DEFERRED_CONFIG_KEY] = True
            logger.warning(
                "AStock store close deferred because application-owned workers remain active"
            )

        # A deferred close is retryable: a later lifecycle callback can drain
        # the worker/request that missed this deadline.  Once all ownership
        # obligations are satisfied, subsequent calls are idempotent.
        if resources_drained and store_closed:
            app.config[_COMPLETE_CONFIG_KEY] = True
            app.config.pop(_STORE_DEFERRED_CONFIG_KEY, None)

    logger.info("AStock application resources shut down")
    return True


def register_atexit_shutdown(app: Flask) -> None:
    """Register one process-exit cleanup callback for an application instance."""
    if app.extensions.get(_ATEXIT_EXTENSION_KEY, False):
        return
    atexit.register(shutdown_app_resources, app)
    app.extensions[_ATEXIT_EXTENSION_KEY] = True


def install_signal_handlers(app: Flask) -> None:
    """Install SIGTERM/SIGINT handlers for standalone AStock launchers."""

    if threading.current_thread() is not threading.main_thread():
        # ``signal.signal`` is only legal in the interpreter's main thread.
        # Flask test servers and embedding applications may construct the
        # standalone service from a worker thread; resource cleanup remains
        # available through the app lifecycle/atexit hooks in that case.
        logger.warning("Skipping AStock signal handlers outside the main thread")
        return

    def _handle_signal(signum: int, _frame: Any) -> None:
        logger.info("Received %s; shutting down AStock resources", signal.Signals(signum).name)
        shutdown_app_resources(app)
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
