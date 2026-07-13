"""Ops & Audit page routes — Phase 17.

Pages: /ops_audit, /data_health, /settings, /settings/notifications
Templates live in templates/ops/
"""

from __future__ import annotations

from flask import Blueprint, abort, current_app, render_template

bp = Blueprint("web_ops", __name__)


@bp.route("/ops_audit")
def ops_audit() -> str:
    # This page still contains explicit "to be integrated" placeholders.
    # Do not expose it in the supported local formal-release surface.
    if current_app.config.get("ASTOCK_LOCAL_RELEASE", False):
        abort(404)
    return render_template("ops/ops_audit.html")


@bp.route("/data_health")
def data_health() -> str:
    return render_template("ops/data_health.html")


@bp.route("/settings")
def settings() -> str:
    return render_template(
        "ops/settings.html",
        local_release=current_app.config.get("ASTOCK_LOCAL_RELEASE", False),
    )


@bp.route("/settings/notifications")
def settings_notifications() -> str:
    return render_template(
        "ops/settings.html",
        section="notifications",
        local_release=current_app.config.get("ASTOCK_LOCAL_RELEASE", False),
    )
