"""Data query API routes — read-only data from the DuckDB AStockStore.

Routes: /kline, /valuation, /orderbook, /news, /news/live, /news/stock,
        /trade_tape, /research, /research/pdf, /research/expectation,
        /research/search, /fundamentals, /f10, /announcements, /store/stats

All routes return JSON. Error responses follow ``{"error": ..., "status": N}``.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import pandas as pd

from flask import Blueprint, Response, current_app, jsonify, request

from ._helpers import df_to_json, get_store, sanitise_records

bp = Blueprint("market_data_query", __name__)
logger = logging.getLogger(__name__)


def _router() -> Any:
    return current_app.config.get("DATA_FACADE")


def _int_param(name: str, default: int, max_val: int = 1000) -> int:
    raw = request.args.get(name, str(default))
    try:
        val = int(raw)
    except (ValueError, TypeError):
        return default
    return min(max(val, 0), max_val)


def _clean_nan(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nan(v) for v in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


def _with_meta(payload: dict, resp: Any) -> dict:
    if hasattr(resp, "meta") and resp.meta:
        payload["meta"] = dict(resp.meta)
    return payload


# ---------------------------------------------------------------------------
# Kline bars
# ---------------------------------------------------------------------------


@bp.route("/market/kline")
def get_kline() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    start = request.args.get("start")
    end = request.args.get("end")
    interval = request.args.get("interval", "1d")
    limit = _int_param("limit", 500, max_val=5000)
    _FETCH_LIMIT = 400

    try:
        store = get_store()
        store_limit = limit + 1 if limit > 0 else None
        df = store.query_kline(symbol, start=start, end=end, interval=interval, limit=store_limit)
        bars = df_to_json(df)

        has_more = False
        if limit > 0 and len(bars) > limit:
            bars = bars[-limit:]
            has_more = True

        if not bars:
            router = _router()
            if router is not None:
                try:
                    resp = router.get_kline(symbol, interval=interval, limit=_FETCH_LIMIT)
                    if resp.status == "ok" and resp.data:
                        items = resp.data.get("items") or resp.data.get("bars", [])
                        if isinstance(items, list) and len(items) > 0:
                            source_str = resp.source or ""
                            if hasattr(resp, "meta") and resp.meta:
                                source_str = source_str or resp.meta.get("source", "")
                            for item in items:
                                if "trade_date" not in item and "date" in item:
                                    item["trade_date"] = item["date"]
                            df_live = pd.DataFrame(items)
                            date_col_present = any(
                                c in df_live.columns
                                for c in ("trade_date", "date", "datetime", "time")
                            )
                            if date_col_present:
                                store.insert_kline(symbol, df_live, interval=interval, source=source_str)
                            df2 = store.query_kline(symbol, start=start, end=end, interval=interval, limit=store_limit)
                            bars = df_to_json(df2)
                            has_more = False
                            if limit > 0 and len(bars) > limit:
                                bars = bars[-limit:]
                                has_more = True
                except Exception as exc:
                    logger.warning("live kline fetch failed for %s interval=%s: %s", symbol, interval, exc)
                    # 检查是否是超时异常，如果是则提供更友好的错误信息
                    if "timeout" in str(exc).lower() or "timed out" in str(exc).lower():
                        logger.info("kline data not found in store and live fetch timed out, returning empty result")

        bar_count = len(bars)
        date_range: dict[str, str | None] = {"start": None, "end": None}
        if bars:
            first_key = next((k for k in ("bar_time", "trade_date", "date") if k in bars[0]), None)
            if first_key:
                date_range["start"] = bars[0].get(first_key)
                date_range["end"] = bars[-1].get(first_key)

        return jsonify({
            "symbol": symbol, "interval": interval, "bars": bars,
            "count": bar_count, "limit": limit, "has_more": has_more, "range": date_range,
        }), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Valuation
# ---------------------------------------------------------------------------


@bp.route("/market/valuation")
def get_valuation() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    limit = _int_param("limit", 0)
    try:
        store = get_store()
        df = store.query_valuations(symbol)
        valuations = df_to_json(df)
        if limit > 0:
            valuations = valuations[-limit:]

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
                            date_col_present = any(
                                c in df_live.columns for c in ("trade_date", "date")
                            )
                            if not date_col_present:
                                from datetime import date
                                df_live["trade_date"] = date.today()
                            store.insert_valuations(symbol, df_live, source=source_str)
                            df = store.query_valuations(symbol)
                            valuations = df_to_json(df)
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


@bp.route("/market/orderbook")
def get_orderbook() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    try:
        df = get_store().query_order_book(symbol)
        return jsonify({"symbol": symbol, "snapshots": df_to_json(df)}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------


@bp.route("/market/news")
def get_news() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    limit = _int_param("limit", 20)
    try:
        df = get_store().query_news_items(symbol)
        items = df_to_json(df)
        return jsonify({"symbol": symbol, "news": items[-limit:] if limit > 0 else items}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/market/news/live")
def get_news_live() -> tuple[Response, int]:
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
                "symbol": symbol, "type": news_type,
                "source": resp.data.get("source", news_source),
                "items": resp.data.get("items", []),
                "count": resp.data.get("count", 0),
            }), 200
        return jsonify({"symbol": symbol, "type": news_type, "items": [], "count": 0, "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("news live failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/market/news/stock")
def get_stock_news_route() -> tuple[Response, int]:
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
                "symbol": symbol, "items": resp.data.get("items", []),
                "count": resp.data.get("count", 0),
            }, resp)), 200
        return jsonify({"symbol": symbol, "items": [], "count": 0, "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("stock news failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Trade tape
# ---------------------------------------------------------------------------


@bp.route("/market/trade_tape")
def get_trade_tape() -> tuple[Response, int]:
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
            return jsonify(_with_meta({
                "symbol": symbol, "ticks": resp.data.get("items", []), "count": resp.data.get("count", 0)
            }, resp)), 200
        return jsonify({"symbol": symbol, "ticks": [], "count": 0, "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("trade_tape failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------


@bp.route("/market/research")
def get_research() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    limit = _int_param("limit", 20)
    try:
        df = get_store().query_research_reports(symbol)
        items = df_to_json(df)
        return jsonify({"symbol": symbol, "reports": items[-limit:] if limit > 0 else items}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/market/research/pdf")
def get_research_pdf() -> tuple[Response, int]:
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
            # Akshare adapter returns PDF metadata (url, title, etc.), not binary data
            return jsonify({
                "symbol": symbol,
                "pdf_metadata": resp.data,
                "note": "PDF metadata returned; actual PDF download requires pdf_url from metadata",
            }), 200
        return jsonify({"error": resp.error_message or "no research pdf"}), 404
    except Exception as exc:
        logger.warning("research pdf failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/market/research/expectation")
def get_research_expectation() -> tuple[Response, int]:
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
            return jsonify(_with_meta({
                "symbol": symbol, "items": resp.data.get("items", []),
                "count": resp.data.get("count", 0),
            }, resp)), 200
        return jsonify({"symbol": symbol, "items": [], "count": 0, "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("research expectation failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/market/research/search")
def get_research_search() -> tuple[Response, int]:
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
            return jsonify(_with_meta({
                "symbol": symbol, "query": query, "items": resp.data.get("items", []),
                "count": resp.data.get("count", 0),
            }, resp)), 200
        return jsonify({"symbol": symbol, "query": query, "items": [], "count": 0, "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("research search failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Fundamentals / F10
# ---------------------------------------------------------------------------


@bp.route("/market/fundamentals")
def get_fundamentals() -> tuple[Response, int]:
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
            sanitise_records(items)
            return jsonify(_with_meta({"symbol": symbol, "items": items, "count": len(items)}, resp)), 200
        return jsonify({"symbol": symbol, "items": [], "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("fundamentals failed for %s: %s", symbol, exc)
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/market/f10")
def get_f10() -> tuple[Response, int]:
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


@bp.route("/market/announcements")
def get_announcements() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    limit = _int_param("limit", 20)
    try:
        df = get_store().query_announcements(symbol)
        items = df_to_json(df)
        return jsonify({"symbol": symbol, "announcements": items[:limit]}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Store stats
# ---------------------------------------------------------------------------


@bp.route("/market/store/stats")
def get_store_stats() -> tuple[Response, int]:
    try:
        stats = get_store().get_table_stats()
        return jsonify({"stats": stats}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500
