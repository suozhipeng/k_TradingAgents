"""
API key authentication and capability guards for AStock Pro.

Supports Bearer token -> api_keys lookup (PGStore -> DuckDB fallback).
Rate limiting is enforced once by the application request hook; this module
only resolves keys and applies route-level role/capability policies.
"""

import hashlib
import logging
from functools import wraps
from typing import Callable, Optional

from flask import request, g, jsonify, current_app

from .key_resolver import resolve_api_key

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def require_auth(roles: Optional[list[str]] = None):
    """Decorator: require a valid API key with optional role check.

    Extracts ``Authorization: Bearer <key>`` from the request header,
    SHA-256 hashes it, and looks it up in the store (PGStore -> DuckDB).

    On success populates::

        g.actor      — key_id
        g.role       — role string (e.g. "admin", "readonly")
        g.key_id     — same as g.actor
        g.allowed_capabilities — capability string from the key record

    Usage::

        @require_auth(roles=["admin"])
        def admin_route():
            ...

        @require_auth()
        def any_authenticated_route():
            ...
    """
    def decorator(f: Callable):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({
                    "error": "missing_auth",
                    "message": "Authorization: Bearer <key> required"
                }), 401

            api_key = auth_header[7:]
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            # Try PGStore first, fall back to DuckDB
            store = getattr(g, "pg_store", None) or getattr(g, "store", None)
            if store is None:
                store = current_app.config.get("STORE")
            if store is None:
                return jsonify({
                    "error": "no_store",
                    "message": "Database not connected"
                }), 500

            record = resolve_api_key(store, key_hash)

            if record is None:
                return jsonify({
                    "error": "invalid_key",
                    "message": "Invalid or expired API key"
                }), 401

            # Role check
            key_role = record.get("role", "readonly")
            if roles and key_role not in roles:
                return jsonify({
                    "error": "forbidden",
                    "message": f"Requires one of: {roles}"
                }), 403

            # Populate g
            g.actor = record.get("key_id", "unknown")
            g.role = key_role
            g.key_id = record.get("key_id", "")
            g.allowed_capabilities = record.get("allowed_capabilities", "")

            return f(*args, **kwargs)
        return decorated
    return decorator


def require_capability(*capabilities: str, roles: Optional[list[str]] = None):
    """Require an authenticated role plus one of the named capabilities.

    The application-wide write hook has already resolved the bearer key.  In
    test mode (``ASTOCK_REQUIRE_AUTH=false``) this deliberately remains a
    no-op so isolated route tests need not manufacture credentials.
    """
    def decorator(f: Callable):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_app.config.get("ASTOCK_REQUIRE_AUTH", True):
                return f(*args, **kwargs)
            role = getattr(g, "role", "public")
            if roles and role not in roles:
                return jsonify({"error": "forbidden", "message": "Insufficient role"}), 403
            granted = {
                item.strip() for item in getattr(g, "allowed_capabilities", "").split(",")
                if item.strip()
            }
            if "*" not in granted and not any(item in granted for item in capabilities):
                return jsonify({"error": "forbidden", "message": "Required capability missing"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def optional_auth(f: Callable):
    """Decorator: populate ``g.actor`` / ``g.role`` if a Bearer token is
    present and valid, but never block the request.

    Sets safe defaults::

        g.actor = "anonymous"
        g.role  = "public"
        g.key_id = ""

    If a valid key is found, those fields are replaced with the key record
    values.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        g.actor = "anonymous"
        g.role = "public"
        g.key_id = ""
        g.allowed_capabilities = ""

        # Try to extract identity from header but don't fail
        try:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                key_hash = hashlib.sha256(auth_header[7:].encode()).hexdigest()
                store = getattr(g, "pg_store", None) or getattr(g, "store", None)
                if store is None:
                    store = current_app.config.get("STORE")
                record = resolve_api_key(store, key_hash)
                if record:
                    g.actor = record["key_id"]
                    g.role = record.get("role", "public")
                    g.key_id = record["key_id"]
                    g.allowed_capabilities = record.get("allowed_capabilities", "")
        except Exception as exc:
            logger.warning("Capability check failed: %s", exc)
        return f(*args, **kwargs)
    return decorated
