"""Data query API routes — read-only data from the DuckDB AStockStore.

Routes: /kline, /valuation, /orderbook, /news, /news/live, /news/stock,
        /trade_tape, /research, /research/pdf, /research/expectation,
        /research/search, /fundamentals, /f10, /announcements, /store/stats

All routes return JSON. Error responses follow ``{"error": ..., "status": N}``.
"""

from __future__ import annotations

import logging
import math
import threading
from concurrent.futures import Future, TimeoutError as FuturesTimeoutError
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from flask import Blueprint, Response, current_app, jsonify, request

from .envelope import error_response, success_response

from ._helpers import _as_bool, df_to_json, get_store, sanitise_records
from tradingagents.astock.time_utils import market_today

bp = Blueprint("market_data_query", __name__)
logger = logging.getLogger(__name__)

# Coalesce concurrent refreshes for the same symbol.  A chart page can issue
# multiple K-line requests while it loads; without this guard each one would
# independently hit the upstream provider and contend for the same DuckDB
# write lock.
_daily_refresh_lock = threading.Lock()
_daily_refresh_flights: dict[str, Future[dict[str, Any]]] = {}
_permanent_write_lock = threading.Lock()


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


def _refresh_daily_kline_incrementally(symbol: str, *, force: bool = False) -> dict[str, Any]:
    """Refresh a symbol's daily bars without letting a provider stall a query.

    The refresh begins at the newest locally stored daily bar so provider data
    is upserted incrementally (including a replacement for today's partial
    bar).  ``BatchLoader`` owns a bounded worker and reports timeout/failure
    per request; consequently the API can still return the last good local
    data if one upstream module is slow or unavailable.
    """
    if not force and not current_app.config.get("ASTOCK_AUTO_REFRESH_DAILY_KLINE", True):
        return {"status": "disabled", "rows_upserted": 0}

    timeout = float(current_app.config.get("ASTOCK_DAILY_KLINE_REFRESH_TIMEOUT_SECONDS", 8))
    with _daily_refresh_lock:
        existing = _daily_refresh_flights.get(symbol)
        if existing is None:
            flight: Future[dict[str, Any]] = Future()
            _daily_refresh_flights[symbol] = flight
            is_leader = True
        else:
            flight = existing
            is_leader = False

    if not is_leader:
        try:
            result = dict(flight.result(timeout=max(0.1, timeout)))
            result["coalesced"] = True
            return result
        except FuturesTimeoutError:
            return {
                "status": "pending", "rows_upserted": 0, "mode": "incremental",
                "coalesced": True, "reason": "another refresh is still running",
            }

    try:
        result = _perform_daily_kline_incremental_refresh(symbol, timeout)
        flight.set_result(result)
        return result
    except Exception as exc:
        logger.warning("daily K-line refresh failed for %s: %s", symbol, exc)
        result = {"status": "failed", "rows_upserted": 0, "mode": "incremental", "error": {"code": "refresh_failed"}}
        flight.set_result(result)
        return result
    finally:
        with _daily_refresh_lock:
            _daily_refresh_flights.pop(symbol, None)


