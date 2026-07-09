"""Data job management API routes — async job CRUD.

Routes: /data/jobs*, /data/import-database
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request
from ._helpers import get_store

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


# ---------------------------------------------------------------------------
# Job CRUD
# ---------------------------------------------------------------------------


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
    start = body.get("start")
    end = body.get("end")
    include_valuation = bool(body.get("include_valuation", False))
    total = len(symbols) * len(intervals) + (len(symbols) if include_valuation else 0)

    store = get_store()
    router = current_app.config.get("DATA_FACADE")

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
