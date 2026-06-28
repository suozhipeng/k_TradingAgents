"""Data query API routes — read data from the DuckDB AStockStore.

All routes return JSON.  Error responses follow ``{"error": ..., "status": N}``.

Uses lazy imports for ``tradingagents.astock.*`` to avoid the full dependency
chain at module load time.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import pandas as pd

from flask import Blueprint, Response, current_app, jsonify, request

from ._helpers import df_to_json

# Backward-compatible alias
_df_to_json = df_to_json

bp = Blueprint("data", __name__)

logger = logging.getLogger(__name__)


def _store() -> Any:
    """Grab the store from app config (lazy; already initialised by factory)."""
    return current_app.config["STORE"]


def _router() -> Any:
    """Grab the AStockDataFacade/router from app config (lazy)."""
    return current_app.config.get("DATA_FACADE")


def _jobs() -> Any:
    """Grab the in-process data job manager from app config."""
    return current_app.config["DATA_JOB_MANAGER"]


def _int_param(name: str, default: int) -> int:
    """Parse an int query param with safe fallback."""
    raw = request.args.get(name, str(default))
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default


# ── NaN 清洗工具（Flask jsonify 不兼容 NaN）──
def _clean_nan(obj: Any) -> Any:
    """Recursively replace NaN floats with None in dicts/lists/scalars."""
    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nan(v) for v in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


def _with_meta(payload: dict, resp: Any) -> dict:
    """Merge ``resp.meta`` (quality tag, source info) into a JSON payload."""
    if hasattr(resp, "meta") and resp.meta:
        payload["meta"] = dict(resp.meta)
    return payload


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _records_from_body(body: dict[str, Any]) -> list[dict[str, Any]]:
    records = body.get("records")
    if records is None and "record" in body:
        records = [body["record"]]
    if records is None:
        records = []
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        raise ValueError("records must be a list or object")
    if any(not isinstance(item, dict) for item in records):
        raise ValueError("each record must be an object")
    return [dict(item) for item in records]


def _known_symbols_or_payload(body: dict[str, Any]) -> list[str]:
    symbols = body.get("symbols")
    if symbols in (None, "", "all"):
        return _store().list_symbols()
    if isinstance(symbols, str):
        return [symbols]
    return [str(item) for item in symbols if item]


def _raw_store() -> Any:
    """Return the underlying store when the app wraps it with ValidatedStore."""
    store = _store()
    return getattr(store, "_store", store)


def _table_columns(table_name: str) -> set[str]:
    raw = _raw_store()
    if hasattr(raw, "_table_columns"):
        return set(raw._table_columns(table_name))
    if hasattr(raw, "table_columns"):
        return set(raw.table_columns(table_name))
    return set()


def _validate_manual_rows(table_name: str, rows: list[dict[str, Any]]) -> None:
    """Validate manual insert payloads before they reach the store.

    The store still enforces constraints and quality rules; this check catches
    user-facing input mistakes early so the API can return a clear 4xx message.
    """
    raw = _raw_store()
    if hasattr(raw, "table_exists") and not raw.table_exists(table_name):
        raise ValueError(f"Unknown table: {table_name}")

    allowed = _table_columns(table_name)
    if allowed:
        aliases = set()
        if table_name == "kline_bars":
            aliases.update({"date", "datetime", "time", "turnover"})
        if table_name == "valuations":
            aliases.update({"date", "pe_ttm", "market_value"})
        unknown = sorted(
            {key for row in rows for key in row}
            - allowed
            - aliases
        )
        if unknown:
            raise ValueError(
                f"Unknown field(s) for {table_name}: {', '.join(unknown)}"
            )

    if table_name == "kline_bars":
        date_fields = {"bar_time", "trade_date", "date", "datetime", "time"}
        for idx, row in enumerate(rows):
            if not row.get("symbol"):
                raise ValueError(f"records[{idx}].symbol is required")
            if not any(row.get(field) for field in date_fields):
                raise ValueError(
                    f"records[{idx}] requires one of: bar_time, trade_date, date, datetime, time"
                )
            if row.get("interval"):
                normalise = getattr(raw, "_normalise_interval", None)
                if normalise is not None:
                    normalise(str(row["interval"]))

    if table_name == "valuations":
        for idx, row in enumerate(rows):
            if not row.get("symbol"):
                raise ValueError(f"records[{idx}].symbol is required")
            if not (row.get("trade_date") or row.get("date")):
                raise ValueError(f"records[{idx}].trade_date is required")


def _insert_error_response(exc: Exception) -> tuple[Response, int]:
    """Map insert failures to user-facing API responses."""
    from tradingagents.astock.quality import BlockedImportError

    if isinstance(exc, BlockedImportError):
        return jsonify({
            "error": "data_quality_blocked",
            "message": str(exc),
            "violations": getattr(exc, "violations", []),
            "status": 422,
        }), 422
    if isinstance(exc, ValueError):
        return jsonify({
            "error": "invalid_input",
            "message": str(exc),
            "status": 400,
        }), 400
    return jsonify({
        "error": "insert_failed",
        "message": str(exc),
        "status": 500,
    }), 500


# ---------------------------------------------------------------------------
# Kline bars
# ---------------------------------------------------------------------------


@bp.route("/kline")
def get_kline() -> tuple[Response, int]:
    """GET /api/v1/kline?symbol=600519.SH&start=2024-01-01&end=2024-06-01&interval=1d&limit=5

    Store-first: reads from DuckDB.  If empty, fetches live via the router chain,
    persists the result to DuckDB, then returns.
    """
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    start = request.args.get("start")
    end = request.args.get("end")
    interval = request.args.get("interval", "1d")
    limit = _int_param("limit", 0)
    try:
        store = _store()
        df = store.query_kline(symbol, start=start, end=end, interval=interval)
        bars = _df_to_json(df)

        # If store has no data, try live fetch and persist
        if not bars:
            router = _router()
            if router is not None:
                try:
                    resp = router.get_kline(symbol, interval=interval, limit=limit or 400)
                    if resp.status == "ok" and resp.data:
                        data = resp.data
                        items = data.get("items") or data.get("bars", [])
                        if isinstance(items, list) and len(items) > 0:
                            first_date = items[0].get("date") or items[0].get("trade_date") or ""

                            # Persist both daily and minute bars; kline_bars uses bar_time TIMESTAMP.
                            source_str = resp.source or ""
                            if hasattr(resp, "meta") and resp.meta:
                                source_str = source_str or resp.meta.get("source", "")

                            # Normalise field names for store.insert_kline
                            for item in items:
                                if "trade_date" not in item and "date" in item:
                                    item["trade_date"] = item["date"]

                            df_live = pd.DataFrame(items)
                            if "trade_date" in df_live.columns:
                                store.insert_kline(symbol, df_live, interval=interval, source=source_str)

                            # Re-query to get the persisted data within requested range
                            df2 = store.query_kline(symbol, start=start, end=end, interval=interval)
                            bars = _df_to_json(df2)
                except Exception:
                    logger.warning("live kline fetch failed for %s interval=%s", symbol, interval, exc_info=True)

        if limit > 0 and bars:
            bars = bars[-limit:]
        return jsonify({"symbol": symbol, "interval": interval, "bars": bars}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Valuation
# ---------------------------------------------------------------------------


@bp.route("/valuation")
def get_valuation() -> tuple[Response, int]:
    """GET /api/v1/valuation?symbol=600519.SH&limit=5"""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    limit = _int_param("limit", 0)
    try:
        store = _store()
        df = store.query_valuations(symbol)
        valuations = _df_to_json(df)
        if limit > 0:
            valuations = valuations[-limit:]

        # If store has no data, try live fetch and persist
        if not valuations:
            router = _router()
            if router is not None:
                try:
                    resp = router.get_valuation(symbol)
                    if resp.status == "ok" and resp.data:
                        items = resp.data.get("items") or resp.data.get("valuations")
                        if items is None and any(k in resp.data for k in ("pe", "pb", "market_cap", "price")):
                            items = [resp.data]
                        if items:
                            source_str = resp.source or ""
                            df_live = pd.DataFrame(items)
                            if "trade_date" not in df_live.columns and "date" not in df_live.columns:
                                from datetime import date
                                df_live["trade_date"] = date.today()
                            store.insert_valuations(symbol, df_live, source=source_str)
                            df = store.query_valuations(symbol)
                            valuations = _df_to_json(df)
                            if limit > 0:
                                valuations = valuations[-limit:]
                except Exception:
                    logger.warning("live valuation fetch failed for %s", symbol, exc_info=True)

        return jsonify({"symbol": symbol, "valuations": valuations}), 200
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
    limit = _int_param("limit", 20)
    try:
        df = _store().query_news_items(symbol)
        items = _df_to_json(df)
        return jsonify({"symbol": symbol, "news": items[-limit:] if limit > 0 else items}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/news/live")
def get_news_live() -> tuple[Response, int]:
    """GET /api/v1/news/live?symbol=600519.SH&limit=20&type=flash&source=em
    type:   flash (快讯, 默认) | global (全球新闻)
    source: em (东方财富, 默认) | sina (新浪) | futu (富途) | ths (同花顺)
    """
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    limit = _int_param("limit", 20)
    news_type = request.args.get("type", "flash")
    news_source = request.args.get("source", "em")
    try:
        router = _router()
        if not router:
            return jsonify({"error": "data router not available", "status": 503}), 503
        if news_type == "global":
            resp = router.get_global_news(symbol, limit=limit)
        else:
            resp = router.get_flash_news(symbol, limit=limit, extras={"news_source": news_source})
        if resp.status == "ok" and resp.data:
            return jsonify({
                "symbol": symbol,
                "type": news_type,
                "source": resp.data.get("source", news_source),
                "items": resp.data.get("items", []),
                "count": resp.data.get("count", 0),
            }), 200
        return jsonify({"symbol": symbol, "type": news_type, "items": [], "count": 0, "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("news live failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/news/stock")
def get_stock_news_route() -> tuple[Response, int]:
    """GET /api/v1/news/stock?symbol=600519.SH&limit=10
    个股新闻，基于 akshare.stock_news_em（东方财富）
    """
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    limit = _int_param("limit", 10)
    try:
        router = _router()
        if not router:
            return jsonify({"error": "data router not available", "status": 503}), 503
        resp = router.get_stock_news(symbol, limit=limit)
        if resp.status == "ok" and resp.data:
            return jsonify(_with_meta({
                "symbol": symbol,
                "items": resp.data.get("items", []),
                "count": resp.data.get("count", 0),
            }, resp)), 200
        return jsonify({"symbol": symbol, "items": [], "count": 0, "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("stock news failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Trade tape (逐笔成交)
# ---------------------------------------------------------------------------


@bp.route("/trade_tape")
def get_trade_tape() -> tuple[Response, int]:
    """GET /api/v1/trade_tape?symbol=600519.SH&limit=50"""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    limit = _int_param("limit", 50)
    try:
        router = _router()
        if not router:
            return jsonify({"error": "data router not available", "status": 503}), 503
        resp = router.get_trade_tape(symbol, limit=limit)
        if resp.status == "ok" and resp.data:
            return jsonify(_with_meta({"symbol": symbol, "ticks": resp.data.get("items", []), "count": resp.data.get("count", 0)}, resp)), 200
        return jsonify({"symbol": symbol, "ticks": [], "count": 0, "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("trade_tape failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Research — PDF download, institution expectation, search
# ---------------------------------------------------------------------------


@bp.route("/research")
def get_research() -> tuple[Response, int]:
    """GET /api/v1/research?symbol=600519.SH&limit=20"""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    limit = _int_param("limit", 20)
    try:
        df = _store().query_research_reports(symbol)
        items = _df_to_json(df)
        return jsonify({"symbol": symbol, "reports": items[-limit:] if limit > 0 else items}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/research/pdf")
def get_research_pdf() -> tuple[Response, int]:
    """GET /api/v1/research/pdf?symbol=600519.SH&title=2025年报"""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    title = request.args.get("title", "")
    try:
        router = _router()
        if not router:
            return jsonify({"error": "data router not available", "status": 503}), 503
        kwargs = {"title": title} if title else {}
        resp = router.download_research_pdf(symbol, **kwargs)
        if resp.status == "ok" and resp.data:
            return jsonify(resp.data), 200
        return jsonify({"error": resp.error_message or "no research pdf"}), 404
    except Exception as exc:
        logger.warning("research pdf failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/research/expectation")
def get_research_expectation() -> tuple[Response, int]:
    """GET /api/v1/research/expectation?symbol=600519.SH&limit=10"""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    limit = _int_param("limit", 10)
    try:
        router = _router()
        if not router:
            return jsonify({"error": "data router not available", "status": 503}), 503
        resp = router.get_institution_expectation(symbol, limit=limit)
        if resp.status == "ok" and resp.data:
            return jsonify(_with_meta({"symbol": symbol, "items": resp.data.get("items", []), "count": resp.data.get("count", 0)}, resp)), 200
        return jsonify({"symbol": symbol, "items": [], "count": 0, "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("research expectation failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/research/search")
def get_research_search() -> tuple[Response, int]:
    """GET /api/v1/research/search?symbol=600519.SH&query=%E8%8C%85%E5%8F%B0&limit=10"""
    symbol = request.args.get("symbol", "")
    query = request.args.get("query", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    if not query:
        return jsonify({"error": "query is required", "status": 400}), 400
    limit = _int_param("limit", 10)
    try:
        router = _router()
        if not router:
            return jsonify({"error": "data router not available", "status": 503}), 503
        resp = router.search_research(symbol, query=query, limit=limit)
        if resp.status == "ok" and resp.data:
            return jsonify(_with_meta({"symbol": symbol, "query": query, "items": resp.data.get("items", []), "count": resp.data.get("count", 0)}, resp)), 200
        return jsonify({"symbol": symbol, "query": query, "items": [], "count": 0, "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("research search failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Fundamentals (财务指标 + F10)
# ---------------------------------------------------------------------------


@bp.route("/fundamentals")
def get_fundamentals() -> tuple[Response, int]:
    """GET /api/v1/fundamentals?symbol=600519.SH&limit=10"""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    limit = _int_param("limit", 10)
    try:
        router = _router()
        if not router:
            return jsonify({"error": "data router not available", "status": 503}), 503
        resp = router.get_fundamentals(symbol, limit=limit)
        if resp.status == "ok" and resp.data:
            items = resp.data.get("items", [])
            # 清除 NaN 值（Flask jsonify 不兼容 NaN）
            items = _clean_nan(items)
            return jsonify(_with_meta({"symbol": symbol, "items": items, "count": len(items)}, resp)), 200
        return jsonify({"symbol": symbol, "items": [], "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("fundamentals failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/f10")
def get_f10() -> tuple[Response, int]:
    """GET /api/v1/f10?symbol=600519.SH"""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    try:
        router = _router()
        if not router:
            return jsonify({"error": "data router not available", "status": 503}), 503
        resp = router.get_f10(symbol)
        if resp.status == "ok" and resp.data:
            return jsonify(_with_meta({"symbol": symbol, "f10": resp.data}, resp)), 200
        return jsonify({"error": resp.error_message or "no f10 data"}), 404
    except Exception as exc:
        logger.warning("f10 failed for %s: %s", symbol, exc)
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
    limit = _int_param("limit", 20)
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
        results = loader.load_all(symbols, kline_start=start, kline_end=end, interval=interval)
        return jsonify({"results": results, "status": "ok"}), 200
    except Exception as exc:
        logger.warning("Refresh all failed: %s", exc)
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/data/jobs", methods=["GET"])
def list_data_jobs() -> tuple[Response, int]:
    """GET /api/v1/data/jobs — list in-process data jobs."""
    return jsonify({"jobs": [job.to_dict() for job in _jobs().list()]}), 200


@bp.route("/data/jobs/<job_id>", methods=["GET"])
def get_data_job(job_id: str) -> tuple[Response, int]:
    """GET /api/v1/data/jobs/<job_id> — inspect refresh/import progress."""
    job = _jobs().get(job_id)
    if job is None:
        return jsonify({"error": "job not found", "status": 404}), 404
    return jsonify({"job": job.to_dict()}), 200


@bp.route("/data/jobs/refresh", methods=["POST"])
def create_refresh_job() -> tuple[Response, int]:
    """POST /api/v1/data/jobs/refresh

    JSON:
      {
        "symbols": ["600519.SH"] | "all",  # default: all known local symbols
        "intervals": ["1d", "5m"],         # or "interval": "1d"
        "start": "2024-01-01",
        "end": "2026-06-28",
        "include_valuation": true
      }
    """
    body = request.get_json(force=True, silent=True) or {}
    symbols = _known_symbols_or_payload(body)
    if not symbols:
        return jsonify({
            "error": "symbols are required when the local database has no known symbols",
            "status": 400,
        }), 400
    intervals = body.get("intervals")
    if intervals is None:
        intervals = [body.get("interval", "1d")]
    intervals = [str(item) for item in _as_list(intervals) if item]
    start = body.get("start")
    end = body.get("end")
    include_valuation = bool(body.get("include_valuation", False))
    total = len(symbols) * len(intervals) + (len(symbols) if include_valuation else 0)

    store = _store()
    router = _router()

    def run(update: Any) -> dict[str, Any]:
        from tradingagents.astock.store.loader import KlineLoader, ValuationLoader

        kline_loader = KlineLoader(store, router)
        valuation_loader = ValuationLoader(store, router)
        completed = 0
        results: dict[str, Any] = {"kline": {}, "valuations": {}}
        for symbol in symbols:
            for interval in intervals:
                update(message=f"refreshing kline {symbol} {interval}", completed=completed)
                count = kline_loader.load(symbol, start=start, end=end, interval=interval)
                results["kline"][f"{symbol}:{interval}"] = count
                completed += 1
                update(completed=completed, result=results)
            if include_valuation:
                update(message=f"refreshing valuation {symbol}", completed=completed)
                count = valuation_loader.load(symbol, start=start, end=end)
                results["valuations"][symbol] = count
                completed += 1
                update(completed=completed, result=results)
        return results

    job = _jobs().submit(
        "refresh",
        run,
        total=total,
        message="queued refresh",
    )
    return jsonify({"job": job.to_dict()}), 202


@bp.route("/data/jobs/import-database", methods=["POST"])
def create_database_import_job() -> tuple[Response, int]:
    """POST /api/v1/data/jobs/import-database — import from DuckDB/SQLite."""
    body = request.get_json(force=True, silent=True) or {}
    source_db_path = body.get("source_db_path") or body.get("db_path")
    source_table = body.get("source_table")
    target_table = body.get("target_table") or source_table
    if not source_db_path or not source_table or not target_table:
        return jsonify({
            "error": "source_db_path, source_table and target_table are required",
            "status": 400,
        }), 400
    store = _store()

    def run(update: Any) -> dict[str, Any]:
        update(message=f"importing {source_table} -> {target_table}", completed=0)
        count = store.import_from_database(
            source_db_path=source_db_path,
            source_table=str(source_table),
            target_table=str(target_table),
            source_type=str(body.get("source_type", "auto")),
            symbol=body.get("symbol"),
            start=body.get("start"),
            end=body.get("end"),
            symbol_column=str(body.get("symbol_column", "symbol")),
            date_column=str(body.get("date_column", "trade_date")),
        )
        update(completed=1)
        return {"rows_imported": count, "target_table": target_table}

    job = _jobs().submit("database_import", run, total=1, message="queued import")
    return jsonify({"job": job.to_dict()}), 202


@bp.route("/data/manual/<table_name>", methods=["POST"])
def manual_insert_rows(table_name: str) -> tuple[Response, int]:
    """POST /api/v1/data/manual/<table_name> — insert one or many rows.

    Body accepts either ``{"record": {...}}`` or ``{"records": [{...}]}``.
    Top-level ``symbol``, ``date``/``trade_date``, ``interval`` and ``source``
    are applied as defaults to each row when missing.
    """
    body = request.get_json(force=True, silent=True) or {}
    try:
        records = _records_from_body(body)
    except ValueError as exc:
        return jsonify({"error": str(exc), "status": 400}), 400
    if not records:
        return jsonify({"error": "record or records is required", "status": 400}), 400

    symbol = body.get("symbol")
    trade_date = body.get("trade_date") or body.get("date")
    interval = body.get("interval")
    source = body.get("source")
    for row in records:
        if symbol and "symbol" not in row:
            row["symbol"] = symbol
        if trade_date and "trade_date" not in row and "date" not in row:
            row["trade_date"] = trade_date
        if interval and "interval" not in row:
            row["interval"] = interval
        if source and "source" not in row:
            row["source"] = source
    try:
        _validate_manual_rows(table_name, records)
        count = _store().insert_table_rows(table_name, records)
        return jsonify({
            "table": table_name,
            "rows_inserted": count,
            "status": "ok",
        }), 200
    except Exception as exc:
        logger.warning("Manual insert failed for %s: %s", table_name, exc)
        return _insert_error_response(exc)


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
