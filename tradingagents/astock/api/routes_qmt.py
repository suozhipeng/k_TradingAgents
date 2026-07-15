"""QMT status API routes — mock/read-only bridge health and account snapshots.

**Capability level: ``managed`` (mock/read-only)**

All QMT endpoints return mock data.  Real QMT order/query is deferred to P3
and is not part of the current product scope.  Route-level query parameters
must not enable a real broker connection.

Every response includes a ``status`` dict with:

- ``source``: ``"mock"``
- ``mock``: ``True`` because all current QMT data is synthetic
- ``read_only``: ``True`` (all current routes are read-only)
- ``live_ready``: ``False`` (not connected to a real broker)
- ``capability``: ``"managed"`` with ``"note": "mock/read-only — real QMT order/query is P3 deferred"``

Uses lazy imports for ``tradingagents.astock.execution.qmt_bridge``.
"""

from __future__ import annotations

import logging

from typing import Any

from flask import Blueprint, Response, jsonify
from .envelope import error_response
logger = logging.getLogger(__name__)

bp = Blueprint("qmt", __name__)

# Global QMT bridge instance (lazily created; mock mode only for API routes)
_qmt_bridge: Any = None


def _get_bridge() -> Any:
    """Return the shared QMT bridge instance (always mock by default).

    **Mock mode is intentional.**  API routes never connect to a real broker
    or instantiate ``QmtBridge(use_mock=False)``.

    Real QMT order/query is P3 deferred.
    """
    global _qmt_bridge
    if _qmt_bridge is None:
        from tradingagents.astock.execution.qmt_bridge import QmtBridge

        _qmt_bridge = QmtBridge(use_mock=True)
    return _qmt_bridge


def _bridge_status(bridge: Any) -> dict[str, Any]:
    """Build a common status dict injected into every QMT response.

    Every QMT endpoint adds this dict so the caller can unambiguously
    determine whether the data is mock / real / unavailable.

    Capability level: ``managed`` (mock/read-only).
    Real QMT order/query is P3 deferred.
    """
    return {
        "source": "mock",
        "mock": True,
        "read_only": True,  # All current QMT routes are read-only
        "live_ready": False,  # Not connected to a real broker
        "capability": "managed",
        "allows_real_broker_order": False,
        "allows_real_order_query": False,
        "real_connection_check_enabled": False,
        "note": "mock/read-only — real QMT order/query is P3 deferred",
    }


# ---------------------------------------------------------------------------
# GET /api/v1/qmt/health
# ---------------------------------------------------------------------------


@bp.route("/qmt/health")
def qmt_health() -> tuple[Response, int]:
    """QMT bridge health check.

    **Capability: ``managed`` (mock/read-only)**

    Query params:
        Ignored.  Real QMT checks are disabled in API routes.
    """
    try:
        bridge = _get_bridge()
        ok = bridge.health_check()

        return jsonify(
            {
                "healthy": ok,
                "mock_mode": True,
                "host": bridge.config.host,
                "port": bridge.config.port,
                "real_healthy": False,
                "real_error": "disabled: QMT real connection checks are P3 deferred",
                "real_connection_check": {
                    "enabled": False,
                    "reason": "QMT real broker/order query is P3 deferred",
                },
                "status": _bridge_status(bridge),
            }
        ), 200
    except Exception as exc:
        return error_response(str(exc), 500)


# ---------------------------------------------------------------------------
# GET /api/v1/qmt/positions
# ---------------------------------------------------------------------------


@bp.route("/qmt/positions")
def qmt_positions() -> tuple[Response, int]:
    """QMT current positions (read-only, mock by default)."""
    try:
        bridge = _get_bridge()
        positions = bridge.get_positions()
        return jsonify({
            "positions": positions,
            "mock_mode": bridge.is_mock,
            "status": _bridge_status(bridge),
        }), 200
    except Exception as exc:
        return error_response(str(exc), 500)


# ---------------------------------------------------------------------------
# GET /api/v1/qmt/orders
# ---------------------------------------------------------------------------


@bp.route("/qmt/orders")
def qmt_orders() -> tuple[Response, int]:
    """QMT account snapshot (read-only, mock only).

    NOTE: This endpoint does not query actual order records.  The ``orders``
    key is retained as an empty compatibility field; consumers should read
    ``account_snapshot`` for the mock account state.
    """
    try:
        bridge = _get_bridge()
        account_info = bridge.get_account_info()
        account_snapshot = {
            "account_id": account_info.get("account_id", ""),
            "total_asset": account_info.get("total_asset", 0),
            "cash": account_info.get("cash", 0),
            "market_value": account_info.get("market_value", 0),
            "frozen_cash": account_info.get("frozen_cash", 0),
            "available_cash": account_info.get("available_cash", 0),
        }
        return jsonify({
            "orders": [],
            "account_snapshot": account_snapshot,
            "mock_mode": True,
            "status": _bridge_status(bridge),
        }), 200
    except Exception as exc:
        return error_response(str(exc), 500)
