"""Flask Jinja2 WebUI Blueprint — Phase 17.

Provides 9 pages with Tailwind CSS (dark theme) that consume the Flask REST
API at ``/api/v1/`` via client-side ``fetch()``.
"""

from __future__ import annotations

from datetime import datetime

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
def trading() -> str:
    return render_template("trading.html")


@bp.route("/dashboard")
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


@bp.route("/comparison")
def comparison() -> str:
    return render_template("comparison.html")


@bp.route("/screener")
def screener() -> str:
    return render_template("screener.html")


@bp.route("/dragon_tiger")
def dragon_tiger() -> str:
    return render_template("dragon_tiger.html", today=datetime.now().strftime("%Y-%m-%d"))


@bp.route("/sectors")
def sectors() -> str:
    return render_template("sectors.html")


@bp.route("/northbound")
def northbound() -> str:
    return render_template("northbound.html")


@bp.route("/data_health")
def data_health() -> str:
    return render_template("data_health.html")


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

__all__ = ["bp"]
