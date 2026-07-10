"""Paper trading API routes — trigger and query simulated trading state.

All routes return JSON.  Error responses follow ``{"error": ..., "status": N}``.

Uses lazy imports for ``tradingagents.astock.execution.paper_trader``.
"""

from __future__ import annotations

import logging

from typing import Any

from flask import Blueprint, Response, jsonify, request

from ._paper_service import get_paper_trader, serialize_paper_state, serialize_paper_trades
logger = logging.getLogger(__name__)

bp = Blueprint("paper", __name__)


# ---------------------------------------------------------------------------
# POST /api/v1/paper/cycle
# ---------------------------------------------------------------------------


@bp.route("/paper/cycle", methods=["POST"])
def paper_cycle() -> tuple[Response, int]:
    data = request.get_json(silent=True) or {}
    signals = data.get("signals", {})
    prices = data.get("prices", {})

    if not signals:
        return jsonify({"error": "signals dict is required", "status": 400}), 400
    if not prices:
        return jsonify({"error": "prices dict is required", "status": 400}), 400

    try:
        trader = get_paper_trader()
        state = trader.execute_cycle(signals, prices)
        return jsonify(serialize_paper_state(trader)), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/paper/state
# ---------------------------------------------------------------------------


@bp.route("/paper/state")
def paper_state() -> tuple[Response, int]:
    try:
        trader = get_paper_trader()
        return jsonify(serialize_paper_state(trader)), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/paper/trades
# ---------------------------------------------------------------------------


@bp.route("/paper/trades")
def paper_trades() -> tuple[Response, int]:
    try:
        limit = int(request.args.get("limit", "0"))
        trader = get_paper_trader()
        trades = serialize_paper_trades(trader)
        count = len(trades)
        if limit > 0:
            trades = trades[-limit:]
        return jsonify({
            "trades": trades, "count": count, "limit": limit or count,
        }), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500