def _perform_daily_kline_incremental_refresh(symbol: str, timeout: float) -> dict[str, Any]:
    """Perform the leader side of a coalesced daily K-line refresh."""
    router = _router()
    if router is None:
        return {"status": "unavailable", "rows_upserted": 0, "reason": "data router not available"}

    store = get_store()
    start = None
    try:
        latest = store.query_kline(symbol, interval="1d", limit=1)
        if not latest.empty and "bar_time" in latest.columns:
            value = latest.iloc[-1]["bar_time"]
            start = pd.Timestamp(value).date().isoformat()
    except Exception as exc:
        logger.warning("could not determine local K-line watermark for %s: %s", symbol, exc)

    try:
        from tradingagents.astock.store.loader import BatchLoader

        permanent = None
        if current_app.config.get("ASTOCK_PERMANENT_KLINE_ENABLED", True):
            from tradingagents.astock.store.permanent_kline import get_permanent_kline_store
            permanent = get_permanent_kline_store(
                current_app.config.get("ASTOCK_PERMANENT_KLINE_DB_PATH", "kline/kline.duckdb")
            )
        result = BatchLoader(store, router, max_workers=1, permanent_store=permanent).load_kline_requests(
            [{"symbol": symbol, "start": start, "interval": "1d"}],
            timeout_seconds=timeout,
            timeout_retries=0,
        )[f"{symbol}:1d"]
        result["mode"] = "incremental"
        result["permanent_store"] = _mirror_kline_to_permanent(store, symbol, "1d", start)
        result["intraday_refresh"] = _refresh_intraday_for_current_daily_bar(
            store, router, symbol, timeout
        )
        return result
    except Exception as exc:
        logger.warning("daily K-line refresh failed for %s: %s", symbol, exc)
        return {"status": "failed", "rows_upserted": 0, "mode": "incremental", "error": {"code": "refresh_failed"}}


def _refresh_intraday_for_current_daily_bar(
    store: Any, router: Any, symbol: str, daily_timeout: float
) -> dict[str, Any]:
    """Cache intraday bars only when the latest stored daily bar is today."""
    if not current_app.config.get("ASTOCK_AUTO_REFRESH_INTRADAY_KLINE", True):
        return {"status": "disabled", "rows_upserted": 0}
    try:
        latest = store.query_kline(symbol, interval="1d", limit=1)
        if latest.empty or "bar_time" not in latest.columns:
            return {"status": "skipped", "rows_upserted": 0, "reason": "no daily bar"}
        latest_day = pd.Timestamp(latest.iloc[-1]["bar_time"]).date()
        if latest_day != market_today():
            return {"status": "skipped", "rows_upserted": 0, "reason": "latest daily bar is not today"}

        from tradingagents.astock.store.loader import BatchLoader

        interval = str(current_app.config.get("ASTOCK_INTRADAY_KLINE_INTERVAL", "5m"))
        timeout = min(
            max(1.0, float(current_app.config.get("ASTOCK_INTRADAY_KLINE_REFRESH_TIMEOUT_SECONDS", 5))),
            max(1.0, daily_timeout),
        )
        permanent = None
        if current_app.config.get("ASTOCK_PERMANENT_KLINE_ENABLED", True):
            from tradingagents.astock.store.permanent_kline import get_permanent_kline_store
            permanent = get_permanent_kline_store(
                current_app.config.get("ASTOCK_PERMANENT_KLINE_DB_PATH", "kline/kline.duckdb")
            )
        result = BatchLoader(store, router, max_workers=1, permanent_store=permanent).load_kline_requests(
            [{"symbol": symbol, "start": latest_day.isoformat(), "interval": interval}],
            timeout_seconds=timeout,
            timeout_retries=0,
        )[f"{symbol}:{interval}"]
        result["mode"] = "current_day_intraday"
        result["permanent_store"] = _mirror_kline_to_permanent(store, symbol, interval, latest_day.isoformat())
        return result
    except Exception as exc:
        logger.warning("intraday K-line refresh failed for %s: %s", symbol, exc)
        return {"status": "failed", "rows_upserted": 0, "error": {"code": "refresh_failed"}}


