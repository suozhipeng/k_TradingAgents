"""Watch Center page routes — Phase 17.

Pages: /watchlist, /batch-analyze, /screener, /market_leaders, /monitor,
       /kc_chart
Templates live in templates/watch_center/
"""

from __future__ import annotations

from flask import Blueprint, render_template, request

bp = Blueprint("web_watch_center", __name__)


@bp.route("/watchlist")
def watchlist_page() -> str:
    return render_template("watch_center/watchlist.html")


@bp.route("/batch-analyze")
def batch_analyze_page() -> str:
    return render_template("watch_center/watchlist.html", batch_mode=True)


@bp.route("/screener")
def screener() -> str:
    return render_template("watch_center/screener.html")


@bp.route("/market_leaders")
def market_leaders() -> str:
    return render_template("watch_center/market_leaders.html")


@bp.route("/monitor")
def monitor() -> str:
    return render_template("watch_center/monitor.html")


@bp.route("/kc_chart")
def kc_chart() -> str:
    symbol = request.args.get("symbol", "600519.SH")
    standalone = request.args.get("standalone", "0") == "1"
    return render_template("watch_center/kc_chart.html", symbol=symbol, standalone=standalone)
