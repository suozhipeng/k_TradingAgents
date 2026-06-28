"""Self-contained migration runner for AStock Pro PostgreSQL database.

Usage:
    from tradingagents.astock.store.migrations import MigrationRunner

    runner = MigrationRunner(async_engine)
    await runner.discover()
    results = await runner.upgrade()
    df = await runner.status()
"""

from __future__ import annotations

from .runner import MigrationRunner

__all__ = ["MigrationRunner"]
