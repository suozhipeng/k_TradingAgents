"""Watchlist CRUD API — Web-P2.

GET    /api/v1/watchlist          → list of tracked symbols
POST   /api/v1/watchlist/add      → {symbol, name}
POST   /api/v1/watchlist/remove   → {symbol}
POST   /api/v1/watchlist/batch-analyze → batch AI analysis for all watchlist symbols

Uses DuckDB ``watchlist`` table as the sole storage backend.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from flask import Blueprint, Response, jsonify, request

from .envelope import error_response, success_response

from ._analysis_engine import analyze_stock_symbol

logger = logging.getLogger(__name__)

bp = Blueprint("watchlist", __name__)

def _load_from_duckdb(store: Any) -> list[dict[str, Any]]:
    """Load watchlist from DuckDB watchlist table."""
    try:
        if store is None:
            raise RuntimeError("watchlist store unavailable")
        df = store.query_sql('SELECT symbol, name, added_at, source FROM watchlist ORDER BY added_at DESC')
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")
    except Exception as exc:
        logger.exception("DuckDB watchlist load failed")
        raise RuntimeError("watchlist store unavailable") from exc


def _save_to_duckdb(store: Any, items: list[dict[str, Any]]) -> None:
    """Save watchlist to DuckDB watchlist table."""
    try:
        if store is None or not hasattr(store, "replace_watchlist"):
            raise RuntimeError("watchlist store unavailable")
        store.replace_watchlist(items)
    except Exception as exc:
        logger.exception("DuckDB watchlist save failed")
        raise RuntimeError("watchlist store unavailable") from exc


def _load() -> list[dict[str, Any]]:
    """Load watchlist from the configured DuckDB store."""
    from flask import current_app
    store = current_app.config.get("STORE") if current_app else None
    return _load_from_duckdb(store)


def _save(items: list[dict[str, Any]]) -> None:
    """Save watchlist to the configured DuckDB store."""
    from flask import current_app
    store = current_app.config.get("STORE") if current_app else None
    _save_to_duckdb(store, items)


# ---------------------------------------------------------------------------
# GET /api/v1/watchlist
# ---------------------------------------------------------------------------


@bp.route("/watchlist", methods=["GET"])
def get_watchlist() -> WatchlistResponse:
    """Return the current watchlist symbols."""
    try:
        items = _load()
    except RuntimeError as exc:
        return error_response("watchlist_store_unavailable", 503, detail=str(exc))
    return success_response({"items": items, "count": len(items)})


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
        return error_response("symbol is required", 400)

    try:
        items = _load()
    except RuntimeError as exc:
        return error_response("watchlist_store_unavailable", 503, detail=str(exc))

    # Check duplicates
    existing = {it.get("symbol", "").upper() for it in items if it.get("symbol")}
    if symbol in existing:
        return error_response(f"Symbol {symbol} already in watchlist", 409)

    entry = {
        "symbol": symbol,
        "name": name or symbol,
        "added_at": datetime.now().isoformat(),
        "source": data.get("source", "manual"),
    }
    items.append(entry)
    try:
        _save(items)
    except RuntimeError as exc:
        return error_response("watchlist_store_unavailable", 503, detail=str(exc))

    logger.info("Watchlist add: %s (%s)", symbol, name)
    return success_response({"item": entry, "count": len(items)}, status=201)


# ---------------------------------------------------------------------------
# POST /api/v1/watchlist/remove
# ---------------------------------------------------------------------------


@bp.route("/watchlist/remove", methods=["POST"])
def remove_symbol() -> WatchlistResponse:
    """Remove a symbol from the watchlist."""
    data = request.get_json(silent=True) or {}
    symbol = (data.get("symbol") or "").strip().upper()

    if not symbol:
        return error_response("symbol is required", 400)

    try:
        items = _load()
    except RuntimeError as exc:
        return error_response("watchlist_store_unavailable", 503, detail=str(exc))
    before = len(items)
    items = [it for it in items if it.get("symbol", "").upper() != symbol]
    removed = before - len(items)

    if removed == 0:
        return error_response(f"Symbol {symbol} not found in watchlist", 404)

    try:
        _save(items)
    except RuntimeError as exc:
        return error_response("watchlist_store_unavailable", 503, detail=str(exc))
    logger.info("Watchlist remove: %s", symbol)
    return success_response({"removed": removed, "count": len(items)})


# ---------------------------------------------------------------------------
# POST /api/v1/watchlist/batch-analyze
# ---------------------------------------------------------------------------


@bp.route("/watchlist/batch-analyze", methods=["POST"])
def batch_analyze() -> WatchlistResponse:
    """Submit all watchlist symbols for batch analysis.

    Performs technical analysis on all watchlist symbols and optionally
    triggers AI analysis if LLM is configured.
    """
    try:
        items = _load()
    except RuntimeError as exc:
        return error_response("watchlist_store_unavailable", 503, detail=str(exc))
    if not items:
        return error_response("Watchlist is empty", 400)

    symbols = [it["symbol"] for it in items if it.get("symbol")]
    from flask import current_app

    store = current_app.config.get("STORE")
    if not store:
        return error_response("Store not available", 503)

    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    counts = {"buy": 0, "hold": 0, "sell": 0}

    for sym in symbols:
        try:
            df = store.query_research_reports(sym)
            if df is not None and not df.empty:
                reports = df.tail(3).to_dict(orient="records")
            else:
                reports = []

            tech = analyze_stock_symbol(sym, sym)

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

    return success_response({
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
    })


__all__ = ["bp"]
