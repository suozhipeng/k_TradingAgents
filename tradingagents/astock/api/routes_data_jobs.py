"""Data job management API routes — async job CRUD.

Routes: /data/jobs*, /data/import-database
"""

from __future__ import annotations

import logging
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
    total = len(symbols) * len(intervals) + (len(symbols) if include_valuation else 0)

    store = get_store()
    router = current_app.config.get("DATA_FACADE")

    def run(update: Any) -> dict[str, Any]:
        from tradingagents.astock.store.loader import KlineLoader, ValuationLoader
        kline_loader = KlineLoader(store, router)
        valuation_loader = ValuationLoader(store, router)
        completed = 0
        results: dict[str, Any] = {"mode": mode, "kline": {}, "valuations": {}}
        for symbol in symbols:
            for interval in intervals:
                update(message=f"refreshing kline {symbol} {interval}", completed=completed)
                requested_start = _latest_kline_start(store, symbol, interval) if mode == "incremental" else start
                count = kline_loader.load(symbol, start=requested_start, end=end, interval=interval)
                results["kline"][f"{symbol}:{interval}"] = {
                    "requested_start": requested_start,
                    "requested_end": end,
                    "rows_upserted": count,
                }
                completed += 1
                update(completed=completed, result=results)
            if include_valuation:
                update(message=f"refreshing valuation {symbol}", completed=completed)
                count = valuation_loader.load(symbol, start=start, end=end)
                results["valuations"][symbol] = count
                completed += 1
                update(completed=completed, result=results)
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