def _mirror_kline_to_permanent(store: Any, symbol: str, interval: str, start: str | None) -> dict[str, Any]:
    """Synchronize a K-line series into the permanent local warehouse.

    The warehouse watermark, rather than the request's hot-store watermark,
    controls the copy range.  This makes its first creation a full local
    backfill and lets it recover automatically if an earlier mirror failed.
    """
    if not current_app.config.get("ASTOCK_PERMANENT_KLINE_ENABLED", True):
        return {"status": "disabled", "rows_upserted": 0}
    try:
        configured = str(current_app.config.get("ASTOCK_PERMANENT_KLINE_DB_PATH", "kline/kline.duckdb"))
        from tradingagents.astock.store.permanent_kline import get_permanent_kline_store

        permanent = get_permanent_kline_store(configured)
        path = Path(configured)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[3] / path
        # DuckDB permits concurrent reads, while refreshes for separate symbols
        # can otherwise overlap writes on this long-lived local connection.
        with _permanent_write_lock:
            latest = permanent.query_kline(symbol, interval=interval, limit=1)
            mirror_start = None
            if not latest.empty and "bar_time" in latest.columns:
                mirror_start = pd.Timestamp(latest.iloc[-1]["bar_time"]).isoformat()
            df = store.query_kline(symbol, interval=interval, start=mirror_start)
            rows = permanent.insert_kline(symbol, df, interval=interval, source="incremental_mirror") if not df.empty else 0
        return {
            "status": "ok", "rows_upserted": rows, "path": str(path),
            "mode": "full_local_backfill" if mirror_start is None else "incremental",
        }
    except Exception as exc:
        logger.warning("permanent K-line mirror failed for %s %s: %s", symbol, interval, exc)
        return {
            "status": "failed", "rows_upserted": 0,
            "error": {"code": "permanent_store_sync_failed"},
        }


def _query_local_kline(
    store: Any, symbol: str, *, start: str | None, end: str | None,
    interval: str, limit: int | None, include_cold: bool,
) -> tuple[pd.DataFrame, str]:
    """Read the hot cache first, then the permanent local warehouse.

    Both stores are local-only.  This gives Web requests a durable local
    fallback without accidentally invoking a provider; the caller alone
    decides whether an explicit refresh should be requested afterwards.
    """
    df = store.query_kline(
        symbol, start=start, end=end, interval=interval,
        limit=limit, include_cold=include_cold,
    )
    if not df.empty or not current_app.config.get("ASTOCK_PERMANENT_KLINE_ENABLED", True):
        return df, "hot"
    try:
        from tradingagents.astock.store.permanent_kline import get_permanent_kline_store

        permanent = get_permanent_kline_store(
            current_app.config.get("ASTOCK_PERMANENT_KLINE_DB_PATH", "kline/kline.duckdb")
        )
        if permanent is store or permanent is getattr(store, "_store", None):
            return df, "hot"
        return permanent.query_kline(
            symbol, start=start, end=end, interval=interval,
            limit=limit, include_cold=include_cold,
        ), "permanent"
    except Exception as exc:
        logger.warning("permanent local K-line query failed for %s: %s", symbol, exc)
        return df, "hot"


# ---------------------------------------------------------------------------
# Kline bars
# ---------------------------------------------------------------------------


@bp.route("/market/kline")
def get_kline() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)
    start = request.args.get("start")
    end = request.args.get("end")
    interval = request.args.get("interval", "1d")
    include_cold = request.args.get("include_cold", "0").lower() in ("1", "true", "yes")
    limit = _int_param("limit", 500, max_val=5000)
    try:
        refresh_requested = _as_bool(
            request.args.get("refresh"),
            current_app.config.get("ASTOCK_AUTO_REFRESH_DAILY_KLINE", False),
        )
        daily_refresh = (
            _refresh_daily_kline_incrementally(symbol, force=True)
            if refresh_requested else {"status": "not_requested", "rows_upserted": 0}
        )
        store = get_store()
        store_limit = limit + 1 if limit > 0 else None
        df, local_source = _query_local_kline(
            store, symbol, start=start, end=end, interval=interval,
            limit=store_limit, include_cold=include_cold,
        )
        bars = df_to_json(df)

        refresh_status = str(daily_refresh.get("status", "not_requested"))
        if not bars and refresh_status in {"failed", "unavailable", "pending"}:
            return error_response(
                "market_data_unavailable", 503,
                code="market_data_unavailable",
            )

        # An empty local repository is a normal first-run state, not a fake
        # successful data response.  Keep it as a 200 so charts can render an
        # empty state, but make the required next action machine-readable.
        data_state = "ready" if bars else "not_initialized"

        has_more = False
        if limit > 0 and len(bars) > limit:
            bars = bars[-limit:]
            has_more = True

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
            "data_state": data_state, "local_source": local_source,
            "daily_refresh": daily_refresh,
        }), 200
    except Exception as exc:
        return error_response(str(exc), 500)


