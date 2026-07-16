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
