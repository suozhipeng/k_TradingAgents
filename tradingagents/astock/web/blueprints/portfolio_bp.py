"""Portfolio & Execution page routes — Phase 17.

Pages: /trading, /paper, /qmt, /risk, /portfolio, /reports
Templates live in templates/portfolio/
"""

from __future__ import annotations

from flask import Blueprint, abort, redirect, render_template, url_for, current_app

bp = Blueprint("web_portfolio", __name__)


def _redirect_if_research_only():
    """Return a 302 redirect to /dashboard if in research-only mode."""
    if current_app and current_app.config.get("ASTOCK_LOCAL_RELEASE", False):
        abort(404)
    if current_app and current_app.config.get("ASTOCK_RESEARCH_ONLY", True):
        return redirect(url_for("web.dashboard.dashboard"), 302)
    return None


@bp.route("/trading")
def trading():
    rv = _redirect_if_research_only()
    if rv:
        return rv
    return render_template("portfolio/trading.html")


@bp.route("/paper")
def paper():
    rv = _redirect_if_research_only()
    if rv:
        return rv
    return render_template("portfolio/paper.html")


@bp.route("/qmt")
def qmt():
    rv = _redirect_if_research_only()
    if rv:
        return rv
    return render_template("portfolio/qmt.html")


@bp.route("/risk")
def risk():
    rv = _redirect_if_research_only()
    if rv:
        return rv
    return render_template("portfolio/risk.html")


@bp.route("/portfolio")
def portfolio():
    rv = _redirect_if_research_only()
    if rv:
        return rv
    return render_template("portfolio/portfolio.html")


@bp.route("/reports")
def reports():
    return render_template("portfolio/reports.html")
