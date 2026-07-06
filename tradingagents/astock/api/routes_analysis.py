"""Watchlist technical analysis API — thin wrapper around _analysis_engine.

POST /api/v1/analysis/watchlist  — analyze all watchlist stocks using
  pure technical indicators (RSI, MA crossover, volume).  No LLM calls.

All core logic lives in ``_analysis_engine.py`` so that
``routes_dashboard`` and ``routes_watchlist`` can reuse the same functions.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Response, jsonify

from ._analysis_engine import analyze_stock_symbol, load_watchlist

logger = logging.getLogger(__name__)

bp = Blueprint("analysis", __name__)


# ---------------------------------------------------------------------------
# POST /api/v1/analysis/watchlist
# ---------------------------------------------------------------------------


@bp.route("/analysis/watchlist", methods=["POST"])
def analyze_watchlist() -> tuple[Response, int]:
    items = load_watchlist()
    if not items:
        return jsonify({
            "stocks": [],
            "summary": {"total": 0, "buy": 0, "hold": 0, "sell": 0},
            "message": "暂无自选股",
        }), 200

    results: list[dict[str, Any]] = []
    for item in items:
        symbol = item.get("symbol", "").strip()
        name = item.get("name", symbol)
        if not symbol:
            continue
        result = analyze_stock_symbol(symbol, name)
        results.append(result)

    counts = {"buy": 0, "hold": 0, "sell": 0}
    for r in results:
        rating = r.get("rating", "hold")
        if rating in counts:
            counts[rating] += 1

    rating_order = {"buy": 0, "hold": 1, "sell": 2}
    results.sort(key=lambda r: (rating_order.get(r.get("rating", "hold"), 9), -r.get("score", 0)))

    return jsonify({
        "stocks": results,
        "summary": {
            "total": len(results),
            "buy": counts["buy"],
            "hold": counts["hold"],
            "sell": counts["sell"],
        },
    }), 200