# ---------------------------------------------------------------------------
# Valuation
# ---------------------------------------------------------------------------


@bp.route("/market/valuation")
def get_valuation() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)
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
                                df_live["trade_date"] = market_today()
                            store.insert_valuations(symbol, df_live, source=source_str)
                            df = store.query_valuations(symbol)
                            valuations = df_to_json(df)
                            if limit > 0:
                                valuations = valuations[-limit:]
                except Exception:
                    logger.warning("live valuation fetch failed for %s", symbol, exc_info=True)

        return jsonify({"symbol": symbol, "valuations": valuations}), 200
    except Exception as exc:
        return error_response(str(exc), 500)


# ---------------------------------------------------------------------------
# Order book
# ---------------------------------------------------------------------------


@bp.route("/market/orderbook")
def get_orderbook() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)
    try:
        df = get_store().query_order_book(symbol)
        return jsonify({"symbol": symbol, "snapshots": df_to_json(df)}), 200
    except Exception as exc:
        return error_response(str(exc), 500)


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------


@bp.route("/market/news")
def get_news() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)
    limit = _int_param("limit", 20)
    try:
        df = get_store().query_news_items(symbol)
        items = df_to_json(df)
        return jsonify({"symbol": symbol, "news": items[-limit:] if limit > 0 else items}), 200
    except Exception as exc:
        return error_response(str(exc), 500)


@bp.route("/market/news/live")
def get_news_live() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)
    limit = _int_param("limit", 20)
    news_type = request.args.get("type", "flash")
    news_source = request.args.get("source", "em")
    try:
        router = _router()
        if not router:
            return error_response("data router not available", 503)
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
        return error_response(str(exc), 500)


