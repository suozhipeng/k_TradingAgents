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


def _env_enabled(name: str) -> bool:
    """Return True only for explicit enabled environment values."""
    return os.environ.get(name, "").lower() in ("1", "true", "yes", "on")


def _env_bool(name: str, default: bool) -> bool:
    """Read an optional boolean environment setting without hiding its default."""
    if name not in os.environ:
        return default
    return _env_enabled(name)

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
    app.config.setdefault("MAX_CONTENT_LENGTH", int(os.environ.get("ASTOCK_MAX_REQUEST_BYTES", str(1024 * 1024))))
    app.config.setdefault("ASTOCK_ENABLE_WEB_UI", True)
    # Apply caller overrides before constructing any app-owned services.  In
    # particular, DataJobManager and the scheduler read their limits during
    # construction; applying test_config later silently left those services
    # with environment/default values.
    if test_config:
        app.config.update(test_config)
    local_release = _env_enabled("ASTOCK_LOCAL_RELEASE")
    app.config.setdefault("ASTOCK_LOCAL_RELEASE", local_release)
    # The supported product surface is a loopback-only, single-user local
    # workbench.  It must work without asking the browser to retain a bearer
    # token.  Non-local processes remain fail-closed unless explicitly
    # configured otherwise.
    app.config.setdefault(
        "ASTOCK_REQUIRE_AUTH",
        _env_bool("ASTOCK_REQUIRE_AUTH", not (local_release or _env_enabled("ASTOCK_TESTING"))),
    )
    from tradingagents.astock.store.backend import backend_mgr
    app.config.setdefault("ASTOCK_MOCK_DATA_ENABLED", backend_mgr.config.mock_data_enabled)
    app.config.setdefault(
        "ASTOCK_RESEARCH_ONLY",
        os.environ.get("ASTOCK_RESEARCH_ONLY", "true").lower() not in ("0", "false", "no", "off"),
    )
    # GET requests are read-only by default. Clients that need a foreground
    # refresh must opt in with ``refresh=1`` or an explicit deployment flag.
    app.config.setdefault(
        "ASTOCK_AUTO_REFRESH_DAILY_KLINE",
        os.environ.get("ASTOCK_AUTO_REFRESH_DAILY_KLINE", "").lower()
        in ("1", "true", "yes", "on")
        if "ASTOCK_AUTO_REFRESH_DAILY_KLINE" in os.environ
        else False,
    )
    app.config.setdefault(
        "ASTOCK_DAILY_KLINE_REFRESH_TIMEOUT_SECONDS",
        float(os.environ.get("ASTOCK_DAILY_KLINE_REFRESH_TIMEOUT_SECONDS", "8")),
    )
    app.config.setdefault(
        "ASTOCK_MAIN_ANALYSIS_TIMEOUT_SECONDS",
        float(os.environ.get("ASTOCK_MAIN_ANALYSIS_TIMEOUT_SECONDS", "45")),
    )
    app.config.setdefault(
        "ASTOCK_ANALYSIS_PROCESS_ISOLATION",
        _env_enabled("ASTOCK_ANALYSIS_PROCESS_ISOLATION")
        if "ASTOCK_ANALYSIS_PROCESS_ISOLATION" in os.environ else True,
    )
    app.config.setdefault("ASTOCK_SLOW_REQUEST_MS", float(os.environ.get("ASTOCK_SLOW_REQUEST_MS", "1000")))
    app.config.setdefault("ASTOCK_LLM_REPORT_TTL_SECONDS", float(os.environ.get("ASTOCK_LLM_REPORT_TTL_SECONDS", "600")))
    app.config.setdefault("ASTOCK_LLM_REPORT_CACHE_MAX_ENTRIES", int(os.environ.get("ASTOCK_LLM_REPORT_CACHE_MAX_ENTRIES", "100")))
    app.config.setdefault("ASTOCK_AUTO_REFRESH_INTRADAY_KLINE", _env_enabled("ASTOCK_AUTO_REFRESH_INTRADAY_KLINE") if "ASTOCK_AUTO_REFRESH_INTRADAY_KLINE" in os.environ else True)
    app.config.setdefault("ASTOCK_INTRADAY_KLINE_INTERVAL", os.environ.get("ASTOCK_INTRADAY_KLINE_INTERVAL", "5m"))
    app.config.setdefault("ASTOCK_INTRADAY_KLINE_REFRESH_TIMEOUT_SECONDS", float(os.environ.get("ASTOCK_INTRADAY_KLINE_REFRESH_TIMEOUT_SECONDS", "5")))
    app.config.setdefault(
        "ASTOCK_PERMANENT_KLINE_ENABLED",
        _env_enabled("ASTOCK_PERMANENT_KLINE_ENABLED") if "ASTOCK_PERMANENT_KLINE_ENABLED" in os.environ else not _env_enabled("ASTOCK_TESTING"),
    )
    # Batch imports and request-time incremental refreshes share one canonical
    # local warehouse so backtests have a complete source of truth.
    app.config.setdefault("ASTOCK_PERMANENT_KLINE_DB_PATH", os.environ.get("ASTOCK_PERMANENT_KLINE_DB_PATH", "kline/kline.duckdb"))
    app.config.setdefault("ASTOCK_BACKTEST_ALLOW_LIVE_FALLBACK", _env_enabled("ASTOCK_BACKTEST_ALLOW_LIVE_FALLBACK"))
    app.config.setdefault("ASTOCK_DATA_JOB_MAX_QUEUED", int(os.environ.get("ASTOCK_DATA_JOB_MAX_QUEUED", "100")))
    # A test process creates many app instances. Do not leave one
    # APScheduler thread per compatibility-mode test app unless a test
    # explicitly opts in. Production/default behaviour remains enabled when
    # ASTOCK_TESTING is not set, and the guards below still force it off for
    # local-release/research-only apps.
    app.config.setdefault(
        "ASTOCK_SCHEDULER_ENABLED",
        _env_bool("ASTOCK_SCHEDULER_ENABLED", not _env_enabled("ASTOCK_TESTING")),
    )
    app.config.setdefault("ASTOCK_DASHBOARD_STATS_TTL_SECONDS", float(os.environ.get("ASTOCK_DASHBOARD_STATS_TTL_SECONDS", "30")))
    app.config.setdefault("ASTOCK_IDEMPOTENCY_TTL_SECONDS", float(os.environ.get("ASTOCK_IDEMPOTENCY_TTL_SECONDS", "300")))
    app.config.setdefault("ASTOCK_IDEMPOTENCY_MAX_ENTRIES", int(os.environ.get("ASTOCK_IDEMPOTENCY_MAX_ENTRIES", "1000")))
    app.config.setdefault("ASTOCK_RATE_LIMIT_PER_MINUTE", int(os.environ.get("ASTOCK_RATE_LIMIT_PER_MINUTE", "300")))
    app.config.setdefault("ASTOCK_RATE_LIMIT_MAX_KEYS", int(os.environ.get("ASTOCK_RATE_LIMIT_MAX_KEYS", "10000")))
    app.config.setdefault("ASTOCK_SSE_MAX_CLIENTS", int(os.environ.get("ASTOCK_SSE_MAX_CLIENTS", "50")))
    app.config.setdefault("ASTOCK_MARKET_TIMEZONE", os.environ.get("ASTOCK_MARKET_TIMEZONE", "Asia/Shanghai"))
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_SECURE", _env_enabled("ASTOCK_COOKIE_SECURE"))
    worker_count = int(os.environ.get("WEB_CONCURRENCY", "1"))
    if worker_count > 1:
        raise RuntimeError(
            "WEB_CONCURRENCY must be 1: SSE, background jobs and report cache "
            "are process-local. Deploy a shared coordination backend before enabling multi-worker mode."
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

    # The local formal release is analysis/backtest-only.  Apply this after
    # test configuration as a non-bypassable product-scope guard.
    if app.config.get("ASTOCK_LOCAL_RELEASE", False):
        app.config["ASTOCK_RESEARCH_ONLY"] = True
        app.config["ASTOCK_SCHEDULER_ENABLED"] = False
        # The sole supported UI runs on loopback and uses same-origin requests.
        # Do not make its functionality depend on a browser-held API key.
        app.config["ASTOCK_REQUIRE_AUTH"] = False
        # Reads remain side-effect free.  The workbench explicitly uses the
        # refresh API/job when it needs to initialise or update local bars.
        app.config["ASTOCK_AUTO_REFRESH_DAILY_KLINE"] = False

        # -- PR-2: Single canonical DuckDB enforced ----------------------------------
        # Force every local-release instance to use exactly one database
        # (~/.tradingagents/astock/astock.duckdb).  No second K-line warehouse,
        # no PostgreSQL escape hatch, no mock-data fallback.
        app.config["ASTOCK_PERMANENT_KLINE_ENABLED"] = False
        app.config["ASTOCK_MOCK_DATA_ENABLED"] = False
        app.config.setdefault("ASTOCK_DB_BACKEND", "duckdb")
        app.config.setdefault(
            "ASTOCK_DB_PATH",
            os.path.expanduser("~/.tradingagents/astock/astock.duckdb"),
        )
        logger.info(
            "PR-2 local-release: enforced single canonical DuckDB path, disabled "
            "permanent_kline and mock_data"
        )
    elif app.config.get("ASTOCK_RESEARCH_ONLY", True):
        # Research-only is a runtime boundary, not just an HTTP-route guard.
        app.config["ASTOCK_SCHEDULER_ENABLED"] = False

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

    # -- Process shutdown ------------------------------------------------------
    from .lifecycle import register_atexit_shutdown
    register_atexit_shutdown(app)

    # -- Phase 17: Web UI (Jinja2) blueprint ---------------------------------
    if _bool_config(app, "ASTOCK_ENABLE_WEB_UI", True):
        from tradingagents.astock.web import bp as web_bp
        app.register_blueprint(web_bp)

    return app


__all__ = ["create_app", "DEFAULT_CORS_ORIGIN", "APP_VERSION"]
