"""Data query API routes — read data from the DuckDB AStockStore.

All routes return JSON.  Error responses follow ``{"error": ..., "status": N}``.

Uses lazy imports for ``tradingagents.astock.*`` to avoid the full dependency
chain at module load time.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

bp = Blueprint("data", __name__)

logger = logging.getLogger(__name__)


def _store() -> Any:
    """Grab the store from app config (lazy; already initialised by factory)."""
    return current_app.config["STORE"]


def _router() -> Any:
    """Grab the AStockDataFacade/router from app config (lazy)."""
    return current_app.config.get("DATA_FACADE")


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


# ---------------------------------------------------------------------------
# Data refresh (manual pull from provider → DuckDB)
# ---------------------------------------------------------------------------


@bp.route("/data/refresh/kline", methods=["POST"])
def refresh_kline() -> tuple[Response, int]:
    """POST /api/v1/data/refresh/kline
    JSON: {"symbol": "600519.SH", "start": "2026-01-01", "end": "2026-06-15"}
    """
    body = request.get_json(force=True, silent=True) or {}
    symbol = body.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    start = body.get("start")
    end = body.get("end")
    interval = body.get("interval", "1d")
    try:
        from tradingagents.astock.store.loader import KlineLoader

        store = _store()
        router = _router()
        loader = KlineLoader(store, router)
        count = loader.load(symbol, start=start, end=end, interval=interval)
        return jsonify({"symbol": symbol, "rows_inserted": count, "status": "ok"}), 200
    except Exception as exc:
        logger.warning("Refresh kline failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/data/refresh/valuation", methods=["POST"])
def refresh_valuation() -> tuple[Response, int]:
    """POST /api/v1/data/refresh/valuation
    JSON: {"symbol": "600519.SH"}
    """
    body = request.get_json(force=True, silent=True) or {}
    symbol = body.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    try:
        from tradingagents.astock.store.loader import ValuationLoader

        store = _store()
        router = _router()
        loader = ValuationLoader(store, router)
        count = loader.load(symbol)
        return jsonify({"symbol": symbol, "rows_inserted": count, "status": "ok"}), 200
    except Exception as exc:
        logger.warning("Refresh valuation failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/data/refresh/all", methods=["POST"])
def refresh_all() -> tuple[Response, int]:
    """POST /api/v1/data/refresh/all
    JSON: {"symbols": ["600519.SH", "000001.SZ"], "start": "2026-01-01", "end": "2026-06-15"}
    """
    body = request.get_json(force=True, silent=True) or {}
    symbols = body.get("symbols", [])
    if not symbols:
        return jsonify({"error": "symbols list is required", "status": 400}), 400
    start = body.get("start")
    end = body.get("end")
    interval = body.get("interval", "1d")
    try:
        from tradingagents.astock.store.loader import BatchLoader

        store = _store()
        router = _router()
        loader = BatchLoader(store, router)
        results = loader.load_all(symbols, kline_start=start, kline_end=end)
        return jsonify({"results": results, "status": "ok"}), 200
    except Exception as exc:
        logger.warning("Refresh all failed: %s", exc)
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------


@bp.route("/cache/status")
def cache_status() -> tuple[Response, int]:
    """GET /api/v1/cache/status — in-memory cache stats."""
    try:
        router = _router()
        if not router or not hasattr(router, 'router'):
            return jsonify({"cache": {"enabled": False}}), 200
        cache = router.router.cache if hasattr(router, 'router') else None
        if cache is None:
            return jsonify({"cache": {"enabled": False}}), 200
        info = {"enabled": True, "type": type(cache).__name__}
        if hasattr(cache, "_snapshots"):
            info["snapshots"] = len(cache._snapshots)
        if hasattr(cache, "_history_ranges"):
            info["history_ranges"] = len(cache._history_ranges)
        if hasattr(cache, "_summaries"):
            info["summaries"] = len(cache._summaries)
        return jsonify({"cache": info}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/cache/clear", methods=["POST"])
def cache_clear() -> tuple[Response, int]:
    """POST /api/v1/cache/clear — clear all in-memory caches."""
    try:
        router = _router()
        if not router:
            return jsonify({"status": "ok", "cleared": False, "reason": "no router"}), 200
        cache = router.router.cache if hasattr(router, 'router') else None
        if cache and hasattr(cache, "clear"):
            cache.clear()
            return jsonify({"status": "ok", "cleared": True}), 200
        return jsonify({"status": "ok", "cleared": False, "reason": "cache has no clear()"}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500
