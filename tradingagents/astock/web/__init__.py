"""Flask Jinja2 WebUI Blueprint — Phase 17.

Provides 9 pages with Tailwind CSS (dark theme) that consume the Flask REST
API at ``/api/v1/`` via client-side ``fetch()``.
"""

from __future__ import annotations

from flask import Blueprint, render_template

bp = Blueprint(
    "web",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/web/static",
)

# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@bp.route("/")
def dashboard() -> str:
    return render_template("dashboard.html")


@bp.route("/research")
def research() -> str:
    return render_template("research.html")


@bp.route("/backtest")
def backtest() -> str:
    return render_template("backtest.html")


@bp.route("/strategies")
def strategies() -> str:
    return render_template("strategies.html")


@bp.route("/paper")
def paper() -> str:
    return render_template("paper.html")


@bp.route("/qmt")
def qmt() -> str:
    return render_template("qmt.html")


@bp.route("/risk")
def risk() -> str:
    return render_template("risk.html")


@bp.route("/reports")
def reports() -> str:
    return render_template("reports.html")


@bp.route("/settings")
def settings() -> str:
    return render_template("settings.html")


@bp.route("/performance")
def performance() -> str:
    return render_template("performance.html")


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

__all__ = ["bp"]
