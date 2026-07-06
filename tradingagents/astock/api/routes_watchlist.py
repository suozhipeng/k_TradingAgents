"""Watchlist CRUD API — Web-P2.

GET    /api/v1/watchlist          → list of tracked symbols
POST   /api/v1/watchlist/add      → {symbol, name}
POST   /api/v1/watchlist/remove   → {symbol}
POST   /api/v1/watchlist/batch-analyze → batch AI analysis for all watchlist symbols

Uses DuckDB ``watchlist`` table as primary storage with JSON file fallback.
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

# ---------------------------------------------------------------------------
# Watchlist storage — fallback path lives under the project data dir,
# NOT under the user's HOME, to avoid environment-dependent permissions.
# ---------------------------------------------------------------------------
_WATCHLIST_FALLBACK_DIR = Path(os.environ.get(
    "ASTOCK_WATCHLIST_DIR",
    Path.home() / ".tradingagents",
))
WATCHLIST_PATH = _WATCHLIST_FALLBACK_DIR / "watchlist.json"


def _load_from_duckdb(store: Any) -> list[dict[str, Any]]:
    """Load watchlist from DuckDB watchlist table."""
    try:
        if store is None:
            return []
        df = store.query_sql('SELECT symbol, name, added_at, source FROM watchlist ORDER BY added_at DESC')
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")
    except Exception as exc:
        logger.debug("DuckDB watchlist unavailable: %s", exc)
        return []


def _save_to_duckdb(store: Any, items: list[dict[str, Any]]) -> None:
    """Save watchlist to DuckDB watchlist table."""
    try:
        if store is None:
            return
        import duckdb
        conn = duckdb.connect(store.db_path) if hasattr(store, "db_path") else None
        if conn is None:
            # Try using store's internal connection
            conn = store._conn if hasattr(store, "_conn") else None
        if conn is None:
            return

        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                symbol VARCHAR PRIMARY KEY,
                name VARCHAR,
                added_at TIMESTAMP,
                source VARCHAR DEFAULT 'manual'
            )
        """)
        conn.execute("DELETE FROM watchlist")
        for item in items:
            conn.execute(
                "INSERT INTO watchlist (symbol, name, added_at, source) VALUES (?, ?, ?, ?)",
                [
                    item["symbol"],
                    item.get("name", item["symbol"]),
                    item.get("added_at", datetime.now().isoformat()),
                    item.get("source", "manual"),
                ],
            )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning("DuckDB watchlist save failed, falling back to JSON: %s", exc)
        _save_json(items)


def _load_json() -> list[dict[str, Any]]:
    """Load watchlist from JSON file (legacy fallback)."""
    if not WATCHLIST_PATH.exists():
        return []
    try:
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load watchlist JSON: %s", exc)
        return []


def _json_serializable(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable types to serializable ones."""
    if isinstance(obj, dict):
        return {k: _json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_serializable(v) for v in obj]
    # Handle datetime-like objects (DuckDB Timestamp, pandas Timestamp, etc.)
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    return str(obj)


def _save_json(items: list[dict[str, Any]]) -> None:
    """Save watchlist to JSON file (legacy fallback)."""
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    serializable_items = _json_serializable(items)
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(serializable_items, f, ensure_ascii=False, indent=2)


def _load() -> list[dict[str, Any]]:
    """Load watchlist — tries DuckDB first, falls back to JSON."""
    from flask import current_app
    store = current_app.config.get("STORE") if current_app else None
    items = _load_from_duckdb(store)
    if not items:
        items = _load_json()
    return items


def _save(items: list[dict[str, Any]]) -> None:
    """Save watchlist — tries DuckDB first, falls back to JSON."""
    from flask import current_app
    store = current_app.config.get("STORE") if current_app else None
    _save_to_duckdb(store, items)
    _save_json(items)


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
    """Submit all watchlist symbols for batch analysis.

    Performs technical analysis on all watchlist symbols and optionally
    triggers AI analysis if LLM is configured.
    """
    items = _load()
    if not items:
        return jsonify({"error": "Watchlist is empty", "status": 400}), 400

    symbols = [it["symbol"] for it in items if it.get("symbol")]
    from flask import current_app

    store = current_app.config.get("STORE")
    if not store:
        return jsonify({"error": "Store not available", "status": 503}), 503

    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    counts = {"buy": 0, "hold": 0, "sell": 0}

    for sym in symbols:
        try:
            # Query stored research reports
            df = store.query_research_reports(sym)
            if df is not None and not df.empty:
                reports = df.tail(3).to_dict(orient="records")
            else:
                reports = []

            # Run technical analysis
            from tradingagents.astock.api.routes_analysis import _analyze_stock_symbol
            tech = _analyze_stock_symbol(sym, sym)

            rating = tech.get("rating", "hold")
            if rating in counts:
                counts[rating] += 1

            results.append({
                "symbol": sym,
                "name": tech.get("name", sym),
                "price": tech.get("price", 0),
                "score": tech.get("score", 50),
                "rating": rating,
                "signal": tech.get("signal", ""),
                "reasons": tech.get("reasons", []),
                "reports_count": len(reports),
                "reports": reports,
            })
        except Exception as exc:
            errors.append({"symbol": sym, "error": str(exc)})

    # Sort: buy first, then hold, then sell
    rating_order = {"buy": 0, "hold": 1, "sell": 2}
    results.sort(key=lambda r: (rating_order.get(r.get("rating", "hold"), 9), -r.get("score", 0)))

    return jsonify({
        "status": "complete",
        "total": len(symbols),
        "results_count": len(results),
        "errors_count": len(errors),
        "summary": {"buy": counts["buy"], "hold": counts["hold"], "sell": counts["sell"]},
        "results": results,
        "errors": errors,
        "message": f"完成 {len(results)}/{len(symbols)} 个标的的分析",
        "research_only": True,
        "actionable": False,
    }), 200


__all__ = ["bp"]
