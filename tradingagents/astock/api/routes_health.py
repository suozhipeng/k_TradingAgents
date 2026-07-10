"""Lightweight health-check endpoint — GET /api/v1/health."""

from __future__ import annotations

import logging
import time
from typing import Any

from flask import Blueprint, Response, current_app, jsonify

bp = Blueprint("health", __name__)
logger = logging.getLogger(__name__)


@bp.route("/health")
def health_check() -> tuple[Response, int]:
    """Return a minimal health status for load-balancer / probe use.

    Response::

        {
            "status": "ok",
            "backend": "duckdb|postgresql|clickhouse",
            "store_connected": true,
            "uptime_seconds": 12345,
            "version": "0.1.0"
        }
    """
    start = time.time()
    try:
        store = current_app.config.get("STORE")
        store_connected = store is not None
        # Try to infer backend from the store's inner store attribute
        inner = getattr(store, "inner_store", store)
        backend = getattr(inner, "backend_name", "duckdb") if store_connected else "unknown"
    except Exception as exc:
        logger.warning("health check store probe failed: %s", exc)
        store_connected = False
        backend = "unknown"

    uptime = round(time.time() - current_app.config.get("_START_TIME", time.time()), 1)

    status_code = 200 if store_connected else 503
    return jsonify({
        "status": "ok" if store_connected else "degraded",
        "backend": backend,
        "store_connected": store_connected,
        "mock_data_enabled": bool(current_app.config.get("ASTOCK_MOCK_DATA_ENABLED", False)),
        "uptime_seconds": uptime,
        "version": "0.3.0",
    }), status_code
