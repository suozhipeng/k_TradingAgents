"""Admin API routes — backend switch, config, runtime status.

Requires admin-level API key in production mode.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request

from .auth import require_auth
from .envelope import error_response, success_response
from ._helpers import _as_bool

bp = Blueprint("admin", __name__)
logger = logging.getLogger(__name__)


def _require_admin(*required_capabilities: str) -> bool:
    """Check if the current request has admin role and required capabilities.

    Requires ``ASTOCK_ADMIN_TOKEN`` env var (or ``?token=`` query param).
    DuckDB mode no longer bypasses auth.

    Returns True if allowed, False if blocked (caller should return 403).
    """
    token = request.args.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    expected = os.environ.get("ASTOCK_ADMIN_TOKEN", "")
    if expected and token != expected:
        return False

    role = getattr(g, "role", "public")
    if role != "admin":
        return False

    if required_capabilities:
        caps = getattr(g, "allowed_capabilities", "")
        caps_set = {c.strip() for c in caps.split(",") if c.strip()}
        for cap in required_capabilities:
            if cap not in caps_set and "*" not in caps_set:
                return False

    return True


@bp.route("/admin/backend", methods=["GET"])
@require_auth(roles=["admin"])
def get_backend() -> tuple[Any, int]:
    """Return current backend status."""
    mgr = current_app.config.get("BACKEND_MGR")
    if mgr is None:
        return error_response("BackendManager not configured", 500)
    return success_response(mgr.status())


@bp.route("/admin/backend", methods=["POST"])
def switch_backend() -> tuple[Any, int]:
    """Switch database backend at runtime.

    Body::

        {"backend": "duckdb"}       # → DuckDB local store
        {"backend": "postgresql"}   # → PostgreSQL/TimescaleDB

    PostgreSQL switch requires PG_HOST/PG_PORT/PG_DB/PG_USER/PG_PASSWORD
    to be set in ``~/.tradingagents/backend.json`` or environment variables.

    Returns::

        {"backend": "postgresql", "connected": true,
         "message": "Switched to PostgreSQL/TimescaleDB (production)."}
    """
    data = request.get_json(silent=True) or {}
    target = data.get("backend", "").strip().lower()
    if not target:
        return error_response("Missing 'backend' field. Use 'duckdb' or 'postgresql'.", 400)

    if not _require_admin("backend:switch"):
        return error_response("Admin role + backend:switch capability required", 403)

    mgr = current_app.config.get("BACKEND_MGR")
    if mgr is None:
        return error_response("BackendManager not configured", 500)

    result = mgr.switch_to(target)

    # Update Flask config after switch, wrapping with ValidatedStore
    current_app.config["DB_BACKEND"] = result["backend"]
    if result["backend"] == "postgresql":
        raw_store = mgr.get_pg_store()
        current_app.config["PG_STORE"] = raw_store
    else:
        raw_store = mgr.get_duck_store()
        current_app.config["PG_STORE"] = None

    # Wrap with quality gate if not already wrapped
    from tradingagents.astock.quality import ValidatedStore, QualityExecutor
    if not isinstance(raw_store, ValidatedStore):
        executor = QualityExecutor(raw_store, dry_run=False)
        current_app.config["STORE"] = ValidatedStore(raw_store, executor)
    else:
        current_app.config["STORE"] = raw_store

    status_code = 200 if result.get("connected") else 502
    return jsonify(result), status_code


@bp.route("/admin/backend/config", methods=["GET"])
@require_auth(roles=["admin"])
def get_backend_config() -> tuple[Any, int]:
    """Return current backend configuration (passwords masked)."""
    mgr = current_app.config.get("BACKEND_MGR")
    if mgr is None:
        return error_response("BackendManager not configured", 500)
    cfg = mgr.config.to_dict()
    # Mask password
    if cfg.get("pg_password"):
        cfg["pg_password"] = "***"
    return success_response(cfg)


@bp.route("/admin/mock-data", methods=["GET"])
@require_auth(roles=["admin"])
def get_mock_data_setting() -> tuple[Any, int]:
    """Return the process-wide mock-data switch."""
    return success_response({"enabled": _as_bool(current_app.config.get("ASTOCK_MOCK_DATA_ENABLED"), False)})


@bp.route("/admin/mock-data", methods=["PUT"])
@require_auth(roles=["admin"])
def set_mock_data_setting() -> tuple[Any, int]:
    """Enable or disable process-wide mock data and persist the setting."""
    body = request.get_json(silent=True) or {}
    enabled = _as_bool(body.get("enabled"), False)
    current_app.config["ASTOCK_MOCK_DATA_ENABLED"] = enabled
    manager = current_app.config.get("BACKEND_MGR")
    if manager is not None:
        manager.config.mock_data_enabled = enabled
        manager.config.save()
    logger.warning("Global mock-data mode changed: enabled=%s actor=%s", enabled, getattr(g, "actor", "unknown"))
    return success_response({"enabled": enabled, "persistent": manager is not None})


@bp.route("/admin/health/sync-ch", methods=["POST"])
def trigger_ch_sync() -> tuple[Any, int]:
    """Trigger a ClickHouse sync for the currently active backend.

    Body::

        {"table": "kline_bars", "since": "2026-01-01"}

    The sync source (duckdb or postgresql) is auto-detected from
    the current ``BackendManager`` configuration.
    """
    data = request.get_json(silent=True) or {}
    table = data.get("table")
    since = data.get("since")

    if not _require_admin("clickhouse:sync"):
        return error_response("Admin role + clickhouse:sync capability required", 403)

    mgr = current_app.config.get("BACKEND_MGR")
    if mgr is None:
        return error_response("BackendManager not configured", 500)

    backend = mgr.current_backend
    store = mgr.get_store()

    if store is None:
        return error_response(f"No store available for backend '{backend}'", 502)

    # Import sync logic — call the CLI script as subprocess
    import subprocess, sys
    cmd = [
        sys.executable,
        "scripts/astock_sync_ch.py",
        "--source", backend,
    ]
    if table:
        cmd += ["--table", table]
    if since:
        cmd += ["--since", since]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        return success_response({
            "backend": backend,
            "table": table or "all",
            "returncode": result.returncode,
            "stdout": result.stdout[:2000] if result.stdout else "",
            "stderr": result.stderr[:500] if result.stderr else "",
        }, status=200 if result.returncode == 0 else 502)
    except subprocess.TimeoutExpired:
        return error_response("Sync timed out after 600s", 504)
