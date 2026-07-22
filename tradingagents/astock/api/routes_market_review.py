"""Market review API backed exclusively by Canonical DuckDB."""

from __future__ import annotations

import json
import logging

from flask import Blueprint, Response, current_app, jsonify, request

from ._helpers import get_store
from .envelope import error_response
from tradingagents.astock.review import MarketReviewEngine

logger = logging.getLogger(__name__)
bp = Blueprint("market_review", __name__)


def _canonical_kline_frame(store, as_of: str | None = None):
    sql = 'SELECT * FROM "kline_bars"'
    params: list[str] = []
    if as_of:
        sql += " WHERE trade_date <= ?"
        params.append(as_of)
    sql += " ORDER BY symbol, trade_date"
    return store.conn.execute(sql, params).fetchdf()


@bp.route("/market/review", methods=["POST", "GET"])
def market_review() -> tuple[Response, int]:
    """Compute and persist a deterministic market review from Canonical DuckDB."""
    store = get_store()
    as_of = request.args.get("as_of") or (request.get_json(silent=True) or {}).get("as_of")
    try:
        frame = _canonical_kline_frame(store, as_of=as_of)
        if frame.empty:
            return jsonify({"status": "not_initialized", "facts": [], "message": "Canonical DuckDB has no kline data"}), 200
        report = MarketReviewEngine(store).run(frame, as_of=as_of)
        return jsonify(report), 200
    except ValueError as exc:
        return error_response(str(exc), 400)
    except Exception as exc:
        logger.exception("market review failed")
        return error_response(f"market review failed: {exc}", 500)


@bp.route("/market/review/<run_id>", methods=["GET"])
def get_market_review(run_id: str) -> tuple[Response, int]:
    """Read a persisted review and its fact lineage after restart."""
    store = get_store()
    try:
        row = store.conn.execute(
            "SELECT report_json FROM market_review_runs WHERE run_id = ?", [run_id]
        ).fetchone()
        if not row:
            return error_response("market review not found", 404)
        return jsonify(row[0] if isinstance(row[0], dict) else json.loads(row[0])), 200
    except Exception as exc:
        return error_response(f"market review read failed: {exc}", 500)
