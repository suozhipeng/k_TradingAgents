"""WebUI Blueprint aggregate — registers all module blueprints.

This replaces the monolithic __init__.py that had 326 lines of route
definitions.  Each functional module now has its own blueprint file under
``blueprints/``.
"""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, redirect

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
REACT_DIST = str(BASE_DIR.parent.parent / "webui" / "dist")

# Create the aggregate web blueprint
bp = Blueprint(
    "web",
    __name__,
    template_folder=TEMPLATES_DIR,
    static_folder=REACT_DIST if Path(REACT_DIST).exists() else STATIC_DIR,
    static_url_path="/web/static",
)

# Register child blueprints with unique sub-names under web namespace
bp.register_blueprint(dashboard_bp, name="dashboard")
bp.register_blueprint(watch_center_bp, name="watch_center")
bp.register_blueprint(research_bp, name="research")
bp.register_blueprint(strategy_bp, name="strategy")
bp.register_blueprint(portfolio_bp, name="portfolio")
bp.register_blueprint(ops_bp, name="ops")

# Root redirect → React homepage (dashboard)
# Jinja2 legacy pages still accessible via /web/dashboard etc.
@bp.route("/")
def root():
    return redirect("/dashboard", 302)


@bp.route("/<path:path>")
def spa_fallback(path):
    """SPA fallback: serve React index.html for non-static, non-API routes."""
    react_index = Path(REACT_DIST) / "index.html"
    if Path(REACT_DIST).exists() and path not in ("dashboard", "data-hub", "research", "strategy", "module-map", "agent-flow", "task-center", "risk-panel", "help"):
        return bp.send_static_file("index.html")
    # Legacy Jinja2 routes
    return redirect(f"/{path}", 302)
