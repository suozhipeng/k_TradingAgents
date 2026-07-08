"""Flask request/response hooks for the A-stock API.

Registers ``before_request`` and ``after_request`` handlers plus error
handlers.  These are applied inside ``create_app()`` after the store and
blueprints are configured.
"""

from __future__ import annotations

import asyncio
import hashlib
import json as _json
import logging
import time
import uuid
from typing import Any

from flask import Flask, g, jsonify, request

logger = logging.getLogger(__name__)


def register_hooks(app: Flask) -> None:
    """Attach before_request / after_request / errorhandler callbacks."""

    _register_before_request(app)
    _register_after_request(app)
    _register_error_handlers(app)


# ---------------------------------------------------------------------------
# before_request
# ---------------------------------------------------------------------------

def _register_before_request(app: Flask) -> None:
    @app.before_request
    def _inject_globals() -> None:
        g.store = app.config.get("STORE")
        g.pg_store = app.config.get("PG_STORE")
        g.backend_mgr = app.config.get("BACKEND_MGR")
        g.actor = "anonymous"
        g.role = "public"
        g.key_id = ""
        g.allowed_capabilities = ""

    @app.before_request
    def _require_auth_on_writes() -> tuple[Any, int] | None:
        backend = app.config.get("DB_BACKEND", "duckdb")
        if backend != "postgresql":
            return None
        if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
            return None
        if any(request.path.startswith(p) for p in ("/api/v1/health",)):
            return None

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing_auth",
                            "message": "Bearer token required for write operations"}), 401

        key_hash = hashlib.sha256(auth[7:].encode()).hexdigest()
        store = app.config.get("PG_STORE") or app.config.get("STORE")

        record = None
        if store and hasattr(store, "validate_api_key"):
            try:
                if asyncio.iscoroutinefunction(store.validate_api_key):
                    record = asyncio.run(store.validate_api_key(key_hash))
                else:
                    record = store.validate_api_key(key_hash)
            except Exception:
                record = None

        if record is None:
            return jsonify({"error": "invalid_key",
                            "message": "Invalid or expired API key"}), 401

        g.actor = record.get("key_id", "unknown")
        g.role = record.get("role", "readonly")
        g.key_id = record.get("key_id", "")
        g.allowed_capabilities = record.get("allowed_capabilities", "")
        return None


# ---------------------------------------------------------------------------
# after_request
# ---------------------------------------------------------------------------

def _register_after_request(app: Flask) -> None:
    @app.after_request
    def _audit_write_operations(response: Any) -> Any:
        """Non-blocking audit for all POST/PUT/DELETE/PATCH operations."""
        if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
            return response
        if request.path.startswith("/api/v1/health"):
            return response

        store = app.config.get("STORE")
        if store is None:
            return response

        try:
            actor = getattr(g, "actor", "anonymous")
            status_code = response.status_code if hasattr(response, "status_code") else 200

            detail = {
                "path": request.path,
                "method": request.method,
                "status": status_code,
                "query": dict(request.args),
            }
            try:
                body = request.get_json(silent=True)
                if body:
                    detail["body_keys"] = list(body.keys())[:20]
            except Exception:
                pass

            segs = request.path.strip("/").split("/")
            resource_type = segs[2] if len(segs) > 2 else "api"

            audit_data = {
                "event_id": uuid.uuid4().hex,
                "event_type": "api_write",
                "actor": actor,
                "resource_type": resource_type,
                "resource_id": segs[-1] if segs else "",
                "action": f"{request.method} {request.path}",
                "detail_json": _json.dumps(detail, ensure_ascii=False, default=str),
                "outcome": "success" if status_code < 400 else "error",
            }

            insert_fn = getattr(store, "store_audit_log", None)
            if insert_fn is not None:
                if asyncio.iscoroutinefunction(insert_fn):
                    try:
                        asyncio.run(insert_fn(**audit_data))
                    except RuntimeError:
                        pass
                else:
                    insert_fn(**audit_data)
        except Exception:
            pass
        return response


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(400)
    def bad_request(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Bad request", "status": 400}), 400

    @app.errorhandler(401)
    def unauthorized(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Unauthorized", "status": 401}), 401

    @app.errorhandler(403)
    def forbidden(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Forbidden", "status": 403}), 403

    @app.errorhandler(404)
    def not_found(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Not found", "status": 404}), 404

    @app.errorhandler(429)
    def rate_limited(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Rate limited", "status": 429}), 429

    @app.errorhandler(500)
    def server_error(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Internal server error", "status": 500}), 500
