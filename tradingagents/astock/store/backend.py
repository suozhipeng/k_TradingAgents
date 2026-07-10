"""Runtime database backend switch for AStock Pro.

Allows switching between DuckDB (local OLAP) and PostgreSQL (production
primary) without restarting the Flask process.  Config is persisted in
``~/.tradingagents/backend.json`` so the choice survives restarts.

Typical usage::

    from tradingagents.astock.store.backend import backend_mgr
    
    # At app startup
    create_app() reads backend_mgr.current_backend
    
    # Via API
    POST /api/v1/admin/backend  {"backend": "postgresql"}
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config path
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".tradingagents"
CONFIG_FILE = CONFIG_DIR / "backend.json"

# ---------------------------------------------------------------------------
# Backend config
# ---------------------------------------------------------------------------


@dataclass
class BackendConfig:
    """Serialisable backend configuration."""

    current_backend: str = "duckdb"  # "duckdb" | "postgresql"
    duckdb_path: str = "~/.tradingagents/astock/astock.duckdb"
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "astock"
    pg_user: str = "astock"
    pg_password: str = "astock"
    pg_pool_size: int = 20
    pg_use_timescaledb: bool = True
    mock_data_enabled: bool = False

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> BackendConfig:
        """Load from JSON file, falling back to defaults + env vars."""
        config = cls()

        # Env var overrides (highest priority at first load)
        config.current_backend = (
            os.environ.get("ASTOCK_DB_BACKEND", "duckdb").strip().lower()
        )
        config.duckdb_path = os.environ.get(
            "ASTOCK_DB_PATH", config.duckdb_path
        )
        config.pg_host = os.environ.get("PG_HOST", config.pg_host)
        try:
            config.pg_port = int(os.environ.get("PG_PORT", str(config.pg_port)))
        except (ValueError, TypeError):
            pass
        config.pg_database = os.environ.get("PG_DB", config.pg_database)
        config.pg_user = os.environ.get("PG_USER", config.pg_user)
        config.pg_password = os.environ.get("PG_PASSWORD", config.pg_password)
        try:
            config.pg_pool_size = int(
                os.environ.get("PG_POOL_SIZE", str(config.pg_pool_size))
            )
        except (ValueError, TypeError):
            pass
        config.pg_use_timescaledb = (
            os.environ.get("PG_USE_TIMESCALEDB", "true").lower() == "true"
        )
        config.mock_data_enabled = os.environ.get("ASTOCK_MOCK_DATA_ENABLED", "false").lower() in (
            "true", "1", "yes", "on"
        )

        # File overrides (lower priority, survives manual edit)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for k, v in data.items():
                    if hasattr(config, k) and v is not None:
                        setattr(config, k, v)
            except Exception as exc:
                logger.warning("Failed to load backend config: %s", exc)

        return config

    def save(self, path: Path = CONFIG_FILE) -> None:
        """Persist to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_backend": self.current_backend,
            "duckdb_path": self.duckdb_path,
            "pg_host": self.pg_host,
            "pg_port": self.pg_port,
            "pg_database": self.pg_database,
            "pg_user": self.pg_user,
            "pg_password": self.pg_password,
            "pg_pool_size": self.pg_pool_size,
            "pg_use_timescaledb": self.pg_use_timescaledb,
            "mock_data_enabled": self.mock_data_enabled,
        }


# ---------------------------------------------------------------------------
# Backend manager (singleton)
# ---------------------------------------------------------------------------


