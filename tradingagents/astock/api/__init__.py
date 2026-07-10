"""Flask REST API factory for AStock — Phase 15.

Creates a Flask app with CORS and registers all blueprints under
``/api/v1/``.  Supports both DuckDB (local dev) and PostgreSQL/TimescaleDB
(production) backends.

Backend selection (priority order)
----------------------------------
1. ``backend.json`` persistent config (``~/.tradingagents/backend.json``)
2. ``ASTOCK_DB_BACKEND`` env var at first run

Switch at runtime via ``POST /api/v1/admin/backend``.

ClickHouse sync automatically uses the currently active backend.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from flask import Flask
from flask_cors import CORS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------

DEFAULT_CORS_ORIGIN = "http://localhost:5173"

# Read version from pyproject.toml (works even when not installed as package)
try:
    import tomllib
    _pyproject_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "pyproject.toml")
    if os.path.exists(_pyproject_path):
        with open(_pyproject_path, "rb") as _f:
            APP_VERSION = tomllib.load(_f)["project"]["version"]
    else:
        from importlib.metadata import PackageNotFoundError, version as package_version
        APP_VERSION = package_version("tradingagents")
except Exception:
    APP_VERSION = "0.3.0"


def create_app(
    db_path: str | None = None,
    cors_origin: str | None = None,
    test_config: dict[str, Any] | None = None,
) -> Flask:
    """Application factory.

    Parameters
    ----------
    db_path : str or None
        DuckDB file path for development (defaults to backend config).
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
    app.config.setdefault("ASTOCK_ENABLE_WEB_UI", True)
    # Network-facing deployments must opt in to anonymous mutation explicitly.
    # The test harness sets ASTOCK_TESTING=1 before importing the app factory.
    app.config.setdefault(
        "ASTOCK_REQUIRE_AUTH",
        os.environ.get("ASTOCK_TESTING", "").lower() not in ("1", "true", "yes", "on"),
    )
    from tradingagents.astock.store.backend import backend_mgr
    app.config.setdefault("ASTOCK_MOCK_DATA_ENABLED", backend_mgr.config.mock_data_enabled)
    app.config.setdefault(
        "ASTOCK_RESEARCH_ONLY",
        os.environ.get("ASTOCK_RESEARCH_ONLY", "true").lower() not in ("0", "false", "no", "off"),
    )

    # -- CORS -----------------------------------------------------------------
    origin = cors_origin or os.environ.get("CORS_ORIGIN", DEFAULT_CORS_ORIGIN)
    CORS(app, origins=[origin])

    # -- Store / backend config -----------------------------------------------
    from ._helpers import _bool_config, _int_config
    from .app_factory import _build_store_config, _build_scheduler_config

    _build_store_config(app, db_path)

    # AI model info for template injection
    app.config["RESEARCH_MODEL"] = os.environ.get(
        "RESEARCH_MODEL",
        os.environ.get("TRADINGAGENTS_DEEP_THINK_LLM", "agnes-2.0-flash"),
    )

    # Override config for testing before components read app config.
    if test_config:
        app.config.update(test_config)

    # -- Scheduler ------------------------------------------------------------
    _build_scheduler_config(app)

    # -- Request hooks (before/after/error) -----------------------------------
    from .app_hooks import register_hooks
    register_hooks(app)

    # -- Blueprint registration -----------------------------------------------
    from .blueprint_registry import register_blueprints, wire_notification_store
    register_blueprints(app)

    # -- Notification store wiring --------------------------------------------
    wire_notification_store(app)

    # -- Phase 17: Web UI (Jinja2) blueprint ---------------------------------
    if _bool_config(app, "ASTOCK_ENABLE_WEB_UI", True):
        from tradingagents.astock.web import bp as web_bp
        app.register_blueprint(web_bp)

    return app


__all__ = ["create_app", "DEFAULT_CORS_ORIGIN", "APP_VERSION"]
