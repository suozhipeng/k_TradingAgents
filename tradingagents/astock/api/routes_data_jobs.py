"""Data job management API routes — async job CRUD.

Routes: /data/jobs*, /data/import-database
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request
from ._helpers import _as_bool, get_store

bp = Blueprint("data_jobs", __name__)
logger = logging.getLogger(__name__)


def _jobs() -> Any:
    return current_app.config["DATA_JOB_MANAGER"]




def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _known_symbols_or_payload(body: dict[str, Any]) -> list[str]:
    symbols = body.get("symbols")
    if symbols in (None, "", "all"):
        return get_store().list_symbols()
    if isinstance(symbols, str):
        return [symbols]
    return [str(item) for item in symbols if item]


def _latest_kline_start(store: Any, symbol: str, interval: str) -> str | None:
    """Return a server-derived one-bar overlap start for an idempotent refresh.

    Overlap window is computed dynamically per interval to avoid unnecessary
    API requests while guaranteeing no missed bars:
      - minute-level (e.g. 5m):  -interval * 2
      - hourly (e.g. 60m):       -1 day
      - daily and above:         -1 day
    """
    bars = store.query_kline(symbol, interval=interval, limit=1)
    if bars is None or bars.empty or "bar_time" not in bars.columns:
        return None
    value = bars.iloc[-1]["bar_time"]
    if not value:
        return None
    try:
        timestamp = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
        if isinstance(timestamp, datetime):
            # Minute-level intervals: overlap = interval * 2
            if interval.endswith("m") and interval != "1mo":
                minutes = int(interval[:-1])
                return (timestamp - timedelta(minutes=minutes * 2)).isoformat()
            # Daily and higher: overlap = 1 day
            return (timestamp - timedelta(days=1)).date().isoformat()
    except (TypeError, ValueError):
        pass
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


# ---------------------------------------------------------------------------
# Job CRUD
# ---------------------------------------------------------------------------


@bp.route("/data/refresh/options", methods=["GET"])
def refresh_options() -> tuple[Response, int]:
    """Return the server-owned contract for the Data Hub refresh form."""
    from tradingagents.astock.store.schema_defs import SUPPORTED_KLINE_INTERVALS

    return jsonify({
        "symbols": get_store().list_symbols(),
        "intervals": sorted(SUPPORTED_KLINE_INTERVALS),
        "default_interval": "1d",
        "modes": ["incremental", "range"],
        "include_valuation": True,
        "default_max_concurrency": min(5, max(1, int(os.getenv("ASTOCK_NETWORK_MAX_CONCURRENCY", "5")))),
        "max_concurrency_limit": 5,
        "default_timeout_seconds": max(1, int(float(os.getenv("ASTOCK_JOB_TIMEOUT_SECONDS", "300")))),
        "timeout_retries": {"kline": 3, "valuation": 2, "maximum": 3},
    }), 200


@bp.route("/data/jobs", methods=["GET"])
def list_data_jobs() -> tuple[Response, int]:
    return jsonify({"jobs": [job.to_dict() for job in _jobs().list()]}), 200


@bp.route("/data/jobs/<job_id>", methods=["GET"])
def get_data_job(job_id: str) -> tuple[Response, int]:
    job = _jobs().get(job_id)
    if job is None:
        return jsonify({"error": "job not found", "status": 404}), 404
    return jsonify({"job": job.to_dict()}), 200


@bp.route("/data/jobs/refresh", methods=["POST"])
def create_refresh_job() -> tuple[Response, int]:
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
    if not intervals:
        return jsonify({"error": "at least one interval is required", "status": 400}), 400
    from tradingagents.astock.store.schema_defs import SUPPORTED_KLINE_INTERVALS
    invalid_intervals = sorted(set(intervals) - set(SUPPORTED_KLINE_INTERVALS))
    if invalid_intervals:
        return jsonify({"error": f"unsupported intervals: {', '.join(invalid_intervals)}", "status": 400}), 400
    mode = str(body.get("mode", "range")).lower()
    if mode not in {"incremental", "range"}:
        return jsonify({"error": "mode must be incremental or range", "status": 400}), 400
    if mode == "incremental" and body.get("start"):
        return jsonify({"error": "start is server-derived in incremental mode", "status": 400}), 400
    start = body.get("start")
    end = body.get("end")
    if start and end and str(start) > str(end):
        return jsonify({"error": "start must not be after end", "status": 400}), 400
    include_valuation = _as_bool(body.get("include_valuation"), False)
    try:
        max_concurrency = int(body.get("max_concurrency", os.getenv("ASTOCK_NETWORK_MAX_CONCURRENCY", "5")))
    except (TypeError, ValueError):
        return jsonify({"error": "max_concurrency must be an integer", "status": 400}), 400
    if not 1 <= max_concurrency <= 5:
        return jsonify({"error": "max_concurrency must be between 1 and 5", "status": 400}), 400
    try:
        timeout_seconds = float(body.get("timeout_seconds", os.getenv("ASTOCK_JOB_TIMEOUT_SECONDS", "300")))
    except (TypeError, ValueError):
        return jsonify({"error": "timeout_seconds must be a number", "status": 400}), 400
    if not 1 <= timeout_seconds <= 3600:
        return jsonify({"error": "timeout_seconds must be between 1 and 3600", "status": 400}), 400
    try:
        timeout_retries = int(body.get("timeout_retries", os.getenv("ASTOCK_KLINE_TIMEOUT_RETRIES", "3")))
    except (TypeError, ValueError):
        return jsonify({"error": "timeout_retries must be an integer", "status": 400}), 400
    if not 0 <= timeout_retries <= 3:
        return jsonify({"error": "timeout_retries must be between 0 and 3", "status": 400}), 400
    # Deduplicate at the API boundary: duplicate symbols/intervals must not
    # create repeated provider requests or duplicate DB writes.
    symbols = list(dict.fromkeys(symbols))
    intervals = list(dict.fromkeys(intervals))
    total = len(symbols) * len(intervals) + (len(symbols) if include_valuation else 0)

    store = get_store()
    router = current_app.config.get("DATA_FACADE")

    def run(update: Any) -> dict[str, Any]:
        from tradingagents.astock.store.loader import BatchLoader, ValuationLoader, run_with_timeout_retries, serialize_load_error
        valuation_loader = ValuationLoader(store, router)
        batch_loader = BatchLoader(store, router, max_workers=max_concurrency)
        completed = 0
        results: dict[str, Any] = {"mode": mode, "kline": {}, "valuations": {}, "failure_count": 0}
        kline_requests = [
            {
                "symbol": symbol,
                "interval": interval,
                "start": _latest_kline_start(store, symbol, interval) if mode == "incremental" else start,
                "end": end,
            }
            for symbol in symbols for interval in intervals
        ]
        use_concurrent = len(kline_requests) > 3
        update(message="refreshing kline data", completed=completed)
        results["kline"] = batch_loader.load_kline_requests(
            kline_requests, concurrent=use_concurrent, timeout_seconds=timeout_seconds
            , timeout_retries=timeout_retries
        )
        completed += len(kline_requests)
        results["failure_count"] += sum(1 for item in results["kline"].values() if item["status"] == "failed")
        update(completed=completed, result=results)

        for symbol in symbols:
            if include_valuation:
                update(message=f"refreshing valuation {symbol}", completed=completed)
                try:
                    count, retry_count = run_with_timeout_retries(
                        lambda: valuation_loader.load(symbol, start=start, end=end),
                        retries=int(os.getenv("ASTOCK_VALUATION_TIMEOUT_RETRIES", "2")),
                        deadline=time.monotonic() + timeout_seconds,
                    )
                    results["valuations"][symbol] = {"status": "succeeded", "rows_upserted": count, "retry_count": retry_count}
                except Exception as exc:
                    results["valuations"][symbol] = {"status": "failed", "rows_upserted": 0, "retry_count": getattr(exc, "retry_count", 0), "error": serialize_load_error(exc)}
                    results["failure_count"] += 1
                completed += 1
                update(completed=completed, result=results)
        if results["failure_count"]:
            results["message"] = f"completed with {results['failure_count']} item failure(s)"
        results["max_concurrency"] = max_concurrency
        results["timeout_seconds"] = timeout_seconds
        results["timeout_retries"] = timeout_retries
        return results

    job = _jobs().submit("refresh", run, total=total, message="queued refresh")
    return jsonify({"job": job.to_dict()}), 202


@bp.route("/data/jobs/import-database", methods=["POST"])
def create_database_import_job() -> tuple[Response, int]:
    body = request.get_json(force=True, silent=True) or {}
    source_db_path = body.get("source_db_path") or body.get("db_path")
    source_table = body.get("source_table")
    target_table = body.get("target_table") or source_table
    if not source_db_path or not source_table or not target_table:
        return jsonify({
            "error": "source_db_path, source_table and target_table are required",
            "status": 400,
        }), 400
    store = get_store()

    def run(update: Any) -> dict[str, Any]:
        update(message=f"importing {source_table} -> {target_table}", completed=0)
        count = store.import_from_database(
            source_db_path=source_db_path, source_table=str(source_table),
            target_table=str(target_table), source_type=str(body.get("source_type", "auto")),
            symbol=body.get("symbol"), start=body.get("start"), end=body.get("end"),
            symbol_column=str(body.get("symbol_column", "symbol")),
            date_column=str(body.get("date_column", "trade_date")),
        )
        update(completed=1)
        return {"rows_imported": count, "target_table": target_table}

    job = _jobs().submit("database_import", run, total=1, message="queued import")
    return jsonify({"job": job.to_dict()}), 202
