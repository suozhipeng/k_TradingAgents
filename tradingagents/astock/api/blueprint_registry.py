"""Blueprint registration for the A-stock API.

Centralises all 27 blueprint imports and ``register_blueprint`` calls
into a single function so ``create_app()`` stays readable.

Blueprints are grouped by usage pattern (summary / detail / stream / direct)
matching the comments in the original ``api/__init__.py``.
"""

from __future__ import annotations

from flask import Flask


def register_blueprints(app: Flask) -> None:
    """Import and register all API blueprints."""

    # -- Import all route modules -----------------------------------------------
    from . import routes_data_query
    from . import routes_data_ingest
    from . import routes_data_jobs
    from . import routes_data_cache
    from . import routes_backtest
    from . import routes_paper
    from . import routes_market
    from . import routes_qmt
    from . import routes_sse
    from . import routes_scheduler
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

    # -- [summary]  lightweight aggregation, for dashboard first screen --------
    app.register_blueprint(routes_dashboard.bp,  url_prefix="/api/v1")
    app.register_blueprint(routes_data_health.bp, url_prefix="/api/v1")
    app.register_blueprint(routes_market.bp,     url_prefix="/api/v1")
    app.register_blueprint(routes_watchlist.bp,  url_prefix="/api/v1")
    app.register_blueprint(routes_reports.bp,    url_prefix="/api/v1")
    app.register_blueprint(routes_ops.bp,        url_prefix="/api/v1")

    # -- [detail]  detail data, per symbol + start/end + interval -----------
    app.register_blueprint(routes_data_query.bp,   url_prefix="/api/v1")
    app.register_blueprint(routes_data_ingest.bp,  url_prefix="/api/v1")
    app.register_blueprint(routes_data_jobs.bp,    url_prefix="/api/v1")
    app.register_blueprint(routes_data_cache.bp,   url_prefix="/api/v1")
    app.register_blueprint(routes_backtest.bp,     url_prefix="/api/v1")
    app.register_blueprint(routes_market_data.bp,  url_prefix="/api/v1")
    app.register_blueprint(routes_screener.bp,     url_prefix="/api/v1")
    app.register_blueprint(routes_portfolio.bp,    url_prefix="/api/v1")
    app.register_blueprint(routes_analysis.bp,     url_prefix="/api/v1")
    app.register_blueprint(routes_notifications.bp,url_prefix="/api/v1")
    app.register_blueprint(routes_alerts.bp,       url_prefix="/api/v1")
    app.register_blueprint(routes_daily.bp,        url_prefix="/api/v1")
    app.register_blueprint(routes_qmt.bp,          url_prefix="/api/v1")
    app.register_blueprint(routes_tv.bp,           url_prefix="/api/v1")
    app.register_blueprint(routes_strategy_monitor.bp, url_prefix="/api/v1")

    # -- [stream]  real-time/semi-real-time SSE or polling -------------------
    app.register_blueprint(routes_sse.bp,          url_prefix="/api/v1")
    app.register_blueprint(routes_scheduler.bp,    url_prefix="/api/v1")

    # -- [direct]  direct operations (orders, management) ---------------------
    app.register_blueprint(routes_paper.bp,        url_prefix="/api/v1")
    app.register_blueprint(routes_trade.bp,        url_prefix="/api/v1")
    app.register_blueprint(routes_ai_agent.bp,     url_prefix="/api/v1")
    app.register_blueprint(routes_admin.bp,        url_prefix="/api/v1")


def wire_notification_store(app: Flask) -> None:
    """Wire notification store and auto-start consumer after blueprints are registered."""
    from . import routes_notifications

    try:
        store = app.config.get("STORE")
        if store is not None:
            routes_notifications.set_notification_store(store)
            # Auto-start consumer if any channels exist
            with routes_notifications._channels_lock:
                if routes_notifications._channels:
                    routes_notifications._start_consumer()
                    app.logger.info("Notification consumer started with %d channels", len(routes_notifications._channels))
    except Exception as exc:
        app.logger.warning("Failed to initialize notification consumer: %s", exc)
