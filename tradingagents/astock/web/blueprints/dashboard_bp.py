"""Dashboard page routes — Phase 17 / Web-P0.

Pages: /dashboard, /daily, /momentum_dashboard, /momentum_standalone
Templates live in templates/dashboard/
"""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, redirect, render_template, url_for

bp = Blueprint("web_dashboard", __name__)


@bp.route("/dashboard")
def dashboard() -> str:
    return render_template("dashboard/dashboard.html")


@bp.route("/daily")
def daily_review() -> str:
    return render_template("dashboard/daily_review.html", today=datetime.now().strftime("%Y-%m-%d"))


@bp.route("/momentum_dashboard")
def momentum_dashboard():
    """Keep the historic URL while routing to the consolidated workbench."""
    return redirect(url_for("web.watch_center.market_leaders", tab="momentum"), code=302)


@bp.route("/momentum_standalone")
def momentum_standalone():
    """Keep the historic URL while routing to the consolidated workbench."""
    return redirect(url_for("web.watch_center.market_leaders", tab="momentum"), code=302)
