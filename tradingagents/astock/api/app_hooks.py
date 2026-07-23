"""App-level hooks: schema init, global error handling, and V1.7 envelope wrapping."""

from __future__ import annotations

import logging
import threading

from flask import Flask, jsonify, Response as FlaskResponse

from .envelope import fail, ok

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


# ── V1.7 global after_request: wrap bare JSON in envelope ───────────────────


def _wrap_envelope(response: FlaskResponse) -> FlaskResponse:
    """Wrap bare JSON responses in the V1.7 {ok, data, meta, error} envelope.

    Routes that already return ok()/fail() pass through unchanged.
    """
    if response.content_type != "application/json":
        return response
    # Don't double-wrap
    if hasattr(response, "_v17_enveloped"):
        return response
    try:
        payload = response.get_json()
    except Exception:
        return response
    if not isinstance(payload, dict) or "ok" in payload:
        return response

    # Wrap as success response
    wrapped, _ = ok(payload)
    body = jsonify(wrapped)
    body._v17_enveloped = True
    return body


def register_after_request(app: Flask) -> None:
    app.after_request(_wrap_envelope)


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
                        "meta": {},
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
    """Install app lifecycle hooks, error handlers, and V1.7 envelope wrapping."""
    register_error_handlers(app)
    register_after_request(app)
