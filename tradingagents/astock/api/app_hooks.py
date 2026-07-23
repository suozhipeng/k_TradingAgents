"""App-level hooks: ensure schema is initialised at startup and global error handling."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from flask import Flask, jsonify

from .envelope import fail

logger = logging.getLogger(__name__)

_SCHEMA_INIT_LOCK = threading.Lock()


def ensure_schema_at_startup(app, store) -> None:
    """Initialise DuckDB schema idempotently. Runs once per process."""
    if not store:
        logger.warning("ensure_schema_at_startup called with no store")
        return
    try:
        store.conn.execute("PRAGMA tables('kline_bars')").fetchone()
    except Exception:
        with _SCHEMA_INIT_LOCK:
            try:
                store.migrate("kline_bars", "security_master", "trading_calendar")
                logger.info("DuckDB schema initialised at startup")
            except Exception as exc:
                logger.error("Failed to initialise schema: %s", exc)


def on_app_start(app):
    """Register on-start hooks: ensure schema exists."""
    store = getattr(app, "astock_store", None) or app.config.get("STORE")
    if store:
        ensure_schema_at_startup(app, store)


# ── V1.7 global error handlers ──────────────────────────────────────────────


def _handle_error(exc, status: int = 500):
    """Convert any exception into a V1.7 unified error envelope."""
    if status >= 500:
        logger.error("Unhandled %s: %s", type(exc).__name__, exc)
    body, _ = fail(str(exc) if status < 500 else "internal_server_error",
                    status=status)
    return jsonify(body), status


def register_error_handlers(app: Flask) -> None:
    """Install V1.7 unified error handlers for common HTTP errors."""

    @app.errorhandler(400)
    def bad_request(exc):
        return _handle_error(exc, 400)

    @app.errorhandler(403)
    def forbidden(exc):
        return _handle_error(exc, 403)

    @app.errorhandler(404)
    def not_found(exc):
        return jsonify({"ok": False, "data": None,
                        "meta": {},  # bare minimum
                        "error": {"code": "NOT_FOUND",
                                  "message": "resource not found",
                                  "details": {}, "retryable": False}}), 404

    @app.errorhandler(405)
    def method_not_allowed(exc):
        return _handle_error(exc, 405)

    @app.errorhandler(422)
    def unprocessable(exc):
        return _handle_error(exc, 422)

    @app.errorhandler(429)
    def rate_limited(exc):
        return _handle_error(exc, 429)

    @app.errorhandler(500)
    def internal_error(exc):
        return _handle_error(exc, 500)


def register_hooks(app):
    """Install app lifecycle hooks and V1.7 error handlers."""
    register_error_handlers(app)
