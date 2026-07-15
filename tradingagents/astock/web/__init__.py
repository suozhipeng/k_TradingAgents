"""WebUI Blueprint aggregate — registers all module blueprints.

This replaces the monolithic __init__.py that had 326 lines of route
definitions.  Each functional module now has its own blueprint file under
``blueprints/``.
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, abort, redirect, send_from_directory

BASE_DIR = Path(__file__).resolve().parent

# Import all module blueprints (side-effect: registers them)
from .blueprints.dashboard_bp import bp as dashboard_bp
from .blueprints.watch_center_bp import bp as watch_center_bp
from .blueprints.research_bp import bp as research_bp
from .blueprints.strategy_bp import bp as strategy_bp
from .blueprints.portfolio_bp import bp as portfolio_bp
from .blueprints.ops_bp import bp as ops_bp

TEMPLATES_DIR = str(BASE_DIR / "templates")
STATIC_DIR = str(BASE_DIR / "static")
REACT_DIST = str(BASE_DIR.parent.parent.parent / "webui" / "dist")

# Create the aggregate web blueprint
bp = Blueprint(
    "web",
    __name__,
    template_folder=TEMPLATES_DIR,
    # The local formal release serves the Jinja2 workbench assets.
    static_folder=STATIC_DIR,
    static_url_path="/web/static",
)

# Register child blueprints with unique sub-names under web namespace
bp.register_blueprint(dashboard_bp, name="dashboard")
bp.register_blueprint(watch_center_bp, name="watch_center")
bp.register_blueprint(research_bp, name="research")
bp.register_blueprint(strategy_bp, name="strategy")
bp.register_blueprint(portfolio_bp, name="portfolio")
bp.register_blueprint(ops_bp, name="ops")

# Root redirect → dashboard.
@bp.route("/")
def root():
    return redirect("/dashboard", 302)


@bp.route("/assets/<path:path>")
def react_assets(path: str):
    """Serve React static assets (JS/CSS) from the built dist."""
    if REACT_DIST and os.path.isdir(REACT_DIST):
        asset_dir = os.path.join(REACT_DIST, "assets")
        if os.path.isdir(asset_dir):
            return send_from_directory(asset_dir, path)
    return abort(404)


@bp.route("/react/<path:path>")
def react_static(path: str):
    """Serve other React files from the built dist root."""
    if REACT_DIST and os.path.isdir(REACT_DIST):
        return send_from_directory(REACT_DIST, path)
    return abort(404)


@bp.route("/<path:path>")
def spa_fallback(path: str):
    """Serve React SPA index.html for any non-API, non-static route.

    API routes (/api/*) must still return 404 when unmatched — we don't
    want the React fallback swallowing API errors.

    In local release mode the React SPA is not exposed; unknown routes
    must return 404 so the analysis-and-backtest-only surface is enforced.
    """
    if path.startswith("api/") or path.startswith("api:") or path.startswith("api?"):
        abort(404)
    from flask import current_app
    if current_app and current_app.config.get("ASTOCK_LOCAL_RELEASE", False):
        abort(404)
    if REACT_DIST and os.path.isdir(REACT_DIST):
        return send_from_directory(REACT_DIST, "index.html")
    abort(404)
