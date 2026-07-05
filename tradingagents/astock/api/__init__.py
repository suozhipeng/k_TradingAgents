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

from flask import Flask, g, jsonify
from flask_cors import CORS

from tradingagents.astock.store.backend import backend_mgr

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------

DEFAULT_CORS_ORIGIN = "http://localhost:5173"


def _bool_env(key: str, default: bool = False) -> bool:
    """Read a boolean env var."""
    val = os.environ.get(key, "")
    if not val:
        return default
    return val.strip().lower() in ("true", "1", "yes", "on")


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

    # -- CORS -----------------------------------------------------------------
    origin = cors_origin or os.environ.get("CORS_ORIGIN", DEFAULT_CORS_ORIGIN)
    CORS(app, origins=[origin])

    # -- Backend selection via BackendManager ---------------------------------
    # An explicit db_path is a factory-level override used by tests and local
    # one-off apps.  It must not reuse the process-wide BackendManager store,
    # otherwise ":memory:" databases leak state across app instances.
    if db_path is not None:
        from tradingagents.astock.store.schema import init_astock_db

        store = init_astock_db(db_path)
        app.config["DB_BACKEND"] = "duckdb"
        app.config["STORE"] = store
        app.config["PG_STORE"] = None
    else:
        backend = backend_mgr.current_backend
        app.config["DB_BACKEND"] = backend

        # Initialise the active store (lazy — BackendManager only connects on demand)
        if backend == "postgresql":
            store = backend_mgr.get_pg_store()
            if store is None:
                raise RuntimeError(
                    "Backend is 'postgresql' but PGStore connection failed. "
                    "Run POST /api/v1/admin/backend to check PG_HOST/PG_PORT/PG_DB."
                )
            app.config["STORE"] = store
            app.config["PG_STORE"] = store
        else:
            store = backend_mgr.get_duck_store()
            app.config["STORE"] = store
            app.config["PG_STORE"] = None

    # Wrap store with quality-gated ValidatedStore
    from tradingagents.astock.quality import QualityExecutor, ValidatedStore
    raw_store = app.config["STORE"]
    executor = QualityExecutor(raw_store, dry_run=False)
    app.config["STORE"] = ValidatedStore(raw_store, executor)

    # Always make BackendManager available to routes
    app.config["BACKEND_MGR"] = backend_mgr

    # DataJobManager
    from tradingagents.astock.store.jobs import DataJobManager
    app.config["DATA_JOB_MANAGER"] = DataJobManager()

    # Data facade (router + loaders)
    try:
        from tradingagents.astock.data_sources.router import AStockDataFacade
        app.config["DATA_FACADE"] = AStockDataFacade()
    except Exception:
        app.config["DATA_FACADE"] = None

    # AI model info for template injection
    app.config["RESEARCH_MODEL"] = os.environ.get(
        "RESEARCH_MODEL",
        os.environ.get("TRADINGAGENTS_DEEP_THINK_LLM", "agnes-2.0-flash"),
    )

    # Auto-start PaperTradeScheduler with APScheduler (configurable)
    try:
        from tradingagents.astock.execution.scheduler import PaperTradeScheduler as PTS

        pts = PTS(
            paper_trader=app.config.get("PAPER_TRADER"),
            store=app.config.get("STORE"),
            interval_minutes=int(os.environ.get("ASTOCK_SCHEDULER_INTERVAL_MIN", "30")),
            enabled=_bool_env("ASTOCK_SCHEDULER_ENABLED", True),
        )
        pts.start()
        app.config["SCHEDULER"] = pts
    except Exception as exc:
        logger.warning("PaperTradeScheduler not started: %s", exc)
        app.config["SCHEDULER"] = None

    # Override config for testing
    if test_config:
        app.config.update(test_config)

    # -- before_request: inject globals per request --------------------------
    @app.before_request
    def _inject_globals() -> None:
        g.store = app.config.get("STORE")
        g.pg_store = app.config.get("PG_STORE")
        g.backend_mgr = app.config.get("BACKEND_MGR")
        g.actor = "anonymous"
        g.role = "public"
        g.key_id = ""
        g.allowed_capabilities = ""

    # -- Write-operation auth gate (postgresql mode only) --------------------
    @app.before_request
    def _require_auth_on_writes() -> tuple[Any, int] | None:
        from flask import request

        backend = app.config.get("DB_BACKEND", "duckdb")
        if backend != "postgresql":
            return None
        if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
            return None
        if any(request.path.startswith(p) for p in ("/api/v1/health",)):
            return None

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing_auth",
                            "message": "Bearer token required for write operations"}), 401

        import hashlib
        key_hash = hashlib.sha256(auth[7:].encode()).hexdigest()
        store = app.config.get("PG_STORE") or app.config.get("STORE")

        record = None
        if store and hasattr(store, "validate_api_key"):
            try:
                import asyncio
                if asyncio.iscoroutinefunction(store.validate_api_key):
                    record = asyncio.run(store.validate_api_key(key_hash))
                else:
                    record = store.validate_api_key(key_hash)
            except Exception:
                record = None

        if record is None:
            return jsonify({"error": "invalid_key",
                            "message": "Invalid or expired API key"}), 401

        g.actor = record.get("key_id", "unknown")
        g.role = record.get("role", "readonly")
        g.key_id = record.get("key_id", "")
        g.allowed_capabilities = record.get("allowed_capabilities", "")
        return None

    # -- after_request: auto-write audit log for write operations ----------
    @app.after_request
    def _audit_write_operations(response: Any) -> Any:
        """Non-blocking audit for all POST/PUT/DELETE/PATCH operations."""
        from flask import request

        if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
            return response
        if request.path.startswith("/api/v1/health"):
            return response

        store = app.config.get("STORE")
        if store is None:
            return response

        try:
            import uuid, json as _json, time
            actor = getattr(g, "actor", "anonymous")
            status_code = response.status_code if hasattr(response, "status_code") else 200

            detail = {
                "path": request.path,
                "method": request.method,
                "status": status_code,
                "query": dict(request.args),
            }
            try:
                body = request.get_json(silent=True)
                if body:
                    detail["body_keys"] = list(body.keys())[:20]
            except Exception:
                pass

            segs = request.path.strip("/").split("/")
            resource_type = segs[2] if len(segs) > 2 else "api"

            audit_data = {
                "event_id": uuid.uuid4().hex,
                "event_type": "api_write",
                "actor": actor,
                "resource_type": resource_type,
                "resource_id": segs[-1] if segs else "",
                "action": f"{request.method} {request.path}",
                "detail_json": _json.dumps(detail, ensure_ascii=False, default=str),
                "outcome": "success" if status_code < 400 else "error",
            }

            import asyncio as _asyncio
            insert_fn = getattr(store, "store_audit_log", None)
            if insert_fn is not None:
                if _asyncio.iscoroutinefunction(insert_fn):
                    try:
                        _asyncio.run(insert_fn(**audit_data))
                    except RuntimeError:
                        pass
                else:
                    insert_fn(**audit_data)
        except Exception:
            pass
        return response

    # -- Error handlers -------------------------------------------------------
    @app.errorhandler(400)
    def bad_request(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Bad request", "status": 400}), 400

    @app.errorhandler(401)
    def unauthorized(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Unauthorized", "status": 401}), 401

    @app.errorhandler(403)
    def forbidden(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Forbidden", "status": 403}), 403

    @app.errorhandler(404)
    def not_found(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Not found", "status": 404}), 404

    @app.errorhandler(429)
    def rate_limited(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Rate limited", "status": 429}), 429

    @app.errorhandler(500)
    def server_error(_e: Any) -> tuple[Any, int]:
        return jsonify({"error": "Internal server error", "status": 500}), 500

    # -- Register blueprints --------------------------------------------------
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
    from . import routes_portfolio
    from . import routes_ops
    from . import routes_watchlist
    from . import routes_notifications
    from . import routes_alerts
    from . import routes_analysis
    from . import routes_admin
    from . import routes_daily
    from . import routes_strategy_monitor

    # -- 使用模式分组（仅标注，不拆分文件） --
    #   [summary] 轻量聚合，用于 dashboard 首屏
    #   [detail]  明细数据，按 symbol + start/end + interval + limit/offset 拉取
    #   [stream]  实时/准实时 SSE 或轮询
    #   [direct]  直接操作（下单、管理）

    # [summary]
    app.register_blueprint(routes_dashboard.bp,        url_prefix="/api/v1")
    app.register_blueprint(routes_data_health.bp,      url_prefix="/api/v1")
    app.register_blueprint(routes_market.bp,           url_prefix="/api/v1")
    app.register_blueprint(routes_watchlist.bp,        url_prefix="/api/v1")
    app.register_blueprint(routes_reports.bp,          url_prefix="/api/v1")
    app.register_blueprint(routes_ops.bp,              url_prefix="/api/v1")

    # [detail]
    app.register_blueprint(routes_data.bp,             url_prefix="/api/v1")
    app.register_blueprint(routes_backtest.bp,         url_prefix="/api/v1")
    app.register_blueprint(routes_market_data.bp,      url_prefix="/api/v1")
    app.register_blueprint(routes_screener.bp,         url_prefix="/api/v1")
    app.register_blueprint(routes_portfolio.bp,        url_prefix="/api/v1")
    app.register_blueprint(routes_analysis.bp,         url_prefix="/api/v1")
    app.register_blueprint(routes_notifications.bp,    url_prefix="/api/v1")
    app.register_blueprint(routes_alerts.bp,           url_prefix="/api/v1")
    app.register_blueprint(routes_daily.bp,            url_prefix="/api/v1")
    app.register_blueprint(routes_qmt.bp,              url_prefix="/api/v1")
    app.register_blueprint(routes_tv.bp,               url_prefix="/api/v1")
    app.register_blueprint(routes_strategy_monitor.bp, url_prefix="/api/v1")

    # [stream]
    app.register_blueprint(routes_sse.bp,              url_prefix="/api/v1")

    # [direct]
    app.register_blueprint(routes_paper.bp,            url_prefix="/api/v1")
    app.register_blueprint(routes_trade.bp,            url_prefix="/api/v1")
    app.register_blueprint(routes_ai_agent.bp,         url_prefix="/api/v1")
    app.register_blueprint(routes_admin.bp,            url_prefix="/api/v1")

    # -- Wire notification store & auto-start consumer ------------------------
    try:
        store = app.config.get("STORE")
        if store is not None:
            routes_notifications.set_notification_store(store)
            # Auto-start consumer if any channels exist
            with routes_notifications._channels_lock:
                if routes_notifications._channels:
                    routes_notifications._start_consumer()
                    logger.info("Notification consumer started with %d channels", len(routes_notifications._channels))
    except Exception as exc:
        logger.warning("Failed to initialize notification consumer: %s", exc)

    # -- Phase 17: Web UI (Jinja2) blueprint ---------------------------------
    from tradingagents.astock.web import bp as web_bp
    app.register_blueprint(web_bp)

    # -- Health check ---------------------------------------------------------
    @app.route("/api/v1/health")
    def health() -> tuple[Any, int]:
        status = backend_mgr.status()
        return jsonify({
            "status": "ok",
            "version": "0.2.5",
            "backend": status["backend"],
            "store_connected": status["duckdb_connected"] or status["postgresql_connected"],
        }), 200

    return app


__all__ = ["create_app", "DEFAULT_CORS_ORIGIN"]