class BackendManager:
    """Runtime switchable database backend manager.

    Thread-safe.  Holds up to two store instances:
    - ``_duck_store`` — the DuckDB AStockStore (cheap, always available)
    - ``_pg_store`` — the PostgreSQL PGStore (only connected when switched)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._config: BackendConfig = BackendConfig.load()
        self._duck_store: Any = None
        self._pg_store: Any = None
        self._duck_initialised = False
        self._pg_initialised = False

    # -- properties ----------------------------------------------------------

    @property
    def current_backend(self) -> str:
        return self._config.current_backend

    @property
    def config(self) -> BackendConfig:
        return self._config

    # -- store accessors -----------------------------------------------------

    def get_store(self) -> Any:
        """Return the *active* store (DuckDB or PG depending on backend)."""
        if self._config.current_backend == "postgresql":
            return self.get_pg_store()
        return self.get_duck_store()

    def get_duck_store(self) -> Any:
        """Return the DuckDB store (lazy init)."""
        if not self._duck_initialised:
            with self._lock:
                if not self._duck_initialised:
                    from tradingagents.astock.store.schema import init_astock_db

                    self._duck_store = init_astock_db(self._config.duckdb_path)
                    self._duck_initialised = True
                    logger.info("DuckDB store initialised: %s", self._config.duckdb_path)
        return self._duck_store

    def get_pg_store(self) -> Any | None:
        """Return the PostgreSQL store (lazy connect).  Returns None if PG
        is unreachable or not configured."""
        if not self._pg_initialised:
            with self._lock:
                if not self._pg_initialised:
                    self._pg_store = self._connect_pg()
                    self._pg_initialised = True
        return self._pg_store

    def _connect_pg(self) -> Any | None:
        """Internal: initialise and connect PGStore."""
        try:
            from tradingagents.astock.store.pg_store import PGConfig, PGStore

            cfg = self._config
            config = PGConfig(
                host=cfg.pg_host,
                port=cfg.pg_port,
                database=cfg.pg_database,
                user=cfg.pg_user,
                password=cfg.pg_password,
                pool_size=cfg.pg_pool_size,
                use_timescaledb=cfg.pg_use_timescaledb,
            )
            store = PGStore(config, sync=True)
            # Use the same _run_async pattern as PGStore to avoid asyncio.run() nesting
            import asyncio

            def _do_connect():
                import asyncio as _asyncio
                try:
                    _loop = _asyncio.get_running_loop()
                except RuntimeError:
                    _loop = None
                if _loop is not None:
                    # Event loop already running — use thread executor
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        future = pool.submit(_asyncio.run, store.connect())
                        future.result()
                        future = pool.submit(_asyncio.run, store.init_schema())
                        future.result()
                else:
                    asyncio.run(store.connect())
                    asyncio.run(store.init_schema())

            _do_connect()
            logger.info(
                "PGStore connected: %s@%s:%s/%s",
                cfg.pg_user, cfg.pg_host, cfg.pg_port, cfg.pg_database,
            )
            return store
        except Exception as exc:
            logger.warning("PGStore connect failed: %s", exc)
            return None

    # -- switch --------------------------------------------------------------

    def switch_to(self, backend: str) -> dict[str, Any]:
        """Switch the active backend at runtime.

        Arguments:
            backend: ``"duckdb"`` or ``"postgresql"``

        Returns:
            ``{"backend": ..., "connected": bool, "message": ...}``
        """
        backend = backend.strip().lower()
        if backend not in ("duckdb", "postgresql"):
            return {
                "backend": self._config.current_backend,
                "connected": False,
                "message": f"Unknown backend: {backend!r}. Use 'duckdb' or 'postgresql'.",
            }

        with self._lock:
            if backend == self._config.current_backend:
                return {
                    "backend": backend,
                    "connected": True,
                    "message": f"Already on {backend} backend.",
                }

            if backend == "duckdb":
                # DuckDB is always available; just flip the switch
                self._config.current_backend = "duckdb"
                self._config.save()
                logger.info("Switched backend → duckdb")
                return {
                    "backend": "duckdb",
                    "connected": True,
                    "message": "Switched to DuckDB (local OLAP).",
                }

            # Switching to PostgreSQL — must connect
            pg = self._connect_pg()
            if pg is None:
                return {
                    "backend": self._config.current_backend,
                    "connected": False,
                    "message": "PostgreSQL unreachable. Check PG_HOST/PG_PORT/PG_DB/PG_USER/PG_PASSWORD.",
                }
            self._pg_store = pg
            self._pg_initialised = True
            self._config.current_backend = "postgresql"
            self._config.save()
            logger.info("Switched backend → postgresql")
            return {
                "backend": "postgresql",
                "connected": True,
                "message": "Switched to PostgreSQL/TimescaleDB (production).",
            }

    def status(self) -> dict[str, Any]:
        """Return a status dict for API consumption."""
        duck_ok = self._duck_initialised and self._duck_store is not None
        pg_ok = self._pg_initialised and self._pg_store is not None

        pg_info = {}
        if pg_ok and self._pg_store is not None:
            pg_info = {
                "host": self._config.pg_host,
                "port": self._config.pg_port,
                "database": self._config.pg_database,
            }

        return {
            "backend": self._config.current_backend,
            "duckdb_connected": duck_ok,
            "postgresql_connected": pg_ok,
            "postgresql": pg_info,
        }

    @property
    def backend_for_ch_sync(self) -> str:
        """Return the source key to pass to astock_sync_ch.py --source."""
        return self._config.current_backend


# ---------------------------------------------------------------------------
# Module-level singleton (imported by create_app and routes)
# ---------------------------------------------------------------------------

backend_mgr = BackendManager()
