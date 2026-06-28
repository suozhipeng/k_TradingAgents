# V20260628_001__initial_schema.py
"""Initial schema creation — all core AStock tables and indexes.

This migration bootstraps the entire schema by delegating to
PGStore.init_schema(). It has no rollback SQL because dropping
all tables is destructive; use with caution.
"""

from __future__ import annotations

from sqlalchemy import text

version_id = "V20260628_001"
description = "Create initial schema (all tables, indexes, storage profiles)"
dependencies: list[str] = []


async def upgrade(engine):
    """Create all tables and indexes via Base.metadata.create_all."""
    from tradingagents.astock.store.pg_store import PGStore

    # Build a minimal PGStore instance to reuse init_schema().
    # We only need the engine, config, and sync flag.
    store = PGStore.__new__(PGStore)
    store._async_engine = engine
    store._sync = False
    store._sync_engine = None
    store._config = type("obj", (object,), {"use_timescaledb": False})()
    store._async_session_factory = None
    store._connected = True
    await store.init_schema()


async def downgrade(engine):
    """No automatic rollback — schema creation is not safely reversible.

    To drop all tables, use PGStore.drop_all_tables() explicitly.
    """
    pass
