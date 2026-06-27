"""Watchlist CRUD API — Web-P2.

GET    /api/v1/watchlist          → list of tracked symbols
POST   /api/v1/watchlist/add      → {symbol, name}
POST   /api/v1/watchlist/remove   → {symbol}

Uses a JSON file at ~/.tradingagents/watchlist.json as temporary storage.
TODO: migrate to DuckDB persistence.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

logger = logging.getLogger(__name__)

bp = Blueprint("watchlist", __name__)

# Tuple type alias used by all endpoint functions
WatchlistResponse = tuple[Response, int] | Response

WATCHLIST_PATH = Path.home() / ".tradingagents" / "watchlist.json"


def _load() -> list[dict[str, Any]]:
    """Load watchlist from JSON file."""
    if not WATCHLIST_PATH.exists():
        return []
    try:
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load watchlist: %s", exc)
        return []


def _save(items: list[dict[str, Any]]) -> None:
    """Save watchlist to JSON file."""
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# GET /api/v1/watchlist
# ---------------------------------------------------------------------------


@bp.route("/watchlist", methods=["GET"])
def get_watchlist() -> WatchlistResponse:
    """Return the current watchlist symbols."""
    items = _load()
    return jsonify({"items": items, "count": len(items)})


# ---------------------------------------------------------------------------
# POST /api/v1/watchlist/add
# ---------------------------------------------------------------------------


@bp.route("/watchlist/add", methods=["POST"])
def add_symbol() -> WatchlistResponse:
    """Add a symbol to the watchlist."""
    data = request.get_json(silent=True) or {}
    symbol = (data.get("symbol") or "").strip().upper()
    name = (data.get("name") or "").strip()

    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400

    items = _load()

    # Check duplicates
    existing = {it.get("symbol", "").upper() for it in items if it.get("symbol")}
    if symbol in existing:
        return jsonify({"error": f"Symbol {symbol} already in watchlist", "status": 409}), 409

    entry = {
        "symbol": symbol,
        "name": name or symbol,
        "added_at": datetime.now().isoformat(),
        "source": data.get("source", "manual"),
    }
    items.append(entry)
    _save(items)

    logger.info("Watchlist add: %s (%s)", symbol, name)
    return jsonify({"item": entry, "count": len(items), "status": "ok"}), 201


# ---------------------------------------------------------------------------
# POST /api/v1/watchlist/remove
# ---------------------------------------------------------------------------


@bp.route("/watchlist/remove", methods=["POST"])
def remove_symbol() -> WatchlistResponse:
    """Remove a symbol from the watchlist."""
    data = request.get_json(silent=True) or {}
    symbol = (data.get("symbol") or "").strip().upper()

    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400

    items = _load()
    before = len(items)
    items = [it for it in items if it.get("symbol", "").upper() != symbol]
    removed = before - len(items)

    if removed == 0:
        return jsonify({"error": f"Symbol {symbol} not found in watchlist", "status": 404}), 404

    _save(items)
    logger.info("Watchlist remove: %s", symbol)
    return jsonify({"removed": removed, "count": len(items), "status": "ok"}), 200


# ---------------------------------------------------------------------------
# POST /api/v1/watchlist/batch-analyze
# ---------------------------------------------------------------------------


@bp.route("/watchlist/batch-analyze", methods=["POST"])
def batch_analyze() -> WatchlistResponse:
    """Submit all watchlist symbols for batch analysis."""
    items = _load()
    if not items:
        return jsonify({"error": "Watchlist is empty", "status": 400}), 400

    symbols = [it["symbol"] for it in items if it.get("symbol")]

    # Placeholder: creates a task record via the ops API pattern
    # In real implementation, this would enqueue the batch analysis job
    from flask import current_app

    store = current_app.config.get("STORE")
    task_id = None
    if store and hasattr(store, "create_task"):
        try:
            task_id = store.create_task(
                name=f"batch-analyze-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                type="batch_analysis",
                params={"symbols": symbols, "count": len(symbols)},
            )
        except Exception as exc:
            logger.warning("Could not persist batch task: %s", exc)

    return jsonify(
        {
            "status": "queued",
            "symbols_count": len(symbols),
            "symbols": symbols,
            "task_id": task_id,
            "message": f"已提交 {len(symbols)} 个标的的批量分析任务",
        }
    ), 202


__all__ = ["bp"]
