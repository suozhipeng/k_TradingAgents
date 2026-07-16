"""Dashboard page routes — Phase 17 / Web-P0.

Pages: /dashboard, /daily
Templates live in templates/dashboard/
"""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, render_template

bp = Blueprint("web_dashboard", __name__)


@bp.route("/dashboard")
def dashboard() -> str:
    return render_template("dashboard/dashboard.html")


@bp.route("/daily")
def daily_review() -> str:
    return render_template("dashboard/daily_review.html", today=datetime.now().strftime("%Y-%m-%d"))
