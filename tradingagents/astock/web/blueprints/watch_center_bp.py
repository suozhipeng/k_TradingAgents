"""Watch Center page routes — Phase 17.

Pages: /watchlist, /batch-analyze, /screener, /market_leaders, /monitor,
       /tv_chart, /kc_chart, /dragon_tiger, /sectors, /northbound,
       /momentum_rotation
Templates live in templates/watch_center/
"""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, url_for

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


@bp.route("/tv_chart")
def tv_chart() -> str:
    symbol = request.args.get("symbol", "600519.SH")
    return render_template("watch_center/tv_chart.html", symbol=symbol)


@bp.route("/kc_chart")
def kc_chart() -> str:
    symbol = request.args.get("symbol", "600519.SH")
    standalone = request.args.get("standalone", "0") == "1"
    return render_template("watch_center/kc_chart.html", symbol=symbol, standalone=standalone)


# Legacy redirects → the corresponding /market_leaders tab.
@bp.route("/dragon_tiger")
def dragon_tiger():
    return redirect(url_for("web.watch_center.market_leaders", tab="dragon_tiger"), code=302)


@bp.route("/sectors")
def sectors():
    return redirect(url_for("web.watch_center.market_leaders", tab="sectors"), code=302)


@bp.route("/northbound")
def northbound():
    return redirect(url_for("web.watch_center.market_leaders", tab="northbound"), code=302)


@bp.route("/momentum_rotation")
def momentum_rotation():
    return redirect(url_for("web.watch_center.market_leaders", tab="rotation"), code=302)
