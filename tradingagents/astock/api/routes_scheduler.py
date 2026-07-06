"""Scheduler management API routes (FR-15).

Extracted from routes_sse.py to separate scheduler CRUD from SSE streaming.

Routes: /sse/scheduler/*
"""

from __future__ import annotations

import json
import logging
from typing import Any

from flask import Blueprint, Response, jsonify, request

bp = Blueprint("scheduler", __name__)
logger = logging.getLogger(__name__)


def _get_sched() -> Any:
    from tradingagents.astock.execution.scheduler import get_scheduler
    return get_scheduler()


@bp.route("/sse/scheduler/status")
def scheduler_status() -> tuple[Response, int]:
    sched = _get_sched()
    if sched is None:
        return Response(json.dumps({"status": "not_configured"}), mimetype="application/json"), 200
    return jsonify({
        "running": sched.running, "paused": sched.paused, "enabled": sched.enabled,
        "cycle_count": sched.cycle_count, "next_run_time": sched.next_run_time,
        "interval_minutes": sched._interval_minutes,
    }), 200


@bp.route("/sse/scheduler/start", methods=["POST"])
def scheduler_start() -> tuple[Response, int]:
    sched = _get_sched()
    if sched is None:
        return jsonify({"error": "scheduler not configured", "status": 500}), 500
    sched.start()
    return jsonify({"status": "started", "running": sched.running}), 200


@bp.route("/sse/scheduler/stop", methods=["POST"])
def scheduler_stop() -> tuple[Response, int]:
    sched = _get_sched()
    if sched is None:
        return jsonify({"error": "scheduler not configured", "status": 500}), 500
    sched.stop()
    return jsonify({"status": "stopped", "running": sched.running}), 200


@bp.route("/sse/scheduler/pause", methods=["POST"])
def scheduler_pause() -> tuple[Response, int]:
    sched = _get_sched()
    if sched is None:
        return jsonify({"error": "scheduler not configured", "status": 500}), 500
    sched.pause()
    return jsonify({"status": "paused", "paused": sched.paused}), 200


@bp.route("/sse/scheduler/resume", methods=["POST"])
def scheduler_resume() -> tuple[Response, int]:
    sched = _get_sched()
    if sched is None:
        return jsonify({"error": "scheduler not configured", "status": 500}), 500
    sched.resume()
    return jsonify({"status": "resumed", "paused": sched.paused}), 200


@bp.route("/sse/scheduler/jobs", methods=["GET"])
def list_scheduler_jobs() -> tuple[Response, int]:
    sched = _get_sched()
    if sched is None:
        return jsonify({"error": "scheduler not configured", "status": 500}), 500
    return jsonify({"jobs": sched.list_jobs()}), 200


@bp.route("/sse/scheduler/jobs", methods=["POST"])
def add_scheduler_job() -> tuple[Response, int]:
    sched = _get_sched()
    if sched is None:
        return jsonify({"error": "scheduler not configured", "status": 500}), 500
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id", "")
    job_type = data.get("job_type", "cron")
    trigger_type = data.get("trigger_type", "cron")
    trigger_args = data.get("trigger_args", {})
    enabled = data.get("enabled", True)
    if not job_id:
        return jsonify({"error": "job_id is required", "status": 400}), 400
    try:
        if job_type == "interval":
            minutes = trigger_args.get("minutes", 5)
            sched.add_interval_job(job_id=job_id, minutes=minutes, enabled=enabled)
        else:
            hour = trigger_args.get("hour", "*")
            minute = trigger_args.get("minute", "0")
            day_of_week = trigger_args.get("day_of_week", "*")
            sched.add_cron_job(job_id=job_id, hour=hour, minute=minute, day_of_week=day_of_week, enabled=enabled)
        return jsonify({"status": "ok", "job_id": job_id}), 201
    except Exception as exc:
        logger.warning("Failed to add scheduler job: %s", exc)
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/sse/scheduler/jobs/<job_id>", methods=["DELETE"])
def remove_scheduler_job(job_id: str) -> tuple[Response, int]:
    sched = _get_sched()
    if sched is None:
        return jsonify({"error": "scheduler not configured", "status": 500}), 500
    removed = sched.remove_job(job_id)
    if not removed:
        return jsonify({"error": f"Job not found: {job_id}", "status": 404}), 404
    return jsonify({"status": "removed", "job_id": job_id}), 200


@bp.route("/sse/scheduler/jobs/<job_id>/toggle", methods=["POST"])
def toggle_scheduler_job(job_id: str) -> tuple[Response, int]:
    sched = _get_sched()
    if sched is None:
        return jsonify({"error": "scheduler not configured", "status": 500}), 500
    data = request.get_json(silent=True) or {}
    enabled = data.get("enabled", True)
    toggled = sched.toggle_job(job_id, enabled)
    if not toggled:
        return jsonify({"error": f"Job not found: {job_id}", "status": 404}), 404
    return jsonify({"status": "ok", "job_id": job_id, "enabled": enabled}), 200
