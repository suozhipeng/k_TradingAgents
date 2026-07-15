"""Data ingestion API routes — write operations (refresh, manual insert).

Routes: /data/refresh/*, /data/manual/<table>
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

from .envelope import error_response, success_response
from ._helpers import get_store

bp = Blueprint("data_ingest", __name__)
logger = logging.getLogger(__name__)


def _permanent_kline_store() -> Any:
    if not current_app.config.get("ASTOCK_PERMANENT_KLINE_ENABLED", True):
        return None
    from tradingagents.astock.store.permanent_kline import get_permanent_kline_store
    return get_permanent_kline_store(
        current_app.config.get("ASTOCK_PERMANENT_KLINE_DB_PATH", "kline/kline.duckdb")
    )



# ---------------------------------------------------------------------------
# Data refresh
# ---------------------------------------------------------------------------


@bp.route("/data/lifecycle/intraday", methods=["POST"])
def manage_intraday_lifecycle() -> tuple[Response, int]:
    """Preview or explicitly archive old minute K-lines into Parquet.

    ``confirm_delete`` defaults to false, so callers can inspect the exact
    partitions and row counts before any hot-store rows are removed.
    """
    body = request.get_json(force=True, silent=True) or {}
    try:
        retention_days = min(max(int(body.get("retention_days", 180)), 1), 3650)
        archive_dir = str(body.get("archive_dir", "kline/archive"))
        confirm_delete = bool(body.get("confirm_delete", False))
        from tradingagents.astock.store.intraday_lifecycle import archive_intraday_kline
        result = archive_intraday_kline(
            get_store(), retention_days=retention_days, archive_dir=archive_dir,
            delete_hot_rows=confirm_delete,
        )
        result["mode"] = "archive_and_delete" if confirm_delete else "preview"
        return jsonify(result), 200
    except Exception as exc:
        logger.warning("Intraday lifecycle operation failed: %s", exc)
        return error_response("intraday_lifecycle_failed", 500)


@bp.route("/data/maintenance", methods=["POST"])
def maintain_local_databases() -> tuple[Response, int]:
    """Checkpoint and analyze the hot and canonical local DuckDB stores."""
    try:
        stores = [("hot", get_store())]
        if current_app.config.get("ASTOCK_PERMANENT_KLINE_ENABLED", True):
            from tradingagents.astock.store.permanent_kline import get_permanent_kline_store
            permanent = get_permanent_kline_store(
                current_app.config.get("ASTOCK_PERMANENT_KLINE_DB_PATH", "kline/kline.duckdb")
            )
            if permanent is not stores[0][1]:
                stores.append(("permanent", permanent))
        completed: list[str] = []
        for name, store in stores:
            if hasattr(store, "vacuum"):
                store.vacuum()
                completed.append(name)
        return jsonify({"status": "ok", "maintained": completed}), 200
    except Exception as exc:
        logger.warning("Local database maintenance failed: %s", exc)
        return error_response("maintenance_failed", 500)


@bp.route("/data/refresh/kline", methods=["POST"])
def refresh_kline() -> tuple[Response, int]:
    body = request.get_json(force=True, silent=True) or {}
    symbol = body.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)
    start = body.get("start")
    end = body.get("end")
    interval = body.get("interval", "1d")
    try:
        from tradingagents.astock.store.loader import KlineLoader
        store = get_store()
        router = current_app.config.get("DATA_FACADE")
        if not router:
            return error_response("data router not available", 503)
        loader = KlineLoader(store, router, permanent_store=_permanent_kline_store())
        count = loader.load(symbol, start=start, end=end, interval=interval)
        return jsonify({"symbol": symbol, "rows_inserted": count, "status": "ok"}), 200
    except Exception as exc:
        error_msg = str(exc)
        # 提供更有意义的错误信息
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            logger.warning("Refresh kline timed out for %s: %s", symbol, exc)
            return error_response("request_timed_out", 408)
        elif "network" in error_msg.lower() or "connection" in error_msg.lower():
            logger.warning("Refresh kline network error for %s: %s", symbol, exc)
            return error_response("network_error", 503)
        else:
            logger.warning("Refresh kline failed for %s: %s", symbol, exc)
            return error_response("refresh_failed", 500)


@bp.route("/data/refresh/valuation", methods=["POST"])
def refresh_valuation() -> tuple[Response, int]:
    body = request.get_json(force=True, silent=True) or {}
    symbol = body.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)
    try:
        from tradingagents.astock.store.loader import ValuationLoader
        store = get_store()
        router = current_app.config.get("DATA_FACADE")
        if not router:
            return error_response("data router not available", 503)
        loader = ValuationLoader(store, router)
        count = loader.load(symbol)
        return jsonify({"symbol": symbol, "rows_inserted": count, "status": "ok"}), 200
    except Exception as exc:
        error_msg = str(exc)
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            logger.warning("Refresh valuation timed out for %s: %s", symbol, exc)
            return error_response("request_timed_out", 408)
        elif "network" in error_msg.lower() or "connection" in error_msg.lower():
            logger.warning("Refresh valuation network error for %s: %s", symbol, exc)
            return error_response("network_error", 503)
        else:
            logger.warning("Refresh valuation failed for %s: %s", symbol, exc)
            return error_response("refresh_failed", 500)


@bp.route("/data/refresh/all", methods=["POST"])
def refresh_all() -> tuple[Response, int]:
    body = request.get_json(force=True, silent=True) or {}
    symbols = body.get("symbols", [])
    if not symbols:
        return error_response("symbols list is required", 400)
    start = body.get("start")
    end = body.get("end")
    interval = body.get("interval", "1d")
    try:
        from tradingagents.astock.store.loader import BatchLoader
        store = get_store()
        router = current_app.config.get("DATA_FACADE")
        if not router:
            return error_response("data router not available", 503)
        loader = BatchLoader(store, router, permanent_store=_permanent_kline_store())
        results = loader.load_all(symbols, kline_start=start, kline_end=end, interval=interval)
        return jsonify({"results": results, "status": "ok"}), 200
    except Exception as exc:
        error_msg = str(exc)
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            logger.warning("Refresh all timed out: %s", exc)
            return error_response("request_timed_out", 408)
        elif "network" in error_msg.lower() or "connection" in error_msg.lower():
            logger.warning("Refresh all network error: %s", exc)
            return error_response("network_error", 503)
        else:
            logger.warning("Refresh all failed: %s", exc)
            return error_response("refresh_failed", 500)


# ---------------------------------------------------------------------------
# Manual insert
# ---------------------------------------------------------------------------


def _raw_store() -> Any:
    store = get_store()
    return getattr(store, "_store", store)


def _table_columns(table_name: str) -> set[str]:
    raw = _raw_store()
    if hasattr(raw, "_table_columns"):
        return set(raw._table_columns(table_name))
    if hasattr(raw, "table_columns"):
        return set(raw.table_columns(table_name))
    return set()


def _validate_manual_rows(table_name: str, rows: list[dict[str, Any]]) -> None:
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
            {key for row in rows for key in row} - allowed - aliases
        )
        if unknown:
            raise ValueError(f"Unknown field(s) for {table_name}: {', '.join(unknown)}")

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
    from tradingagents.astock.quality import BlockedImportError
    if isinstance(exc, BlockedImportError):
        return jsonify({
            "error": "data_quality_blocked", "message": str(exc),
            "violations": getattr(exc, "violations", []), "status": 422,
        }), 422
    if isinstance(exc, ValueError):
        return error_response("invalid_input", 400, detail=str(exc))
    return error_response("insert_failed", 500, detail=str(exc))


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


@bp.route("/data/manual/<table_name>", methods=["POST"])
def manual_insert_rows(table_name: str) -> tuple[Response, int]:
    body = request.get_json(force=True, silent=True) or {}
    try:
        records = _records_from_body(body)
    except ValueError as exc:
        return error_response(str(exc), 400)
    if not records:
        return error_response("record or records is required", 400)

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
        count = get_store().insert_table_rows(table_name, records)
        return jsonify({"table": table_name, "rows_inserted": count, "status": "ok"}), 200
    except Exception as exc:
        logger.warning("Manual insert failed for %s: %s", table_name, exc)
        return _insert_error_response(exc)
