"""Flask app factory helpers for the A-stock API.

Contains the ``_build_store_config()`` helper that sets up the backend,
store, and quality-gated store — the first half of ``create_app()``.
"""

from __future__ import annotations

import logging
import os
import time

from flask import Flask

from tradingagents.astock.store.backend import backend_mgr

logger = logging.getLogger(__name__)


def _build_store_config(app: Flask, db_path: str | None = None) -> None:
    """Configure DB backend, store, and quality gate for the given app.

    Parameters
    ----------
    app : Flask
        The application instance (mutated in-place via ``app.config``).
    db_path : str or None
        Explicit DuckDB file path. When provided, bypasses the
        process-wide ``BackendManager`` and creates an isolated store.
    """
    app.config.setdefault(
        "ASTOCK_SHUTDOWN_TIMEOUT_SECONDS",
        float(os.environ.get("ASTOCK_SHUTDOWN_TIMEOUT_SECONDS", "5")),
    )

    # -- Backend selection via BackendManager ---------------------------------
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
    # Persist refresh progress so the formal Data Hub can show durable task
    # evidence rather than only process-local thread state.
    app.config["DATA_JOB_MANAGER"] = DataJobManager(
        store=raw_store,
        max_queued=int(app.config.get("ASTOCK_DATA_JOB_MAX_QUEUED", 100)),
    )

    # Data facade (router + loaders)
    try:
        from tradingagents.astock.data_sources.router import AStockDataFacade
        app.config["DATA_FACADE"] = AStockDataFacade()
    except Exception as exc:
        app.logger.warning("Failed to initialize DataFacade: %s", exc)
        app.config["DATA_FACADE"] = None

    # Record app start time for health-check uptime
    app.config["_START_TIME"] = time.time()


def _build_scheduler_config(app: Flask) -> None:
    """Auto-start PaperTradeScheduler with APScheduler (configurable)."""
    from ._helpers import _bool_config, _int_config

    try:
        from tradingagents.astock.execution.scheduler import PaperTradeScheduler as PTS

        enabled = _bool_config(app, "ASTOCK_SCHEDULER_ENABLED", True)
        paper_trader = app.config.get("PAPER_TRADER")
        # The scheduler is app-owned. Construct its paper-trader dependency
        # in the same app config instead of allowing a later request or the
        # execution module singleton to supply a process-shared instance.
        if enabled and paper_trader is None:
            from tradingagents.astock.execution.paper_trader import PaperTrader

            paper_trader = PaperTrader()
            app.config["PAPER_TRADER"] = paper_trader

        pts = PTS(
            paper_trader=paper_trader,
            store=app.config.get("STORE"),
            interval_minutes=_int_config(app, "ASTOCK_SCHEDULER_INTERVAL_MIN", 30),
            enabled=enabled,
        )
        pts.start()
        app.config["SCHEDULER"] = pts
    except Exception as exc:
        logger.warning("PaperTradeScheduler not started: %s", exc)
        app.config["SCHEDULER"] = None