@bp.route("/market/news/stock")
def get_stock_news_route() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)
    limit = _int_param("limit", 10)
    try:
        router = _router()
        if not router:
            return error_response("data router not available", 503)
        resp = router.get_stock_news(symbol, limit=limit)
        if resp.status == "ok" and resp.data:
            return jsonify(_with_meta({
                "symbol": symbol, "items": resp.data.get("items", []),
                "count": resp.data.get("count", 0),
            }, resp)), 200
        return jsonify({"symbol": symbol, "items": [], "count": 0, "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("stock news failed for %s: %s", symbol, exc)
        return error_response(str(exc), 500)


# ---------------------------------------------------------------------------
# Trade tape
# ---------------------------------------------------------------------------


@bp.route("/market/trade_tape")
def get_trade_tape() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)
    limit = _int_param("limit", 50)
    try:
        router = _router()
        if not router:
            return error_response("data router not available", 503)
        resp = router.get_trade_tape(symbol, limit=limit)
        if resp.status == "ok" and resp.data:
            return jsonify(_with_meta({
                "symbol": symbol, "ticks": resp.data.get("items", []), "count": resp.data.get("count", 0)
            }, resp)), 200
        return jsonify({"symbol": symbol, "ticks": [], "count": 0, "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("trade_tape failed for %s: %s", symbol, exc)
        return error_response(str(exc), 500)


# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------


@bp.route("/market/research")
def get_research() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)
    limit = _int_param("limit", 20)
    try:
        df = get_store().query_research_reports(symbol)
        items = df_to_json(df)
        return jsonify({"symbol": symbol, "reports": items[-limit:] if limit > 0 else items}), 200
    except Exception as exc:
        return error_response(str(exc), 500)


@bp.route("/market/research/pdf")
def get_research_pdf() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)
    title = request.args.get("title", "")
    try:
        router = _router()
        if not router:
            return error_response("data router not available", 503)
        kwargs = {"title": title} if title else {}
        resp = router.download_research_pdf(symbol, **kwargs)
        if resp.status == "ok" and resp.data:
            # Akshare adapter returns PDF metadata (url, title, etc.), not binary data
            return jsonify({
                "symbol": symbol,
                "pdf_metadata": resp.data,
                "note": "PDF metadata returned; actual PDF download requires pdf_url from metadata",
            }), 200
        return error_response(resp.error_message or "no research pdf", 404)
    except Exception as exc:
        logger.warning("research pdf failed for %s: %s", symbol, exc)
        return error_response(str(exc), 500)


@bp.route("/market/research/expectation")
def get_research_expectation() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)
    limit = _int_param("limit", 10)
    try:
        router = _router()
        if not router:
            return error_response("data router not available", 503)
        resp = router.get_institution_expectation(symbol, limit=limit)
        if resp.status == "ok" and resp.data:
            return jsonify(_with_meta({
                "symbol": symbol, "items": resp.data.get("items", []),
                "count": resp.data.get("count", 0),
            }, resp)), 200
        return jsonify({"symbol": symbol, "items": [], "count": 0, "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("research expectation failed for %s: %s", symbol, exc)
        return error_response(str(exc), 500)


@bp.route("/market/research/search")
def get_research_search() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    query = request.args.get("query", "")
    if not symbol:
        return error_response("symbol is required", 400)
    if not query:
        return error_response("query is required", 400)
    limit = _int_param("limit", 10)
    try:
        router = _router()
        if not router:
            return error_response("data router not available", 503)
        resp = router.search_research(symbol, query=query, limit=limit)
        if resp.status == "ok" and resp.data:
            return jsonify(_with_meta({
                "symbol": symbol, "query": query, "items": resp.data.get("items", []),
                "count": resp.data.get("count", 0),
            }, resp)), 200
        return jsonify({"symbol": symbol, "query": query, "items": [], "count": 0, "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("research search failed for %s: %s", symbol, exc)
        return error_response(str(exc), 500)


# ---------------------------------------------------------------------------
# Fundamentals / F10
# ---------------------------------------------------------------------------


@bp.route("/market/fundamentals")
def get_fundamentals() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)
    limit = _int_param("limit", 10)
    try:
        router = _router()
        if not router:
            return error_response("data router not available", 503)
        resp = router.get_fundamentals(symbol, limit=limit)
        if resp.status == "ok" and resp.data:
            items = resp.data.get("items", [])
            sanitise_records(items)
            return jsonify(_with_meta({"symbol": symbol, "items": items, "count": len(items)}, resp)), 200
        return jsonify({"symbol": symbol, "items": [], "note": resp.error_message or "no data"}), 200
    except Exception as exc:
        logger.warning("fundamentals failed for %s: %s", symbol, exc)
        return error_response(str(exc), 500)


@bp.route("/market/f10")
def get_f10() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)
    try:
        router = _router()
        if not router:
            return error_response("data router not available", 503)
        resp = router.get_f10(symbol)
        if resp.status == "ok" and resp.data:
            return jsonify(_with_meta({"symbol": symbol, "f10": resp.data}, resp)), 200
        return error_response(resp.error_message or "no f10 data", 404)
    except Exception as exc:
        logger.warning("f10 failed for %s: %s", symbol, exc)
        return error_response(str(exc), 500)


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------


@bp.route("/market/announcements")
def get_announcements() -> tuple[Response, int]:
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)
    limit = _int_param("limit", 20)
    try:
        df = get_store().query_announcements(symbol)
        items = df_to_json(df)
        return jsonify({"symbol": symbol, "announcements": items[:limit]}), 200
    except Exception as exc:
        return error_response(str(exc), 500)


# ---------------------------------------------------------------------------
# Store stats
# ---------------------------------------------------------------------------


@bp.route("/market/store/stats")
def get_store_stats() -> tuple[Response, int]:
    try:
        stats = get_store().get_table_stats()
        return jsonify({"stats": stats}), 200
    except Exception as exc:
        return error_response(str(exc), 500)
