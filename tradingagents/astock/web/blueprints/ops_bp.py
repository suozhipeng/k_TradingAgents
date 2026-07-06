"""Ops & Audit page routes — Phase 17.

Pages: /ops_audit, /data_health, /settings, /settings/notifications
Templates live in templates/ops/
"""

from __future__ import annotations

from flask import Blueprint, render_template

bp = Blueprint("web_ops", __name__)


@bp.route("/ops_audit")
def ops_audit() -> str:
    return render_template("ops/ops_audit.html")


@bp.route("/data_health")
def data_health() -> str:
    return render_template("ops/data_health.html")


@bp.route("/settings")
def settings() -> str:
    return render_template("ops/settings.html")


@bp.route("/settings/notifications")
def settings_notifications() -> str:
    return render_template("ops/settings.html", section="notifications")
