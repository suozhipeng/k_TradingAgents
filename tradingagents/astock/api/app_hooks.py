"""App-level hooks: ensure schema is initialised at startup."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA_INIT_LOCK = threading.Lock()


def ensure_schema_at_startup(app, store) -> None:
    """Initialise DuckDB schema idempotently. Runs once per process."""
    if not store:
        logger.warning("ensure_schema_at_startup called with no store")
        return
    try:
        store.conn.execute("PRAGMA tables('kline_bars')").fetchone()
    except Exception:
        with _SCHEMA_INIT_LOCK:
            try:
                store.migrate("kline_bars", "security_master", "trading_calendar")
                logger.info("DuckDB schema initialised at startup")
            except Exception as exc:
                logger.error("Failed to initialise schema: %s", exc)


def on_app_start(app):
    """Register on-start hooks: ensure schema exists."""
    store = getattr(app, "astock_store", None) or app.config.get("STORE")
    if store:
        ensure_schema_at_startup(app, store)


def register_hooks(app):
    """Install app lifecycle hooks (currently no-op in Flask, used by test scaffolding)."""
    # The actual bootstrap happens inside app_factory after create_app.
    pass
