"""Data query API routes — read data from the DuckDB AStockStore.

All routes return JSON.  Error responses follow ``{"error": ..., "status": N}``.

Uses lazy imports for ``tradingagents.astock.*`` to avoid the full dependency
chain at module load time.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

bp = Blueprint("data", __name__)


def _store() -> Any:
    """Grab the store from app config (lazy; already initialised by factory)."""
    return current_app.config["STORE"]


def _df_to_json(df: Any) -> list[dict[str, Any]]:
    """Convert a pandas DataFrame to a list of plain dicts."""
    if df is None or (hasattr(df, "empty") and df.empty):
        return []
    if hasattr(df, "to_dict"):
        return df.to_dict(orient="records")
    return list(df)


# ---------------------------------------------------------------------------
# Kline bars
# ---------------------------------------------------------------------------


@bp.route("/kline")
def get_kline() -> tuple[Response, int]:
    """GET /api/v1/kline?symbol=600519.SH&start=2024-01-01&end=2024-06-01&interval=1d"""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    start = request.args.get("start")
    end = request.args.get("end")
    interval = request.args.get("interval", "1d")
    try:
        df = _store().query_kline(symbol, start=start, end=end, interval=interval)
        return jsonify({"symbol": symbol, "interval": interval, "bars": _df_to_json(df)}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Valuation
# ---------------------------------------------------------------------------


@bp.route("/valuation")
def get_valuation() -> tuple[Response, int]:
    """GET /api/v1/valuation?symbol=600519.SH"""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    try:
        df = _store().query_valuations(symbol)
        return jsonify({"symbol": symbol, "valuations": _df_to_json(df)}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Order book
# ---------------------------------------------------------------------------


@bp.route("/orderbook")
def get_orderbook() -> tuple[Response, int]:
    """GET /api/v1/orderbook?symbol=600519.SH"""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    try:
        df = _store().query_order_book(symbol)
        return jsonify({"symbol": symbol, "snapshots": _df_to_json(df)}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------


@bp.route("/news")
def get_news() -> tuple[Response, int]:
    """GET /api/v1/news?symbol=600519.SH&limit=20"""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    limit_str = request.args.get("limit", "20")
    try:
        limit = int(limit_str)
    except ValueError:
        limit = 20
    try:
        df = _store().query_news_items(symbol)
        items = _df_to_json(df)
        return jsonify({"symbol": symbol, "news": items[:limit]}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Research reports
# ---------------------------------------------------------------------------


@bp.route("/research")
def get_research() -> tuple[Response, int]:
    """GET /api/v1/research?symbol=600519.SH&limit=20"""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    limit_str = request.args.get("limit", "20")
    try:
        limit = int(limit_str)
    except ValueError:
        limit = 20
    try:
        df = _store().query_research_reports(symbol)
        items = _df_to_json(df)
        return jsonify({"symbol": symbol, "reports": items[:limit]}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------


@bp.route("/announcements")
def get_announcements() -> tuple[Response, int]:
    """GET /api/v1/announcements?symbol=600519.SH&limit=20"""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    limit_str = request.args.get("limit", "20")
    try:
        limit = int(limit_str)
    except ValueError:
        limit = 20
    try:
        df = _store().query_announcements(symbol)
        items = _df_to_json(df)
        return jsonify({"symbol": symbol, "announcements": items[:limit]}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Store stats
# ---------------------------------------------------------------------------


@bp.route("/store/stats")
def get_store_stats() -> tuple[Response, int]:
    """GET /api/v1/store/stats — DuckDB table statistics."""
    try:
        stats = _store().get_table_stats()
        return jsonify({"stats": stats}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500
