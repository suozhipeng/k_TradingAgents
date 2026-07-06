"""Dashboard page routes — Phase 17 / Web-P0.

Pages: /dashboard, /daily, /momentum_dashboard, /momentum_standalone
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


@bp.route("/momentum_dashboard")
def momentum_dashboard() -> str:
    return render_template("dashboard/momentum_dashboard.html", legacy_redirect="/market_leaders")


@bp.route("/momentum_standalone")
def momentum_standalone() -> str:
    return render_template("dashboard/momentum_dashboard.html", legacy_redirect="/market_leaders")
