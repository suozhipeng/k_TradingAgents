"""Strategy Lab page routes — Phase 17.

Pages: /strategy_hub, /strategies, /strategies/monitor, /backtest
Templates live in templates/strategy/
"""

from __future__ import annotations

from flask import Blueprint, redirect, url_for, render_template

bp = Blueprint("web_strategy", __name__)


@bp.route("/strategy_hub")
def strategy_hub() -> str:
    return render_template("strategy/strategy_hub.html")


@bp.route("/strategies")
def strategies() -> str:
    return render_template("strategy/strategies.html")


@bp.route("/strategies/monitor")
def strategy_monitor() -> str:
    return render_template("strategy/strategy_monitor.html")


@bp.route("/backtest")
def backtest_console() -> str:
    return render_template("strategy/backtest.html")


@bp.route("/comparison")
@bp.route("/compare")
def comparison_redirect() -> str:
    return redirect(url_for("web_strategy.strategy_hub"), 301)


@bp.route("/performance")
def performance_redirect() -> str:
    return redirect(url_for("web_strategy.strategy_hub"), 301)
