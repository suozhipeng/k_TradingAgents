"""Ops & Audit page routes — Phase 17 + PR-5 Data Hub."""
from __future__ import annotations
from flask import Blueprint, abort, current_app, render_template

bp = Blueprint("web_ops", __name__)


@bp.route("/ops_audit")
def ops_audit() -> str:
    if current_app.config.get("ASTOCK_LOCAL_RELEASE", False):
        abort(404)
    return render_template("ops/ops_audit.html")


@bp.route("/data_health")
def data_health() -> str:
    return render_template("ops/data_health.html")


@bp.route("/settings")
def settings() -> str:
    return render_template("ops/settings.html",
        local_release=current_app.config.get("ASTOCK_LOCAL_RELEASE", False))


@bp.route("/settings/notifications")
def settings_notifications() -> str:
    return render_template("ops/settings.html",
        section="notifications",
        local_release=current_app.config.get("ASTOCK_LOCAL_RELEASE", False))


@bp.route("/data_hub")
def data_hub() -> str:
    """Data Hub page — shows data sources, table stats, ingestion status."""
    return render_template("ops/data_hub.html")
