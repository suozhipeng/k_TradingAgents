"""Connection, schema initialization, and storage-profile seeding."""

from __future__ import annotations

from .pg_common import *


class PGConnectionMixin:
    """Connection, schema initialization, and storage-profile seeding."""

    def __init__(self, config: PGConfig | None = None, sync: bool = False) -> None:
        self._config = config or PGConfig()
        self._sync = sync
        self._async_engine = None
        self._sync_engine = None
        self._async_session_factory = None
        self._connected = False

    # ---- connection management -----------------------------------------------

    async def connect(self) -> None:
        """Open the database connection pool and auto-create schema if needed."""
        if self._connected:
            return
        if self._sync:
            from sqlalchemy import create_engine

            self._sync_engine = create_engine(
                self._config.sync_dsn,
                poolclass=QueuePool,
                pool_size=self._config.pool_size,
                max_overflow=self._config.pool_size,
                pool_timeout=30,
                pool_recycle=3600,
                connect_args={"application_name": self._config.application_name},
            )
            # Test connection
            with self._sync_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()
        else:
            self._async_engine = create_async_engine(
                self._config.dsn,
                pool_size=self._config.pool_size,
                max_overflow=self._config.pool_size,
                pool_pre_ping=True,
                echo=False,
            )
            self._async_session_factory = async_sessionmaker(
                self._async_engine, class_=AsyncSession, expire_on_commit=False
            )
            # Test connection
            async with self._async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        self._connected = True
        logger.info(
            "Connected to PostgreSQL at %s:%s/%s (sync=%s)",
            self._config.host,
            self._config.port,
            self._config.database,
            self._sync,
        )

    async def close(self) -> None:
        """Close the database connection pool."""
        if self._async_engine is not None:
            await self._async_engine.dispose()
            self._async_engine = None
        if self._sync_engine is not None:
            self._sync_engine.dispose()
            self._sync_engine = None
        self._async_session_factory = None
        self._connected = False
        logger.info("Disconnected from PostgreSQL")

    # ---- schema --------------------------------------------------------------

    async def init_schema(self) -> None:
        """Create all tables and indexes if they don't exist."""
        if self._sync:
            Base.metadata.create_all(self._sync_engine)
            self._create_indexes_sync()
            self._seed_storage_profiles_sync()
        else:
            async with self._async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await self._create_indexes_async()
            await self._seed_storage_profiles_async()
        # Try to create TimescaleDB hypertable for kline_bars
        if self._config.use_timescaledb:
            await self._ensure_timescaledb_hypertable()
        # Auto-discover and register migration files
        self.discover_migrations()
        logger.info("Schema initialised (%d tables)", len(ALL_MODEL_CLASSES))

    async def _create_indexes_async(self) -> None:
        """Create all query-path indexes (async)."""
        async with self._async_engine.connect() as conn:
            for ddl in INDEX_DEFS.values():
                try:
                    await conn.execute(text(ddl))
                except Exception:
                    logger.warning("Index creation failed (may already exist): %s", ddl[:60])
            await conn.commit()

    def _create_indexes_sync(self) -> None:
        """Create all query-path indexes (sync)."""
        with self._sync_engine.connect() as conn:
            for ddl in INDEX_DEFS.values():
                try:
                    conn.execute(text(ddl))
                except Exception:
                    logger.warning("Index creation failed (may already exist): %s", ddl[:60])
            conn.commit()

    async def _ensure_timescaledb_hypertable(self) -> None:
        """Convert kline_bars to a TimescaleDB hypertable if the extension is available."""
        try:
            if self._sync:
                with self._sync_engine.connect() as conn:
                    result = conn.execute(
                        text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')")
                    )
                    has_timescaledb = result.scalar()
                    if has_timescaledb:
                        # Check if already a hypertable
                        exists = conn.execute(
                            text(
                                "SELECT EXISTS(SELECT 1 FROM _timescaledb_catalog.hypertable "
                                "WHERE table_name = 'kline_bars')"
                            )
                        ).scalar()
                        if not exists:
                            conn.execute(
                                text(
                                    "SELECT create_hypertable('kline_bars', 'bar_time', "
                                    "chunk_time_interval => INTERVAL '7 days', "
                                    "if_not_exists => TRUE)"
                                )
                            )
                            conn.commit()
                            logger.info("kline_bars converted to TimescaleDB hypertable")
                    conn.commit()
            else:
                async with self._async_engine.connect() as conn:
                    result = await conn.execute(
                        text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')")
                    )
                    has_timescaledb = result.scalar()
                    if has_timescaledb:
                        exists = await conn.execute(
                            text(
                                "SELECT EXISTS(SELECT 1 FROM _timescaledb_catalog.hypertable "
                                "WHERE table_name = 'kline_bars')"
                            )
                        )
                        if not exists.scalar():
                            await conn.execute(
                                text(
                                    "SELECT create_hypertable('kline_bars', 'bar_time', "
                                    "chunk_time_interval => INTERVAL '7 days', "
                                    "if_not_exists => TRUE)"
                                )
                            )
                            logger.info("kline_bars converted to TimescaleDB hypertable")
                    await conn.commit()
        except Exception as exc:
            logger.info("TimescaleDB hypertable creation skipped: %s", exc)

    def _seed_storage_profiles_sync(self) -> None:
        """Seed the database_storage_profiles table (sync)."""
        profiles = [
            {
                "profile_name": "postgresql_production_oltp",
                "role": "production_primary",
                "engine": "postgresql",
                "read_write_model": "multi-user transactional primary store",
                "notes": "Commercial primary database; TimescaleDB extension for time-series tables.",
            },
            {
                "profile_name": "duckdb_local_olap",
                "role": "local_cache_olap",
                "engine": "duckdb",
                "read_write_model": "single-writer analytical cache",
                "notes": "Use for local WebUI, research, backtest snapshots, and export/import.",
            },
            {
                "profile_name": "clickhouse_production_olap",
                "role": "production_analytics",
                "engine": "clickhouse",
                "read_write_model": "append-oriented analytical replica",
                "notes": "Recommended for high-volume historical market-data scans.",
            },
        ]
        with self._sync_engine.connect() as conn:
            for p in profiles:
                conn.execute(
                    text(
                        "INSERT INTO database_storage_profiles "
                        "(profile_name, role, engine, read_write_model, notes) "
                        "VALUES (:profile_name, :role, :engine, :read_write_model, :notes) "
                        "ON CONFLICT (profile_name) DO NOTHING"
                    ),
                    p,
                )
            conn.commit()

    async def _seed_storage_profiles_async(self) -> None:
        """Seed the database_storage_profiles table (async)."""
        profiles = [
            {
                "profile_name": "postgresql_production_oltp",
                "role": "production_primary",
                "engine": "postgresql",
                "read_write_model": "multi-user transactional primary store",
                "notes": "Commercial primary database; TimescaleDB extension for time-series tables.",
            },
            {
                "profile_name": "duckdb_local_olap",
                "role": "local_cache_olap",
                "engine": "duckdb",
                "read_write_model": "single-writer analytical cache",
                "notes": "Use for local WebUI, research, backtest snapshots, and export/import.",
            },
            {
                "profile_name": "clickhouse_production_olap",
                "role": "production_analytics",
                "engine": "clickhouse",
                "read_write_model": "append-oriented analytical replica",
                "notes": "Recommended for high-volume historical market-data scans.",
            },
        ]
        async with self._async_engine.connect() as conn:
            for p in profiles:
                await conn.execute(
                    text(
                        "INSERT INTO database_storage_profiles "
                        "(profile_name, role, engine, read_write_model, notes) "
                        "VALUES (:profile_name, :role, :engine, :read_write_model, :notes) "
                        "ON CONFLICT (profile_name) DO NOTHING"
                    ),
                    p,
                )
            await conn.commit()
