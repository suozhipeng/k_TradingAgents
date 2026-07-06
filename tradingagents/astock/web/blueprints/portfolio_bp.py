"""Portfolio & Execution page routes — Phase 17.

Pages: /trading, /paper, /qmt, /risk, /portfolio, /reports
Templates live in templates/portfolio/
"""

from __future__ import annotations

from flask import Blueprint, render_template

bp = Blueprint("web_portfolio", __name__)


@bp.route("/trading")
def trading() -> str:
    return render_template("portfolio/trading.html")


@bp.route("/paper")
def paper() -> str:
    return render_template("portfolio/paper.html")


@bp.route("/qmt")
def qmt() -> str:
    return render_template("portfolio/qmt.html")


@bp.route("/risk")
def risk() -> str:
    return render_template("portfolio/risk.html")


@bp.route("/portfolio")
def portfolio() -> str:
    return render_template("portfolio/portfolio.html")


@bp.route("/reports")
def reports() -> str:
    return render_template("portfolio/reports.html")
