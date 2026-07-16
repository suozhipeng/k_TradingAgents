"""Controlled shutdown for AStock Flask application resources."""

from __future__ import annotations

import atexit
import logging
import signal
import threading
from typing import Any

from flask import Flask

logger = logging.getLogger(__name__)

_LOCK_EXTENSION_KEY = "astock_shutdown_lock"
_COMPLETE_CONFIG_KEY = "ASTOCK_SHUTDOWN_COMPLETE"
_ATEXIT_EXTENSION_KEY = "astock_atexit_registered"


def shutdown_app_resources(app: Flask) -> bool:
    """Stop application-owned workers and close the store exactly once.

    The scheduler is stopped before data jobs and the data store, preserving
    its ability to persist job state.  Cleanup is best-effort: one failed
    resource must not prevent subsequent resources from being released.
    """
    lock = app.extensions.setdefault(_LOCK_EXTENSION_KEY, threading.Lock())
    with lock:
        if app.config.get(_COMPLETE_CONFIG_KEY, False):
            return False
        app.config[_COMPLETE_CONFIG_KEY] = True

        resources: tuple[tuple[str, Any, str, dict[str, Any]], ...] = (
            ("scheduler", app.config.get("SCHEDULER"), "stop", {}),
            ("data job manager", app.config.get("DATA_JOB_MANAGER"), "shutdown", {"wait": False}),
            ("store", app.config.get("STORE"), "close", {}),
        )
        for name, resource, method_name, kwargs in resources:
            method = getattr(resource, method_name, None)
            if not callable(method):
                continue
            try:
                method(**kwargs)
            except Exception:
                logger.exception("Failed to close AStock %s", name)

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

    def _handle_signal(signum: int, _frame: Any) -> None:
        logger.info("Received %s; shutting down AStock resources", signal.Signals(signum).name)
        shutdown_app_resources(app)
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
