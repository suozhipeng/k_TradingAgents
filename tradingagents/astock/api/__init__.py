"""Flask REST API factory for AStock — Phase 15.

Creates a Flask app with CORS and registers all blueprints under
``/api/v1/``.  The store defaults to ``~/.tradingagents/astock/astock.duckdb``.

All ``tradingagents.astock`` imports are lazy (inside functions) to avoid
triggering the full package dependency chain at module load time.
"""

from __future__ import annotations

import os
from typing import Any

from flask import Flask, jsonify
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------

DEFAULT_DB_PATH = "~/.tradingagents/astock/astock.duckdb"
DEFAULT_CORS_ORIGIN = "http://localhost:5173"


def _init_store(db_path: str) -> Any:
    """Lazy import + init of AStockStore so ``tradingagents.astock`` is
    not imported at module level."""
    from tradingagents.astock.store.schema import init_astock_db

    return init_astock_db(db_path)


def create_app(
    db_path: str | None = None,
    cors_origin: str | None = None,
    test_config: dict[str, Any] | None = None,
) -> Flask:
    """Application factory.

    Parameters
    ----------
    db_path : str or None
        DuckDB file path.  Defaults to ``~/.tradingagents/astock/astock.duckdb``.
        Pass ``':memory:'`` for testing.
    cors_origin : str or None
        CORS allowed origin.  Defaults to ``http://localhost:5173``.
    test_config : dict or None
        Extra Flask config for test overrides.

    Returns
    -------
    Flask
        Configured Flask application instance.
    """
    app = Flask(__name__)

    # -- CORS -----------------------------------------------------------------
    origin = cors_origin or os.environ.get("CORS_ORIGIN", DEFAULT_CORS_ORIGIN)
    CORS(app, origins=[origin])

    # -- Store ----------------------------------------------------------------
    resolved_db = db_path or os.environ.get(
        "ASTOCK_DB_PATH", DEFAULT_DB_PATH
    )
    store = _init_store(resolved_db)
    app.config["STORE"] = store
    app.config["DB_PATH"] = resolved_db

    # -- Data facade (router + loaders for refresh API) -----------------------
    try:
        from tradingagents.astock.data_sources.router import AStockDataFacade

        facade = AStockDataFacade()
        app.config["DATA_FACADE"] = facade
    except Exception:
        app.config["DATA_FACADE"] = None

    # Override config for testing
    if test_config:
        app.config.update(test_config)

    # -- Error handlers -------------------------------------------------------
    @app.errorhandler(400)
    def bad_request(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Bad request", "status": 400}), 400

    @app.errorhandler(404)
    def not_found(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Not found", "status": 404}), 404

    @app.errorhandler(500)
    def server_error(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Internal server error", "status": 500}), 500

    # -- Register blueprints (lazy imports) ----------------------------------
    # Each blueprint module uses lazy imports internally; loading them here
    # only triggers the top-level Python module import, not the full astock
    # dependency chain.
    from . import routes_data
    from . import routes_backtest
    from . import routes_paper
    from . import routes_market
    from . import routes_qmt
    from . import routes_sse
    from . import routes_reports
    from . import routes_dashboard
    from . import routes_screener
    from . import routes_market_data
    from . import routes_data_health
    from . import routes_trade
    from . import routes_tv
    from . import routes_ai_agent

    app.register_blueprint(routes_data.bp, url_prefix="/api/v1")
    app.register_blueprint(routes_backtest.bp, url_prefix="/api/v1")
    app.register_blueprint(routes_paper.bp, url_prefix="/api/v1")
    app.register_blueprint(routes_market.bp, url_prefix="/api/v1")
    app.register_blueprint(routes_qmt.bp, url_prefix="/api/v1")
    app.register_blueprint(routes_sse.bp, url_prefix="/api/v1")
    app.register_blueprint(routes_reports.bp, url_prefix="/api/v1")
    app.register_blueprint(routes_dashboard.bp, url_prefix="/api/v1")
    app.register_blueprint(routes_screener.bp, url_prefix="/api/v1")
    app.register_blueprint(routes_market_data.bp, url_prefix="/api/v1")
    app.register_blueprint(routes_data_health.bp, url_prefix="/api/v1")
    app.register_blueprint(routes_trade.bp, url_prefix="/api/v1")
    app.register_blueprint(routes_tv.bp, url_prefix="/api/v1")
    app.register_blueprint(routes_ai_agent.bp, url_prefix="/api/v1")

    # -- Phase 17: Web UI (Jinja2) blueprint -------------------------------
    from tradingagents.astock.web import bp as web_bp

    app.register_blueprint(web_bp)

    # -- Health check ---------------------------------------------------------
    @app.route("/api/v1/health")
    def health() -> tuple[Any, int]:
        return jsonify({"status": "ok", "version": "0.2.5"}), 200

    return app


__all__ = ["create_app", "DEFAULT_DB_PATH", "DEFAULT_CORS_ORIGIN"]
