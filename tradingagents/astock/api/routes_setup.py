"""Setup & bootstrap API — idempotent initialisation, data ingestion, health probes.

All endpoints are idempotent: repeated calls must not corrupt data.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

from .envelope import error_response
from ._helpers import mock_data_enabled

bp = Blueprint("setup", __name__)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GET /api/v1/setup/status
# ---------------------------------------------------------------------------


@bp.route("/setup/status")
def setup_status() -> tuple[Response, int]:
    """Return the current bootstrap / setup status of the local data layer."""
    from .envelope import ok, fail
    store = current_app.config.get("STORE")
    if store is None:
        return fail("store not initialized", 500)

    tables: dict[str, Any] = {}
    try:
        table_stats = store.get_table_stats() if hasattr(store, "get_table_stats") else {}
        for name, info in table_stats.items():
            tables[name] = {
                "rows": info.get("row_count", 0),
                "schema_ok": bool(info.get("schema_ok")),
            }
    except Exception as exc:
        tables["_error"] = str(exc)

    data_state = "available" if any((t.get("rows", 0) or 0) > 0 for t in tables.values()) else "unavailable"
    return ok({
        "status": "ok" if any(tables.values()) else "not_initialized",
        "tables": tables,
        "has_real_data": any((t.get("rows", 0) or 0) > 0 for t in tables.values()),
        "mock_data_enabled": mock_data_enabled(),
    }, data_state=data_state)


# ---------------------------------------------------------------------------
# POST /api/v1/setup/bootstrap
# ---------------------------------------------------------------------------


@bp.route("/setup/bootstrap", methods=["POST"])
def setup_bootstrap() -> tuple[Response, int]:
    """Bootstrap canonical DuckDB with index + sample stock K-line data.

    Idempotent: calling twice will not duplicate rows.
    Requires real Provider data — never uses implicit mock.
    """
    if mock_data_enabled():
        return error_response("mock mode disabled under local-release", 403)

    store = current_app.config.get("STORE")
    if store is None:
        return error_response("store not initialized", 500)

    try:
        # Idempotency: check if already bootstrapped (at least some kline bars)
        existing_rows = 0
        try:
            existing_rows = store.kline_count()
        except Exception:
            pass

        if existing_rows > 0:
            return jsonify({
                "status": "already_bootstrapped",
                "existing_kline_bars": existing_rows,
                "note": "Bootstrap skipped — data already present.",
            }), 200

        # Bootstrap with deterministic samples from store-backed K-line data.
        store.bootstrap_sample_data()

        new_rows = 0
        try:
            new_rows = store.kline_count()
        except Exception:
            pass

        return jsonify({
            "status": "bootstrapped",
            "new_kline_bars": new_rows,
            "note": "Initialized with sample index + stock K-line data.",
        }), 200

    except TypeError:
        # bootstrap_sample_data not implemented on this store backend
        return error_response(
            "bootstrap_sample_data not available on this store backend", 501
        )
    except Exception as exc:
        logger.exception("Bootstrap failed")
        return error_response(f"bootstrap failed: {exc}", 500)


# ---------------------------------------------------------------------------
# GET /api/v1/setup/schema-info
# ---------------------------------------------------------------------------


@bp.route("/setup/schema-info")
def setup_schema_info() -> tuple[Response, int]:
    """Return the canonical schema definition for the DuckDB store."""
    store = current_app.config.get("STORE")
    if store is None:
        return error_response("store not initialized", 500)

    try:
        info = {}
        schemas = store.get_all_schemas()
        for tbl, cols in schemas.items():
            info[tbl] = {"columns": len(cols), "primary_key": []}
            for c in cols:
                if c.get("pk"):
                    info[tbl]["primary_key"].append(c.get("name", ""))

        return jsonify({"schema": info}), 200
    except Exception as exc:
        return error_response(f"schema introspection failed: {exc}", 500)
