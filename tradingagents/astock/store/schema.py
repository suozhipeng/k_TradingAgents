"""DuckDB table definitions and AStockStore — the local database storage layer.

All tables use ``INSERT OR REPLACE`` semantics for upsert-style writes, with
``PRIMARY KEY`` constraints ensuring idempotent re-insertion.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

import duckdb
import pandas as pd

from . import schema_defs

logger = logging.getLogger(__name__)

# Supported kline intervals — from SSOT
SUPPORTED_KLINE_INTERVALS = schema_defs.SUPPORTED_KLINE_INTERVALS

# ---------------------------------------------------------------------------
# All tables in creation order — derived from schema_defs.py
# ---------------------------------------------------------------------------

ALL_TABLE_DEFS: dict[str, str] = {
    name: defn.create_ddl("duckdb")
    for name, defn in schema_defs.TABLE_DEFS.items()
}

# PostgreSQL index definitions — imported from schema_defs (SSOT)
INDEX_DEFS: dict[str, str] = schema_defs.DEFAULT_INDEX_DEFS.copy()

# Column name remaps from provider payloads → DuckDB column names
# (dataframe column -> table column)
KLINE_COLUMN_MAP: dict[str, str] = {
    "bar_time": "bar_time",
    "date": "bar_time",
    "datetime": "bar_time",
    "time": "bar_time",
    "trade_date": "trade_date",
    "symbol": "symbol",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
    "amount": "amount",
    "turnover": "turnover_rate",
    "turnover_rate": "turnover_rate",
    "interval": "interval",
    "adjust": "adjust",
    "quality": "quality",
    "source": "source",
}

# Common provider / CSV field variants.  Normalisation is deliberately kept at
# the Store boundary so manual import, concurrent refresh and local recovery
# all receive the same compatibility behaviour.
FIELD_ALIASES: dict[str, str] = {
    "日期": "bar_time", "交易日期": "trade_date", "时间": "bar_time",
    "开盘": "open", "最高": "high", "最低": "low", "收盘": "close",
    "成交量": "volume", "成交额": "amount", "换手率": "turnover_rate",
    "市盈率": "pe", "市净率": "pb", "总市值": "market_cap",
    "datetime": "bar_time", "timestamp": "bar_time", "date": "bar_time",
    "trade_date": "trade_date", "open_price": "open", "high_price": "high",
    "low_price": "low", "close_price": "close", "vol": "volume",
    "turnover": "turnover_rate", "market_value": "market_cap",
}

VALUATION_COLUMN_MAP: dict[str, str] = {
    "symbol": "symbol",
    "date": "trade_date",
    "trade_date": "trade_date",
    "pe": "pe",
    "pe_ttm": "pe",
    "pb": "pb",
    "market_cap": "market_cap",
    "market_value": "market_cap",
    "source": "source",
}

# ---------------------------------------------------------------------------
# AStockStore
# ---------------------------------------------------------------------------


class _ThreadSafeDuckDBResult:
    """Guard a DuckDB result cursor for the lifetime of a query result.

    ``DuckDBPyConnection.execute`` returns a cursor, and fetching from that
    cursor happens after ``execute`` has returned.  Locking only the execute
    call therefore leaves a race with another query or with store shutdown.
    This small proxy keeps the existing ``execute(...).fetchdf()`` API while
    serialising every cursor method and rejecting use after the owning
    connection has been closed.
    """

    def __init__(
        self,
        cursor: duckdb.DuckDBPyConnection,
        owner: "_ThreadSafeDuckDBConnection",
    ) -> None:
        self._cursor_value = cursor
        self._owner = owner

    def __getattr__(self, name: str) -> Any:
        with self._owner._lock:
            self._owner._ensure_open()
            target = getattr(self._cursor_value, name)
            if not callable(target):
                return target

        def _call(*args: Any, **kwargs: Any) -> Any:
            with self._owner._lock:
                self._owner._ensure_open()
                result = getattr(self._cursor_value, name)(*args, **kwargs)
                if isinstance(result, duckdb.DuckDBPyConnection):
                    return _ThreadSafeDuckDBResult(result, self._owner)
                return result

        return _call


class _ThreadSafeDuckDBConnection:
    """Serialize access to one DuckDB connection and its result cursors.

    DuckDB's Python connection object is shared by Flask request threads and
    data-job workers.  Every operation, including result fetching and close,
    uses the same store lock.  A fresh cursor is created per execute so a
    later query in the same thread cannot overwrite an earlier result.
    """

    def __init__(self, connection: duckdb.DuckDBPyConnection, lock: threading.RLock) -> None:
        self._connection = connection
        self._lock = lock
        self._closed = False
        self._local = threading.local()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("AStockStore connection is closed")

    def _new_cursor(self) -> duckdb.DuckDBPyConnection:
        self._ensure_open()
        return self._connection.cursor()

    def _cursor_for_execute(self) -> duckdb.DuckDBPyConnection:
        """Use a registration cursor when a dataframe is being inserted."""
        cursor = getattr(self._local, "registered_cursor", None)
        if cursor is not None:
            return cursor
        return self._new_cursor()

    def execute(self, query: str, parameters: Any = None) -> _ThreadSafeDuckDBResult:
        with self._lock:
            cursor = self._cursor_for_execute()
            if parameters is None:
                cursor.execute(query)
            else:
                cursor.execute(query, parameters)
            return _ThreadSafeDuckDBResult(cursor, self)

    def executemany(self, query: str, parameters: Any) -> _ThreadSafeDuckDBResult:
        with self._lock:
            cursor = self._cursor_for_execute()
            cursor.executemany(query, parameters)
            return _ThreadSafeDuckDBResult(cursor, self)

    def cursor(self) -> _ThreadSafeDuckDBResult:
        with self._lock:
            return _ThreadSafeDuckDBResult(self._new_cursor(), self)

    def register(self, name: str, obj: Any, *, replace: bool = False) -> _ThreadSafeDuckDBResult:
        with self._lock:
            cursor = getattr(self._local, "registered_cursor", None)
            if cursor is None:
                cursor = self._new_cursor()
            if replace:
                try:
                    cursor.unregister(name)
                except Exception:
                    pass
            cursor.register(name, obj)
            self._local.registered_cursor = cursor
            return _ThreadSafeDuckDBResult(cursor, self)

    def unregister(self, name: str) -> _ThreadSafeDuckDBResult:
        with self._lock:
            cursor = getattr(self._local, "registered_cursor", None)
            if cursor is None:
                cursor = self._new_cursor()
            try:
                cursor.unregister(name)
            finally:
                self._local.registered_cursor = None
            return _ThreadSafeDuckDBResult(cursor, self)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._connection.close()

    def __getattr__(self, name: str) -> Any:
        """Delegate uncommon connection attributes under the same lock."""
        if name.startswith("_"):
            raise AttributeError(name)

        def _call(*args: Any, **kwargs: Any) -> Any:
            with self._lock:
                self._ensure_open()
                target = getattr(self._connection, name)
                return target(*args, **kwargs)

        return _call


class AStockStore:
    """DuckDB-backed local database for A-share data.

    Uses ``:memory:`` (testing) or a file path for persistence.
    All write operations are thread-safe via an internal ``threading.Lock``.

    Parameters
    ----------
    db_path : str
        Path to DuckDB file. Use ``':memory:'`` for in-memory (testing).
    """

    def __init__(self, db_path: str = "~/.tradingagents/astock/astock.duckdb") -> None:
        resolved = os.path.expanduser(db_path)
        self._db_path = resolved
        self._conn: _ThreadSafeDuckDBConnection | None = None
        self._lock = threading.RLock()
        self._owns_conn = False

    def __getattribute__(self, name: str) -> Any:
        """Serialize public store methods around the shared DuckDB handle.

        The explicit method-level lock is intentionally centralised here so
        newly added store methods cannot silently bypass the concurrency
        contract.  ``RLock`` permits existing methods to call one another.
        Connection internals and properties are excluded; the connection
        proxy serializes its own operations.
        """
        attr = object.__getattribute__(self, name)
        if name.startswith("_") or name in {"conn", "db_path"} or not callable(attr):
            return attr
        lock = object.__getattribute__(self, "_lock")

        def _locked(*args: Any, **kwargs: Any) -> Any:
            with lock:
                return attr(*args, **kwargs)

        return _locked

    # ---- connection management -------------------------------------------

    @property
    def conn(self) -> _ThreadSafeDuckDBConnection:
        with self._lock:
            if self._conn is None:
                self.connect()
            assert self._conn is not None
            return self._conn

    @property
    def db_path(self) -> str:
        return self._db_path

    def connect(self) -> None:
        """Open (or reuse) the DuckDB connection."""
        with self._lock:
            if self._conn is not None:
                return
            if self._db_path != ":memory:":
                Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            raw_connection = duckdb.connect(self._db_path)
            self._conn = _ThreadSafeDuckDBConnection(raw_connection, self._lock)
            self._owns_conn = True

    def close(self) -> None:
        """Close the DuckDB connection if owned."""
        if self._conn is not None and self._owns_conn:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None
        self._owns_conn = False

    def __enter__(self) -> AStockStore:
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ---- schema ----------------------------------------------------------

    def init_schema(self) -> None:
        """Create the current production schema for a fresh database."""
        for ddl in ALL_TABLE_DEFS.values():
            self.conn.execute(ddl)
        self.create_indexes()
        self._seed_storage_profiles()
        # Auto-discover and register migration files
        self.discover_migrations()

    def _table_columns(self, table_name: str) -> list[str]:
        if not self.table_exists(table_name):
            return []
        return [
            str(row[1])
            for row in self.conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        ]

    def create_indexes(self) -> None:
        """Create query-path indexes for the production schema."""
        for ddl in INDEX_DEFS.values():
            self.conn.execute(ddl)

    def _seed_storage_profiles(self) -> None:
        """Record the intended commercial storage topology."""
        self.insert_table_rows(
            "database_storage_profiles",
            [
                {
                    "profile_name": "duckdb_local_olap",
                    "role": "local_cache_olap",
                    "engine": "duckdb",
                    "read_write_model": "single-writer analytical cache",
                    "notes": "Use for local WebUI, research, backtest snapshots, and export/import. Not the high-concurrency production write store.",
                },
                {
                    "profile_name": "postgresql_production_oltp",
                    "role": "production_primary",
                    "engine": "postgresql",
                    "read_write_model": "multi-user transactional primary store",
                    "notes": "Recommended commercial primary database; TimescaleDB extension can be layered on time-series tables.",
                },
                {
                    "profile_name": "clickhouse_production_olap",
                    "role": "production_analytics",
                    "engine": "clickhouse",
                    "read_write_model": "append-oriented analytical replica",
                    "notes": "Recommended for high-volume historical market-data scans after ingestion from the primary store.",
                },
            ],
        )

    # ── migration engine --------------------------------------------------

    def migrate(self, *names: str) -> list[dict[str, Any]]:
        """Apply a named, versioned migration if it has not been run before.

        Each migration is a ``(name, description, sql_or_none, rollback_sql_or_none)``
        entry defined in ``_MIGRATIONS``. After the SQL is executed (if any), a
        row is inserted into ``migration_versions``.

        If *names* is empty, all un-applied migrations are run in order.
        Returns a list of ``{version_id, description, status, duration_ms}`` records.
        """
        if not self.table_exists("migration_versions"):
            self.conn.execute(schema_defs.TABLE_DEFS["migration_versions"].create_ddl("duckdb"))

        applied = {
            str(row[0])
            for row in self.conn.execute(
                "SELECT version_id FROM migration_versions"
            ).fetchall()
        }

        results: list[dict[str, Any]] = []
        candidates = list(self._MIGRATIONS)
        if names:
            candidates = [n for n in candidates if n in names]
            missing = set(names) - {n for n in candidates}
            if missing:
                msg = f"Unknown migration(s): {missing}. Known: {list(self._MIGRATIONS)}"
                raise ValueError(msg)

        for vid, desc, sql, rollback_sql in candidates:
            if vid in applied:
                continue
            import time as _time
            t0 = _time.time()
            status = "applied"
            duration_ms = 0
            try:
                if sql:
                    self.conn.execute(sql)
                elapsed = _time.time() - t0
                duration_ms = int(round(elapsed * 1000))
            except Exception as exc:
                status = "failed"
                elapsed = _time.time() - t0
                duration_ms = int(round(elapsed * 1000))
                msg = f"Migration {vid!r} failed: {exc}"
                self.conn.execute(
                    "INSERT INTO migration_versions (version_id, description, status, duration_ms, checksum) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [vid, desc, status, duration_ms, repr(sql) if sql else ""],
                )
                raise RuntimeError(msg) from exc

            self.conn.execute(
                "INSERT INTO migration_versions (version_id, description, status, duration_ms, checksum, rollback_sql) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [vid, desc, status, duration_ms, repr(sql) if sql else "", rollback_sql],
            )
            results.append({
                "version_id": vid,
                "description": desc,
                "status": status,
                "duration_ms": duration_ms,
            })
        return results

    def list_migrations(self) -> pd.DataFrame:
        """Return all applied migration records."""
        return self.conn.execute(
            "SELECT * FROM migration_versions ORDER BY applied_at"
        ).fetchdf()

    def rollback_migration(self, version_id: str) -> None:
        """Roll back a previously applied migration if rollback_sql is set."""
        row = self.conn.execute(
            "SELECT rollback_sql FROM migration_versions WHERE version_id = ?",
            [version_id],
        ).fetchone()
        if row is None:
            raise ValueError(f"Migration {version_id!r} not found")
        if not row[0]:
            raise ValueError(f"Migration {version_id!r} has no rollback SQL defined")
        self.conn.execute(row[0])
        self.conn.execute("DELETE FROM migration_versions WHERE version_id = ?", [version_id])

    # Defined as class variable for discoverability — (version_id, description, sql, rollback_sql)
    _MIGRATIONS: list[tuple[str, str, str | None, str | None]] = []

    def discover_migrations(self, migrations_dir: str | None = None) -> int:
        """Auto-discover migration files from the migrations/ directory.

        Scans for ``V{YYYYMMDD}_{NNN}__{name}.py`` files, extracts the
        ``version_id``, ``description``, ``upgrade_sql``, and ``rollback_sql``
        attributes, and registers them in ``_MIGRATIONS``.

        Returns the number of migrations discovered.
        """
        if migrations_dir is None:
            migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
        mig_dir = Path(migrations_dir)
        if not mig_dir.is_dir():
            return 0

        import re

        pattern = re.compile(r"^V(\d{8})_(\d{3})__(.+)\.py$")
        discovered: dict[str, tuple[str, str, str | None, str | None]] = {}
        for fpath in sorted(mig_dir.iterdir()):
            if not fpath.is_file() or not fpath.name.endswith(".py"):
                continue
            m = pattern.match(fpath.name)
            if not m:
                continue
            version_id = f"V{m.group(1)}_{m.group(2)}"
            name_part = m.group(3)
            content = fpath.read_text(encoding="utf-8")

            description = name_part.replace("_", " ").title()
            ds_match = re.search(r'^\s*description\s*=\s*"([^"]*)"', content, re.MULTILINE)
            if ds_match:
                description = ds_match.group(1)

            # Migration files may expose callable upgrade()/downgrade()
            # functions whose docstrings are prose, not executable SQL.  Only
            # explicit SQL assignments belong in this tuple-based adapter.
            upgrade_sql = None
            sql_assign = re.search(r'(?:upgrade_sql|ddl)\s*=\s*"""(.*?)"""', content, re.DOTALL)
            if sql_assign:
                upgrade_sql = sql_assign.group(1).strip() or None

            rollback_sql = None
            sql_assign = re.search(r'(?:rollback_sql|rollback_ddl)\s*=\s*"""(.*?)"""', content, re.DOTALL)
            if sql_assign:
                rollback_sql = sql_assign.group(1).strip() or None

            discovered[version_id] = (version_id, description, upgrade_sql, rollback_sql)

        # ``_MIGRATIONS`` historically lived on the class, so every store
        # instance appended the same file again.  Replace discovered versions
        # atomically and retain only explicitly registered custom migrations.
        existing = [entry for entry in self._MIGRATIONS if entry[0] not in discovered]
        self._MIGRATIONS = sorted(existing + list(discovered.values()), key=lambda x: x[0])
        return len(discovered)

    # ── schema ----------------------------------------------------------

    def schema_sql(self, target: str = "duckdb") -> str:
        """Return DDL for the current schema.

        ``duckdb`` is executable locally. ``postgresql`` is a production-primary
        starting point that preserves table names, keys, checks, and indexes.
        """
        target_normalized = str(target or "duckdb").lower()
        if target_normalized not in ("duckdb", "postgresql"):
            raise ValueError("target must be one of: duckdb, postgresql")
        statements = list(ALL_TABLE_DEFS.values()) + list(INDEX_DEFS.values())
        sql = ";\n\n".join(stmt.strip().rstrip(";") for stmt in statements) + ";\n"
        if target_normalized == "duckdb":
            return sql
        replacements = {
            "DOUBLE": "DOUBLE PRECISION",
            "VARCHAR": "TEXT",
            "CREATE INDEX IF NOT EXISTS": "CREATE INDEX IF NOT EXISTS",
        }
        for old, new in replacements.items():
            sql = sql.replace(old, new)
        return sql

    def drop_all_tables(self) -> None:
        """Drop all managed tables (for test teardown)."""
        for table_name in ALL_TABLE_DEFS:
            self.conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        result = self.conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
            [table_name],
        ).fetchone()
        return result is not None and result[0] > 0

    def list_symbols(self, table_name: str | None = None) -> list[str]:
        """Return known symbols from managed tables.

        If *table_name* is omitted, all managed tables with a ``symbol`` column
        are scanned and the result is de-duplicated.
        """
        tables = [table_name] if table_name else list(ALL_TABLE_DEFS)
        symbols: set[str] = set()
        for table in tables:
            if not table or table not in ALL_TABLE_DEFS or not self.table_exists(table):
                continue
            try:
                columns = {
                    str(row[1])
                    for row in self.conn.execute(f'PRAGMA table_info("{table}")').fetchall()
                }
                if "symbol" not in columns:
                    continue
                rows = self.conn.execute(
                    f'SELECT DISTINCT symbol FROM "{table}" WHERE symbol IS NOT NULL'
                ).fetchall()
                symbols.update(str(row[0]) for row in rows if row and row[0])
            except Exception:
                continue
        return sorted(symbols)

    # ── audit log ---------------------------------------------------------

    def store_audit_log(
        self,
        event_type: str,
        action: str,
        *,
        actor: str | None = None,
        actor_ip: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        detail: dict[str, Any] | None = None,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        outcome: str = "success",
    ) -> str:
        """Write an audit event to the audit_log table. Returns the event_id."""
        import uuid, json
        event_id = uuid.uuid4().hex
        self.conn.execute(
            "INSERT INTO audit_log "
            "(event_id, event_type, actor, actor_ip, resource_type, resource_id, "
            " action, detail_json, old_value_json, new_value_json, outcome) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                event_id,
                event_type,
                actor,
                actor_ip,
                resource_type,
                resource_id,
                action,
                json.dumps(detail, ensure_ascii=False) if detail else None,
                json.dumps(old_value, ensure_ascii=False) if old_value else None,
                json.dumps(new_value, ensure_ascii=False) if new_value else None,
                outcome,
            ],
        )
        return event_id

    def query_audit_log(
        self,
        *,
        actor: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        """Search audit log with optional filters."""
        sql = "SELECT * FROM audit_log WHERE 1=1"
        params: list[Any] = []
        if actor:
            sql += " AND actor = ?"
            params.append(actor)
        if resource_type:
            sql += " AND resource_type = ?"
            params.append(resource_type)
        if resource_id:
            sql += " AND resource_id = ?"
            params.append(resource_id)
        if event_type:
            sql += " AND event_type = ?"
            params.append(event_type)
        sql += " ORDER BY event_time DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(sql, params).fetchdf()

    # ── API keys ----------------------------------------------------------

    def add_api_key(
        self,
        *,
        key_hash: str,
        key_prefix: str = "",
        label: str = "",
        role: str = "readonly",
        owner: str = "",
        allowed_capabilities: str = "",
        rate_limit: int = 100,
        expires_at: str | None = None,
    ) -> str:
        """Register an API key hash. Returns key_id."""
        import uuid
        key_id = uuid.uuid4().hex
        self.conn.execute(
            "INSERT INTO api_keys (key_id, key_hash, key_prefix, label, role, owner, "
            "allowed_capabilities, rate_limit, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [key_id, key_hash, key_prefix, label, role, owner,
             allowed_capabilities, rate_limit, expires_at],
        )
        return key_id

    def revoke_api_key(self, key_id: str) -> None:
        """Soft-revoke an API key."""
        self.conn.execute(
            "UPDATE api_keys SET is_active = FALSE WHERE key_id = ?", [key_id]
        )

    def validate_api_key(self, key_hash: str) -> dict[str, Any] | None:
        """Check if a key hash is valid and active. Returns key record or None."""
        row = self.conn.execute(
            "SELECT key_id, role, allowed_capabilities, rate_limit, expires_at "
            "FROM api_keys WHERE key_hash = ? AND is_active = TRUE "
            "AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)",
            [key_hash],
        ).fetchone()
        if row is None:
            return None
        record = {
            "key_id": str(row[0]),
            "role": str(row[1]),
            "allowed_capabilities": str(row[2]) if row[2] else "",
            "rate_limit": int(row[3]) if row[3] else 100,
        }
        # Update last_used_at
        self.conn.execute(
            "UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE key_id = ?",
            [record["key_id"]],
        )
        return record

    # ── data quality rules ------------------------------------------------

    def store_quality_rule(
        self,
        *,
        rule_name: str,
        description: str = "",
        scope_dataset: str = "",
        scope_interval: str = "",
        check_sql: str = "",
        severity: str = "warn",
        is_active: bool = True,
        cooldown_minutes: int = 0,
    ) -> str:
        """Register a data quality rule. Returns rule_id."""
        import uuid
        rule_id = uuid.uuid4().hex
        self.conn.execute(
            "INSERT INTO data_quality_rules "
            "(rule_id, rule_name, description, scope_dataset, scope_interval, "
            " check_sql, severity, is_active, cooldown_minutes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [rule_id, rule_name, description, scope_dataset, scope_interval,
             check_sql, severity, is_active, cooldown_minutes],
        )
        return rule_id

    def run_quality_rule(
        self, rule_id: str, *, dry_run: bool = False
    ) -> dict[str, Any]:
        """Execute a single quality rule and store results.

        Returns ``{rule_id, status, matched, failed, details}``.
        """
        rule = self.conn.execute(
            "SELECT rule_name, check_sql, severity FROM data_quality_rules "
            "WHERE rule_id = ? AND is_active = TRUE",
            [rule_id],
        ).fetchone()
        if rule is None:
            raise ValueError(f"Quality rule {rule_id!r} not found or inactive")
        rule_name, check_sql, severity = str(rule[0]), str(rule[1] or ""), str(rule[2])
        if not check_sql:
            raise ValueError(f"Quality rule {rule_id!r} has no check_sql defined")

        try:
            result_df = self.conn.execute(check_sql).fetchdf()
            row_count = len(result_df)
            failed = int(result_df.iloc[0]["violations"]) if not result_df.empty and "violations" in result_df.columns else row_count
            status = "pass" if failed == 0 else severity
        except Exception as exc:
            result_df = pd.DataFrame()
            status = "error"
            failed = -1
            row_count = 0
            _ = exc  # suppress unused

        # quarantine bad rows if violations found and not dry_run
        quarantined = 0
        if not dry_run and failed > 0 and not result_df.empty:
            for _, row in result_df.iterrows():
                self.store_quarantine(
                    source_dataset=rule_name.split(":")[0] if ":" in rule_name else "unknown",
                    symbol=str(row.get("symbol", "")),
                    interval=str(row.get("interval", "")),
                    reason=f"Quality rule {rule_name} failed",
                    rule_id=rule_id,
                    original_values=row.to_dict(),
                    severity=severity,
                )
                quarantined += 1

        self.conn.execute(
            "UPDATE data_quality_rules SET last_run_at = CURRENT_TIMESTAMP, "
            "last_result = ?, failure_count = failure_count + ? "
            "WHERE rule_id = ?",
            [status, max(failed, 0), rule_id],
        )

        self.store_data_quality_check({
            "dataset": rule_name,
            "rule_version": rule_id,
            "status": status,
            "invalid_count": max(failed, 0),
            "details": {"rows_checked": row_count, "severity": severity},
        })

        return {"rule_id": rule_id, "status": status, "matched": row_count, "failed": failed, "quarantined": quarantined}

    def run_all_quality_rules(self) -> list[dict[str, Any]]:
        """Run all active quality rules and return results."""
        rules = self.conn.execute(
            "SELECT rule_id FROM data_quality_rules WHERE is_active = TRUE"
        ).fetchall()
        results = []
        for (rule_id,) in rules:
            try:
                results.append(self.run_quality_rule(rule_id))
            except Exception as exc:
                results.append({"rule_id": rule_id, "status": "error", "error": str(exc)})
        return results

    # ── data quarantine ---------------------------------------------------

    def store_quarantine(
        self,
        *,
        source_dataset: str,
        symbol: str = "",
        interval: str = "",
        bar_time: str | None = None,
        trade_date: str | None = None,
        reason: str = "",
        rule_id: str | None = None,
        original_values: dict[str, Any] | None = None,
        severity: str = "warn",
    ) -> str:
        """Move anomalous data into the quarantine zone. Returns quarantine_id."""
        import uuid, json
        quarantine_id = uuid.uuid4().hex
        with self._lock:
            self.conn.execute(
                "INSERT INTO data_quarantine "
                "(quarantine_id, source_dataset, symbol, interval, bar_time, trade_date, "
                " reason, rule_id, original_values_json, severity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    quarantine_id, source_dataset, symbol or None, interval or None,
                    bar_time, trade_date, reason, rule_id,
                    json.dumps(original_values, ensure_ascii=False, default=str) if original_values else "{}",
                    severity,
                ],
            )
        return quarantine_id

    def store_quarantine_batch(self, rows: list[dict[str, Any]]) -> int:
        """Persist quarantine rows in one transaction for malformed imports."""
        if not rows:
            return 0
        import json
        import uuid

        values = [
            [
                uuid.uuid4().hex, item.get("source_dataset", ""), item.get("symbol") or None,
                item.get("interval") or None, item.get("bar_time"), item.get("trade_date"),
                item.get("reason", ""), item.get("rule_id"),
                json.dumps(item.get("original_values") or {}, ensure_ascii=False, default=str),
                item.get("severity", "warn"),
            ]
            for item in rows
        ]
        with self._lock:
            self.conn.executemany(
                "INSERT INTO data_quarantine "
                "(quarantine_id, source_dataset, symbol, interval, bar_time, trade_date, "
                " reason, rule_id, original_values_json, severity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values,
            )
        return len(values)

    def resolve_quarantine(
        self, quarantine_id: str, *, resolved_by: str = "system"
    ) -> None:
        """Mark a quarantined record as resolved (data was fixed or reviewed)."""
        self.conn.execute(
            "UPDATE data_quarantine SET resolution = 'resolved', resolved_by = ?, "
            "resolved_at = CURRENT_TIMESTAMP WHERE quarantine_id = ?",
            [resolved_by, quarantine_id],
        )

    def query_quarantine(
        self, *, severity: str | None = None, resolution: str = "unresolved", limit: int = 100
    ) -> pd.DataFrame:
        sql = "SELECT * FROM data_quarantine WHERE resolution = ?"
        params: list[Any] = [resolution]
        if severity:
            sql += " AND severity = ?"
            params.append(severity)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(sql, params).fetchdf()

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _df_from_rows(
        rows: pd.DataFrame | list[dict[str, Any]], column_map: dict[str, str]
    ) -> pd.DataFrame:
        """Normalise rows (DataFrame or list of dicts) into a DataFrame whose
        columns are the DuckDB column names (mapped via *column_map*)."""
        if isinstance(rows, pd.DataFrame):
            if rows.empty:
                return pd.DataFrame()
            df = rows.copy()
        elif isinstance(rows, list):
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows)
        else:
            return pd.DataFrame()
        # Normalise whitespace/case and well-known provider/CSV aliases before
        # applying the table-specific map.
        rename = {}
        for src_col in df.columns:
            raw = str(src_col).strip()
            normalized = raw.lower().replace(" ", "_").replace("-", "_")
            # A table-specific exact mapping (notably valuation ``date``) has
            # precedence over generic aliases.
            if raw in column_map:
                rename[src_col] = column_map[raw]
                continue
            if normalized in column_map:
                rename[src_col] = column_map[normalized]
                continue
            canonical = FIELD_ALIASES.get(raw, FIELD_ALIASES.get(normalized, normalized))
            if canonical in column_map:
                rename[src_col] = column_map[canonical]
            elif canonical in column_map.values():
                rename[src_col] = canonical
        if rename:
            df = df.rename(columns=rename)
        # Drop duplicate columns after rename (e.g. ``date`` + ``datetime`` both → ``bar_time``)
        df = df.loc[:, ~df.columns.duplicated()]
        # Keep only columns that exist in the column_map *values*
        target_cols = set(column_map.values())
        cols_to_keep = [c for c in df.columns if c in target_cols]
        df = df[cols_to_keep]
        return df

    def _coerce_kline_write_rows(
        self, df: pd.DataFrame, *, symbol: str, interval: str, source: str
    ) -> pd.DataFrame:
        """Quarantine incompatible K-line rows while retaining valid rows."""
        df = df.copy()
        for column in ("open", "high", "low", "close", "volume", "amount", "turnover_rate"):
            if column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")
        required = [column for column in ("bar_time", "open", "high", "low", "close") if column in df.columns]
        if required:
            invalid = df[required].isna().any(axis=1)
            quarantine_rows = []
            for _, row in df.loc[invalid].iterrows():
                bad_fields = [field for field in required if pd.isna(row.get(field))]
                reason = "incompatible required K-line field(s): {0}".format(", ".join(bad_fields))
                bar_time = row.get("bar_time")
                trade_date = row.get("trade_date")
                quarantine_rows.append({
                    "source_dataset": "kline_bars", "symbol": symbol, "interval": interval,
                    "bar_time": None if pd.isna(bar_time) else str(bar_time),
                    "trade_date": None if pd.isna(trade_date) else str(trade_date),
                    "reason": reason, "rule_id": "field_compatibility",
                    "original_values": {**row.to_dict(), "source": source}, "severity": "error",
                })
            quarantined = self.store_quarantine_batch(quarantine_rows)
            if quarantined:
                logger.error(
                    "KLINE_FIELD_EXCEPTION symbol=%s interval=%s quarantined_rows=%d",
                    symbol, interval, quarantined,
                )
            df = df.loc[~invalid].copy()
        return df

    @staticmethod
    def _canonicalise_dates(df: pd.DataFrame, date_cols: list[str]) -> pd.DataFrame:
        """Convert date-like columns to ``datetime.date``."""
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
        return df

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        """Return a safely quoted SQL identifier."""
        return '"' + str(identifier).replace('"', '""') + '"'

    @staticmethod
    def _normalise_interval(interval: str) -> str:
        value = str(interval or "1d").strip().lower()
        aliases = {
            "1min": "1m",
            "5min": "5m",
            "15min": "15m",
            "30min": "30m",
            "60min": "60m",
            "day": "1d",
            "daily": "1d",
            "week": "1w",
            "weekly": "1w",
            "month": "1mo",
            "monthly": "1mo",
            "year": "1y",
            "yearly": "1y",
            "1mth": "1mo",
        }
        value = aliases.get(value, value)
        if value not in SUPPORTED_KLINE_INTERVALS:
            supported = ", ".join(sorted(SUPPORTED_KLINE_INTERVALS))
            raise ValueError(f"Unsupported kline interval: {interval!r}. Supported: {supported}")
        return value

    @staticmethod
    def _normalise_kline_times(df: pd.DataFrame) -> pd.DataFrame:
        """Populate bar_time and trade_date for date/minute kline rows."""
        df = df.copy()
        if "bar_time" not in df.columns:
            for source_col in ("datetime", "time", "date", "trade_date"):
                if source_col in df.columns:
                    df["bar_time"] = df[source_col]
                    break
        if "bar_time" in df.columns:
            bar_time = pd.to_datetime(df["bar_time"], errors="coerce")
            df["bar_time"] = bar_time
            if "trade_date" not in df.columns:
                df["trade_date"] = bar_time.dt.date
            else:
                trade_date = pd.to_datetime(df["trade_date"], errors="coerce")
                df["trade_date"] = trade_date.fillna(bar_time).dt.date
        elif "trade_date" in df.columns:
            trade_date = pd.to_datetime(df["trade_date"], errors="coerce")
            df["trade_date"] = trade_date.dt.date
            df["bar_time"] = trade_date
        else:
            raise ValueError("kline rows require bar_time, date, datetime, time, or trade_date")
        return df

    # ---- batch insert (INSERT OR REPLACE) --------------------------------

    def _insert_df(
        self, table: str, df: pd.DataFrame, column_map: dict[str, str]
    ) -> int:
        """Normalise *df* via ``column_map`` and execute INSERT OR REPLACE.

        Returns the number of rows affected.
        """
        if df.empty:
            return 0
        normalised = self._df_from_rows(df, column_map)
        if normalised.empty:
            return 0
        # Build explicit column list matching the DataFrame columns
        # This avoids positional-mismatch errors and skips auto-generated columns
        # like ``created_at`` (which has DEFAULT CURRENT_TIMESTAMP in the DDL).
        cols = ", ".join(f'"{c}"' for c in normalised.columns)
        with self._lock:
            self.conn.register("_tmp_df", normalised)
            row_count = self.conn.execute(
                f'INSERT OR REPLACE INTO "{table}" ({cols}) SELECT * FROM _tmp_df'
            ).fetchone()
            self.conn.unregister("_tmp_df")
        return (row_count[0] if row_count else 0) if row_count else 0

    def insert_table_rows(self, table_name: str, rows: pd.DataFrame | list[dict[str, Any]]) -> int:
        """Insert or replace rows into a managed table.

        This is the generic entry point used by manual data-entry APIs. Unknown
        columns are dropped; DuckDB constraints still enforce required primary
        keys and data types.
        """
        if table_name not in ALL_TABLE_DEFS:
            msg = f"Unknown table: {table_name}. Known: {list(ALL_TABLE_DEFS)}"
            raise ValueError(msg)
        if isinstance(rows, pd.DataFrame):
            df = rows.copy()
        else:
            df = pd.DataFrame(rows)
        if df.empty:
            return 0
        if table_name == "kline_bars":
            if "interval" in df.columns:
                df["interval"] = df["interval"].fillna("1d").map(self._normalise_interval)
            else:
                df["interval"] = "1d"
            if "adjust" not in df.columns:
                df["adjust"] = "none"
            if "quality" not in df.columns:
                df["quality"] = "normal"
            df = self._normalise_kline_times(df)
        columns = [
            str(row[1])
            for row in self.conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            if str(row[1]) != "created_at"
        ]
        normalised = df[[column for column in df.columns if column in columns]].copy()
        if normalised.empty:
            return 0
        for date_col in (
            "trade_date",
            "report_date",
            "publish_date",
            "list_date",
            "delist_date",
            "effective_date",
            "end_date",
            "start_date",
            "action_date",
            "ex_date",
        ):
            if date_col in normalised.columns:
                normalised[date_col] = pd.to_datetime(normalised[date_col], errors="coerce").dt.date
        for ts_col in ("timestamp", "bar_time", "start_time", "end_time", "created_at", "updated_at"):
            if ts_col in normalised.columns:
                normalised[ts_col] = pd.to_datetime(normalised[ts_col], errors="coerce")
        cols = ", ".join(f'"{c}"' for c in normalised.columns)
        with self._lock:
            self.conn.register("_tmp_manual_df", normalised)
            row_count = self.conn.execute(
                f'INSERT OR REPLACE INTO "{table_name}" ({cols}) SELECT * FROM _tmp_manual_df'
            ).fetchone()
            self.conn.unregister("_tmp_manual_df")
        return row_count[0] if row_count else 0

    def replace_watchlist(self, items: list[dict[str, Any]]) -> int:
        """Atomically replace the schema-managed local watchlist."""
        with self._lock:
            self.conn.execute("DELETE FROM watchlist")
            for item in items:
                self.conn.execute(
                    "INSERT INTO watchlist (symbol, name, added_at, source) VALUES (?, ?, ?, ?)",
                    [
                        item["symbol"], item.get("name", item["symbol"]),
                        item.get("added_at"), item.get("source", "manual"),
                    ],
                )
        return len(items)

    # ---- kline -----------------------------------------------------------

    def insert_kline(
        self, symbol: str, df: pd.DataFrame, interval: str = "1d", source: str = ""
    ) -> int:
        """Batch insert/replace kline bars for *symbol*."""
        if df.empty:
            return 0
        df = self._df_from_rows(df, KLINE_COLUMN_MAP)
        if df.empty:
            return 0
        interval = self._normalise_interval(interval)
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "interval" not in df.columns:
            df["interval"] = interval
        else:
            df["interval"] = df["interval"].fillna(interval).map(self._normalise_interval)
        if "adjust" not in df.columns:
            df["adjust"] = "none"
        if "quality" not in df.columns:
            df["quality"] = "normal"
        if "source" not in df.columns:
            df["source"] = source
        df = self._normalise_kline_times(df)
        df = self._coerce_kline_write_rows(df, symbol=symbol, interval=interval, source=source)
        if df.empty:
            return 0
        return self._insert_df("kline_bars", df, KLINE_COLUMN_MAP)

    def query_kline(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
        limit: int | None = None,
        include_cold: bool = False,
    ) -> pd.DataFrame:
        """Return kline bars as a DataFrame, sorted by bar_time (ascending).

        When *limit* is set, the SQL-level query uses a **descending** subquery
        with ``LIMIT N``, then re-wraps in an outer ``ORDER BY bar_time ASC`` so
        that the caller always receives chronologically ordered data regardless
        of whether a pushdown limit was applied.
        """
        interval = self._normalise_interval(interval)
        source = "kline_bars"
        if include_cold:
            try:
                self.conn.execute("SELECT 1 FROM kline_bars_cold LIMIT 0")
                source = "(SELECT * FROM kline_bars UNION ALL SELECT * FROM kline_bars_cold) AS all_kline_bars"
            except Exception:
                pass
        inner = f'SELECT * FROM {source} WHERE symbol = ? AND "interval" = ?'
        params: list[Any] = [symbol, interval]
        if start:
            inner += " AND bar_time >= ?"
            params.append(start)
        if end:
            inner += " AND bar_time <= ?"
            params.append(end)

        if limit is not None and limit > 0:
            # Descending limit pushdown → outer re-sort
            inner += " ORDER BY bar_time DESC LIMIT ?"
            params.append(limit)
            sql = f"SELECT * FROM ({inner}) sub ORDER BY bar_time ASC"
        else:
            sql = inner + " ORDER BY bar_time"

        return self.conn.execute(sql, params).fetchdf()

    # ---- valuations ------------------------------------------------------

    def insert_valuations(
        self, symbol: str, df: pd.DataFrame, source: str = ""
    ) -> int:
        """Batch insert/replace valuation data for *symbol*."""
        if df.empty:
            return 0
        df = self._df_from_rows(df, VALUATION_COLUMN_MAP)
        if df.empty:
            return 0
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        df = self._canonicalise_dates(df, ["trade_date", "date"])
        return self._insert_df("valuations", df, VALUATION_COLUMN_MAP)

    def query_valuations(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """Return valuations as a DataFrame, sorted by trade_date."""
        sql = "SELECT * FROM valuations WHERE symbol = ?"
        params: list[Any] = [symbol]
        if start:
            sql += " AND trade_date >= ?"
            params.append(start)
        if end:
            sql += " AND trade_date <= ?"
            params.append(end)
        sql += " ORDER BY trade_date"
        return self.conn.execute(sql, params).fetchdf()

    # ---- order book snapshots --------------------------------------------

    def insert_order_book_snapshot(
        self, symbol: str, df: pd.DataFrame, source: str = ""
    ) -> int:
        """Batch insert/replace order book snapshots for *symbol*."""
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        return self._insert_df("order_book_snapshots", df, {
            "symbol": "symbol",
            "timestamp": "timestamp",
            "bid_price": "bid_price",
            "bid_volume": "bid_volume",
            "ask_price": "ask_price",
            "ask_volume": "ask_volume",
            "source": "source",
        })

    def query_order_book(
        self, symbol: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        sql = "SELECT * FROM order_book_snapshots WHERE symbol = ?"
        params: list[Any] = [symbol]
        if start:
            sql += " AND timestamp >= ?"
            params.append(start)
        if end:
            sql += " AND timestamp <= ?"
            params.append(end)
        sql += " ORDER BY timestamp"
        return self.conn.execute(sql, params).fetchdf()

    # ---- trade tape ------------------------------------------------------

    def insert_trade_tape(self, symbol: str, df: pd.DataFrame, source: str = "") -> int:
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        return self._insert_df("trade_tape", df, {
            "symbol": "symbol",
            "timestamp": "timestamp",
            "price": "price",
            "volume": "volume",
            "direction": "direction",
            "source": "source",
        })

    def query_trade_tape(
        self, symbol: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        sql = "SELECT * FROM trade_tape WHERE symbol = ?"
        params: list[Any] = [symbol]
        if start:
            sql += " AND timestamp >= ?"
            params.append(start)
        if end:
            sql += " AND timestamp <= ?"
            params.append(end)
        sql += " ORDER BY timestamp"
        return self.conn.execute(sql, params).fetchdf()

    # ---- research reports -------------------------------------------------

    def insert_research_reports(
        self, symbol: str, df: pd.DataFrame, source: str = ""
    ) -> int:
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        df = self._canonicalise_dates(df, ["report_date", "date"])
        return self._insert_df("research_reports", df, {
            "symbol": "symbol",
            "report_date": "report_date",
            "title": "title",
            "institution": "institution",
            "analyst": "analyst",
            "rating": "rating",
            "pdf_url": "pdf_url",
            "source": "source",
        })

    def query_research_reports(self, symbol: str) -> pd.DataFrame:
        return self.conn.execute(
            "SELECT * FROM research_reports WHERE symbol = ? ORDER BY report_date",
            [symbol],
        ).fetchdf()

    # ---- news items -------------------------------------------------------

    def insert_news_items(self, symbol: str, df: pd.DataFrame, source: str = "") -> int:
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        df = self._canonicalise_dates(df, ["publish_date", "date"])
        return self._insert_df("news_items", df, {
            "symbol": "symbol",
            "publish_date": "publish_date",
            "title": "title",
            "summary": "summary",
            "url": "url",
            "source": "source",
        })

    def query_news_items(self, symbol: str) -> pd.DataFrame:
        return self.conn.execute(
            "SELECT * FROM news_items WHERE symbol = ? ORDER BY publish_date",
            [symbol],
        ).fetchdf()

    # ---- announcements ----------------------------------------------------

    def insert_announcements(self, symbol: str, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        df = self._canonicalise_dates(df, ["publish_date", "date"])
        return self._insert_df("announcements", df, {
            "symbol": "symbol",
            "publish_date": "publish_date",
            "title": "title",
            "summary": "summary",
            "url": "url",
        })

    def query_announcements(self, symbol: str) -> pd.DataFrame:
        return self.conn.execute(
            "SELECT * FROM announcements WHERE symbol = ? ORDER BY publish_date DESC",
            [symbol],
        ).fetchdf()

    # ---- backtest results -------------------------------------------------

    def store_backtest_result(self, result: Any) -> int:
        """Store a backtest result (dict or BacktestResult-like object)."""
        if hasattr(result, "model_dump"):
            data = result.model_dump()
        elif isinstance(result, dict):
            data = dict(result)
        else:
            data = {}
        run_id = data.get("run_id", str(hash(str(data))))
        df = pd.DataFrame(
            [
                {
                    "run_id": run_id,
                    "symbol": str(data.get("symbol", "")),
                    "strategy_name": str(data.get("strategy_name", "unknown")),
                    "start_date": str(data.get("start_date", "")),
                    "end_date": str(data.get("end_date", "")),
                    "total_return": float(data.get("total_return", 0.0)),
                    "annualized_return": float(data.get("annualized_return", 0.0)),
                    "sharpe_ratio": float(data.get("sharpe_ratio", 0.0)),
                    "max_drawdown": float(data.get("max_drawdown", 0.0)),
                    "win_rate": float(data.get("win_rate", 0.0)),
                    "total_trades": int(data.get("total_trades", 0)),
                    "params_json": json.dumps(
                        {
                            k: v
                            for k, v in data.items()
                            if k
                            not in (
                                "run_id",
                                "symbol",
                                "strategy_name",
                                "start_date",
                                "end_date",
                                "total_return",
                                "annualized_return",
                                "sharpe_ratio",
                                "max_drawdown",
                                "win_rate",
                                "total_trades",
                                "fee_config_used",
                                "execution_signal",
                                "decision_scope",
                                "trades",
                                "data_assumption",
                                "benchmark_symbol",
                                "benchmark_return",
                                "benchmark_max_drawdown",
                                "alpha",
                                "beta",
                                "cost_breakdown",
                            )
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        )
        return self._insert_df(
            "backtest_results",
            df,
            {
                "run_id": "run_id",
                "symbol": "symbol",
                "strategy_name": "strategy_name",
                "start_date": "start_date",
                "end_date": "end_date",
                "total_return": "total_return",
                "annualized_return": "annualized_return",
                "sharpe_ratio": "sharpe_ratio",
                "max_drawdown": "max_drawdown",
                "win_rate": "win_rate",
                "total_trades": "total_trades",
                "params_json": "params_json",
            },
        )

    def get_backtest_results(
        self, strategy_name: str | None = None
    ) -> pd.DataFrame:
        if strategy_name:
            return self.conn.execute(
                "SELECT * FROM backtest_results WHERE strategy_name = ? ORDER BY created_at DESC",
                [strategy_name],
            ).fetchdf()
        return self.conn.execute(
            "SELECT * FROM backtest_results ORDER BY created_at DESC"
        ).fetchdf()

    def clear_backtest_results(self) -> int:
        """Delete all stored backtest results. Returns number of rows deleted."""
        result = self.conn.execute("DELETE FROM backtest_results")
        row = result.fetchone()
        return row[0] if row else 0

    def delete_backtest_result(self, run_id: str) -> int:
        """Delete a single backtest result by run_id. Returns 1 if deleted."""
        result = self.conn.execute(
            "DELETE FROM backtest_results WHERE run_id = ?", [run_id]
        )
        row = result.fetchone()
        return row[0] if row else 0

    # ---- paper trades -----------------------------------------------------

    def store_paper_trade(self, trade: dict[str, Any]) -> int:
        """Store a single paper trade record."""
        df = pd.DataFrame([trade])
        # fields expected: trade_id, symbol, direction, price, volume, fees,
        # trade_date, strategy_name, actionable, decision_scope
        if "trade_id" not in df.columns:
            df["trade_id"] = str(hash(str(trade)))
        if "actionable" not in df.columns:
            df["actionable"] = False
        if "decision_scope" not in df.columns:
            df["decision_scope"] = "paper_trading_only"
        df = self._canonicalise_dates(df, ["trade_date", "date"])
        return self._insert_df(
            "paper_trades",
            df,
            {
                "trade_id": "trade_id",
                "symbol": "symbol",
                "direction": "direction",
                "price": "price",
                "volume": "volume",
                "fees": "fees",
                "trade_date": "trade_date",
                "strategy_name": "strategy_name",
                "actionable": "actionable",
                "decision_scope": "decision_scope",
            },
        )

    def get_paper_trades(self, symbol: str | None = None) -> pd.DataFrame:
        if symbol:
            return self.conn.execute(
                "SELECT * FROM paper_trades WHERE symbol = ? ORDER BY trade_date",
                [symbol],
            ).fetchdf()
        return self.conn.execute(
            "SELECT * FROM paper_trades ORDER BY trade_date"
        ).fetchdf()

    # ---- market indicators ------------------------------------------------

    def insert_market_indicators(self, symbol: str, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        df = self._canonicalise_dates(df, ["trade_date", "date"])
        return self._insert_df(
            "market_indicators",
            df,
            {
                "symbol": "symbol",
                "trade_date": "trade_date",
                "ma_5": "ma_5",
                "ma_20": "ma_20",
                "ma_60": "ma_60",
                "rsi_14": "rsi_14",
                "atr_14": "atr_14",
                "volume_ma_5": "volume_ma_5",
            },
        )

    def query_market_indicators(
        self, symbol: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        sql = "SELECT * FROM market_indicators WHERE symbol = ?"
        params: list[Any] = [symbol]
        if start:
            sql += " AND trade_date >= ?"
            params.append(start)
        if end:
            sql += " AND trade_date <= ?"
            params.append(end)
        sql += " ORDER BY trade_date"
        return self.conn.execute(sql, params).fetchdf()

    def insert_trading_calendar(self, rows: pd.DataFrame | list[dict[str, Any]]) -> int:
        """Insert exchange trading-calendar rows."""
        return self.insert_table_rows("trading_calendar", rows)

    def insert_security_status_history(self, rows: pd.DataFrame | list[dict[str, Any]]) -> int:
        """Insert symbol status/ST history rows."""
        return self.insert_table_rows("security_status_history", rows)

    def insert_adjust_factors(self, rows: pd.DataFrame | list[dict[str, Any]]) -> int:
        """Insert qfq/hfq adjustment factors."""
        return self.insert_table_rows("adjust_factors", rows)

    def query_adjust_factors(
        self,
        symbol: str,
        adjust: str = "qfq",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        sql = "SELECT * FROM adjust_factors WHERE symbol = ? AND adjust = ?"
        params: list[Any] = [symbol, adjust]
        if start:
            sql += " AND trade_date >= ?"
            params.append(start)
        if end:
            sql += " AND trade_date <= ?"
            params.append(end)
        sql += " ORDER BY trade_date"
        return self.conn.execute(sql, params).fetchdf()

    def insert_technical_indicators(self, rows: pd.DataFrame | list[dict[str, Any]]) -> int:
        """Insert generic technical-indicator rows."""
        if isinstance(rows, pd.DataFrame):
            df = rows.copy()
        else:
            df = pd.DataFrame(rows)
        if df.empty:
            return 0
        df = self._normalise_kline_times(df)
        if "interval" in df.columns:
            df["interval"] = df["interval"].fillna("1d").map(self._normalise_interval)
        return self.insert_table_rows("technical_indicators", df)

    def query_technical_indicators(
        self,
        symbol: str,
        indicator: str,
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        interval = self._normalise_interval(interval)
        sql = (
            "SELECT * FROM technical_indicators "
            "WHERE symbol = ? AND indicator = ? AND interval = ?"
        )
        params: list[Any] = [symbol, indicator, interval]
        if start:
            sql += " AND bar_time >= ?"
            params.append(start)
        if end:
            sql += " AND bar_time <= ?"
            params.append(end)
        sql += " ORDER BY bar_time"
        return self.conn.execute(sql, params).fetchdf()

    # ---- metadata / maintenance ------------------------------------------

    def store_data_snapshot(self, snapshot: dict[str, Any]) -> int:
        """Store a dataset snapshot record for lineage and reproducibility."""
        data = dict(snapshot)
        if "snapshot_id" not in data:
            import uuid

            data["snapshot_id"] = uuid.uuid4().hex
        if "metadata_json" not in data and isinstance(data.get("metadata"), dict):
            data["metadata_json"] = json.dumps(data.pop("metadata"), ensure_ascii=False, sort_keys=True)
        return self.insert_table_rows("data_snapshots", [data])

    def store_data_quality_check(self, check: dict[str, Any]) -> int:
        """Store a data-quality check result for commercial data governance."""
        data = dict(check)
        if "check_id" not in data:
            import uuid

            data["check_id"] = uuid.uuid4().hex
        if "details_json" not in data and isinstance(data.get("details"), dict):
            data["details_json"] = json.dumps(data.pop("details"), ensure_ascii=False, sort_keys=True)
        if "fallback_path_json" not in data and isinstance(data.get("fallback_path"), list):
            data["fallback_path_json"] = json.dumps(data.pop("fallback_path"), ensure_ascii=False)
        return self.insert_table_rows("data_quality_checks", [data])

    def store_data_partition(self, partition: dict[str, Any]) -> int:
        """Store a logical data partition record for hot/cold maintenance."""
        data = dict(partition)
        if "partition_id" not in data:
            import uuid

            data["partition_id"] = uuid.uuid4().hex
        return self.insert_table_rows("data_partitions", [data])

    def store_ingestion_job(self, job: dict[str, Any]) -> int:
        """Store or update a database-level ingestion/import job record."""
        data = dict(job)
        if "job_id" not in data:
            import uuid

            data["job_id"] = uuid.uuid4().hex
        if "metadata_json" not in data and isinstance(data.get("metadata"), dict):
            data["metadata_json"] = json.dumps(data.pop("metadata"), ensure_ascii=False, sort_keys=True)
        return self.insert_table_rows("data_ingestion_jobs", [data])

    def store_ingestion_job_event(self, event: dict[str, Any]) -> int:
        """Append a durable ingestion-job progress event."""
        data = dict(event)
        if "event_id" not in data:
            import uuid

            data["event_id"] = uuid.uuid4().hex
        if "metadata_json" not in data and isinstance(data.get("metadata"), dict):
            data["metadata_json"] = json.dumps(data.pop("metadata"), ensure_ascii=False, sort_keys=True)
        return self.insert_table_rows("data_ingestion_job_events", [data])

    # ---- export / import (COPY TO / COPY FROM) ---------------------------

    EXPORT_FORMAT_MAP = {
        "csv": ("(FORMAT CSV, HEADER true)", ".csv"),
        "parquet": ("(FORMAT PARQUET)", ".parquet"),
        "json": ("(FORMAT JSON)", ".json"),
    }

    COMPRESSION_MAP = {
        "gzip": ".gz",
        "bz2": ".bz2",
        "xz": ".xz",
        "zstd": ".zst",
        "none": "",
    }

    # Tables that support incremental export via updated_at or created_at
    INCREMENTAL_TABLES = frozenset({
        "kline_bars", "valuations", "order_book_snapshots", "trade_tape",
        "market_indicators", "technical_indicators", "adjust_factors",
        "security_master", "trading_calendar", "backtest_results",
        "paper_trades", "news_items", "announcements", "research_reports",
        "audit_log", "data_quality_checks", "data_snapshots",
        "data_ingestion_jobs", "data_ingestion_job_events",
        "data_quality_rules", "data_quarantine",
    })

    def export_incremental(
        self,
        table_name: str,
        output_path: str,
        since: str,
        fmt: str = "parquet",
        *,
        updated_at_column: str = "updated_at",
    ) -> int:
        """Export rows that have been updated since *since*.

        Parameters
        ----------
        table_name : str
            Table to export.
        output_path : str
            Destination file path.
        since : str
            ISO-8601 timestamp or date string (e.g. ``"2024-01-01"`` or ``"2024-01-01T00:00:00"``).
        fmt : str
            Export format (``"csv"``, ``"parquet"``, ``"json"``).
        updated_at_column : str
            Column name to compare against *since*.

        Returns
        -------
        int
            Number of rows exported.
        """
        if table_name not in ALL_TABLE_DEFS:
            raise ValueError(f"Unknown table: {table_name}")
        if table_name not in self.INCREMENTAL_TABLES:
            raise ValueError(f"Table {table_name!r} does not support incremental export")
        if fmt not in self.EXPORT_FORMAT_MAP:
            raise ValueError(f"Unsupported format: {fmt}")

        opts, ext = self.EXPORT_FORMAT_MAP[fmt]
        p = Path(output_path)
        if p.suffix != ext:
            p = p.with_suffix(ext)
        output_path = str(p)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        sql = f'SELECT COUNT(*) FROM "{table_name}" WHERE "{updated_at_column}" >= ?'
        count_row = self.conn.execute(sql, [since]).fetchone()
        row_count = count_row[0] if count_row else 0

        if row_count > 0:
            self.conn.execute(
                f'COPY (SELECT * FROM "{table_name}" WHERE "{updated_at_column}" >= ?) TO ? {opts}',
                [since, output_path],
            )
        return row_count

    def export_table(
        self,
        table_name: str,
        fmt: str = "csv",
        output_path: str | None = None,
        compression: str = "none",
    ) -> str:
        """Export *table_name* to a file via DuckDB COPY TO.

        Parameters
        ----------
        table_name : str
            Table to export.
        fmt : str
            One of ``'csv'``, ``'parquet'``, ``'json'``.
        output_path : str | None
            Output file path. If None, auto-generated from table name + format.
        compression : str
            Compression algorithm: ``'none'``, ``'gzip'``, ``'bz2'``, ``'xz'``,
            or ``'zstd'``.  Only applies to CSV and JSON formats
            (Parquet is already compressed).

        Returns
        -------
        str
            Path to the exported file.
        """
        if table_name not in ALL_TABLE_DEFS:
            msg = f"Unknown table: {table_name}. Known: {list(ALL_TABLE_DEFS)}"
            raise ValueError(msg)
        if fmt not in self.EXPORT_FORMAT_MAP:
            msg = f"Unsupported format: {fmt}. Supported: {list(self.EXPORT_FORMAT_MAP)}"
            raise ValueError(msg)

        opts, ext = self.EXPORT_FORMAT_MAP[fmt]
        if output_path is None:
            output_path = f"{table_name}{ext}"
        else:
            # ensure extension
            p = Path(output_path)
            if p.suffix != ext:
                p = p.with_suffix(ext)
            output_path = str(p)

        # Apply compression suffix
        if compression != "none" and compression in self.COMPRESSION_MAP:
            comp_ext = self.COMPRESSION_MAP[compression]
            comp_path = str(Path(output_path) + comp_ext)
        else:
            comp_path = output_path

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(comp_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn.execute(
            f'COPY (SELECT * FROM "{table_name}") TO ? {opts}',
            [output_path],
        )

        # Compress if requested
        if compression != "none" and compression in self.COMPRESSION_MAP:
            import bz2
            import gzip
            import shutil

            comp_ext = self.COMPRESSION_MAP[compression]
            if compression == "gzip":
                with open(output_path, "rb") as f_in:
                    with gzip.open(comp_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
            elif compression == "bz2":
                with open(output_path, "rb") as f_in:
                    with bz2.open(comp_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                # xz / zstd — try gzip fallback
                with open(output_path, "rb") as f_in:
                    with gzip.open(comp_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                compression = "gzip"  # normalize

        return comp_path

    def import_table(
        self,
        table_name: str,
        fmt: str = "csv",
        file_path: str = "",
        *,
        validate: bool = True,
    ) -> int:
        """Import data from a file into *table_name* via DuckDB COPY FROM.

        Parameters
        ----------
        table_name : str
            Target table.
        fmt : str
            One of ``'csv'``, ``'parquet'``, ``'json'``.
        file_path : str
            Path to the source file.
        validate : bool
            If True, verify row count and column types after import.

        Returns
        -------
        int
            Number of rows imported.
        """
        if table_name not in ALL_TABLE_DEFS:
            msg = f"Unknown table: {table_name}. Known: {list(ALL_TABLE_DEFS)}"
            raise ValueError(msg)
        if fmt not in self.EXPORT_FORMAT_MAP:
            msg = f"Unsupported format: {fmt}. Supported: {list(self.EXPORT_FORMAT_MAP)}"
            raise ValueError(msg)

        opts, _ext = self.EXPORT_FORMAT_MAP[fmt]
        reader_fn = {
            "csv": "read_csv_auto",
            "parquet": "read_parquet",
            "json": "read_json_auto",
        }[fmt]
        df = self.conn.execute(f"SELECT * FROM {reader_fn}(?)", [file_path]).fetchdf()
        count = self.insert_table_rows(table_name, df)

        # Validate import
        if validate and count > 0:
            self._validate_import(table_name, file_path, fmt, count)

        return count

    def _validate_import(
        self, table_name: str, file_path: str, fmt: str, expected_rows: int
    ) -> dict[str, Any]:
        """Validate an import by comparing file row count with DB row count.

        Returns a validation result dict.
        """
        # Count rows in file
        if fmt == "parquet":
            try:
                import pyarrow.parquet as pq
                file_rows = pq.read_table(file_path).num_rows
            except Exception:
                file_rows = -1
        elif fmt == "json":
            import json
            try:
                file_rows = sum(1 for _ in open(file_path))
            except Exception:
                file_rows = -1
        elif fmt == "csv":
            import csv
            try:
                with open(file_path, "r") as f:
                    reader = csv.reader(f)
                    next(reader)  # skip header
                    file_rows = sum(1 for _ in reader)
            except Exception:
                file_rows = -1
        else:
            file_rows = -1

        # Count rows in DB
        db_count = self.conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]

        result = {
            "table": table_name,
            "file_rows": file_rows,
            "db_rows": db_count,
            "expected_after_import": expected_rows,
            "match": file_rows == expected_rows == db_count,
        }

        if not result["match"]:
            logger.warning(
                "Import validation warning for %s: file=%d, db=%d, expected=%d",
                table_name, file_rows, db_count, expected_rows,
            )

        return result

    def export_tables(
        self,
        table_names: list[str] | None = None,
        fmt: str = "csv",
        output_dir: str = ".",
        compression: str = "none",
    ) -> dict[str, str]:
        """Export multiple managed tables into *output_dir*."""
        names = table_names or list(ALL_TABLE_DEFS)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        exported: dict[str, str] = {}
        for table_name in names:
            if table_name not in ALL_TABLE_DEFS:
                msg = f"Unknown table: {table_name}. Known: {list(ALL_TABLE_DEFS)}"
                raise ValueError(msg)
            _, ext = self.EXPORT_FORMAT_MAP.get(fmt, ("", ""))
            output_path = str(Path(output_dir) / f"{table_name}{ext}")
            exported[table_name] = self.export_table(table_name, fmt=fmt, output_path=output_path, compression=compression)
        return exported

    def import_tables(
        self,
        table_files: dict[str, str],
        fmt: str = "csv",
        *,
        validate: bool = True,
    ) -> dict[str, int]:
        """Import multiple managed tables from ``{table_name: file_path}``."""
        imported: dict[str, int] = {}
        for table_name, file_path in table_files.items():
            imported[table_name] = self.import_table(table_name, fmt=fmt, file_path=file_path, validate=validate)
        return imported

    def import_from_database(
        self,
        *,
        source_db_path: str,
        source_table: str,
        target_table: str,
        source_type: str = "auto",
        symbol: str | None = None,
        start: str | None = None,
        end: str | None = None,
        symbol_column: str = "symbol",
        date_column: str = "trade_date",
    ) -> int:
        """Import rows from a DuckDB or SQLite database into a managed table."""
        if target_table not in ALL_TABLE_DEFS:
            msg = f"Unknown target table: {target_table}. Known: {list(ALL_TABLE_DEFS)}"
            raise ValueError(msg)
        path = os.path.expanduser(source_db_path)
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        inferred = Path(path).suffix.lower()
        db_type = source_type.lower()
        if db_type == "auto":
            db_type = "sqlite" if inferred in (".sqlite", ".sqlite3", ".db") else "duckdb"
        if db_type not in ("duckdb", "sqlite"):
            raise ValueError("source_type must be one of: auto, duckdb, sqlite")

        where_parts: list[str] = []
        params: list[Any] = []
        symbol_ident = self._quote_identifier(symbol_column)
        date_ident = self._quote_identifier(date_column)
        if symbol:
            where_parts.append(f"{symbol_ident} = ?")
            params.append(symbol)
        if start:
            where_parts.append(f"{date_ident} >= ?")
            params.append(start)
        if end:
            where_parts.append(f"{date_ident} <= ?")
            params.append(end)
        where_sql = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
        sql = f"SELECT * FROM {self._quote_identifier(source_table)}{where_sql}"

        if db_type == "duckdb":
            source_conn = duckdb.connect(path, read_only=True)
            try:
                df = source_conn.execute(sql, params).fetchdf()
            finally:
                source_conn.close()
        else:
            with sqlite3.connect(path) as source_conn:
                df = pd.read_sql_query(sql, source_conn, params=params)
        return self.insert_table_rows(target_table, df)

    # ---- stats -----------------------------------------------------------

    def get_table_stats(self) -> dict[str, dict[str, Any]]:
        """Return per-table row counts and latest date info.

        Returns
        -------
        dict
            ``{table_name: {"rows": int, "latest_date": str or None}}``
        """
        stats: dict[str, dict[str, Any]] = {}
        for table_name in ALL_TABLE_DEFS:
            if not self.table_exists(table_name):
                stats[table_name] = {"rows": 0, "latest_date": None}
                continue
            row_result = self.conn.execute(
                f'SELECT count(*) FROM "{table_name}"'
            ).fetchone()
            row_count = row_result[0] if row_result else 0
            # Try to find the "latest date" column
            latest: Any = None
            for date_col in (
                "bar_time",
                "trade_date",
                "report_date",
                "publish_date",
                "timestamp",
                "end_time",
                "updated_at",
                "created_at",
                "list_date",
            ):
                try:
                    date_result = self.conn.execute(
                        f'SELECT max({date_col}) FROM "{table_name}"'
                    ).fetchone()
                    if date_result and date_result[0] is not None:
                        latest = str(date_result[0])
                        break
                except Exception:
                    continue
            stats[table_name] = {"rows": row_count, "latest_date": latest}
        return stats

    # ---- vacuum ----------------------------------------------------------

    def vacuum(self) -> None:
        """Reclaim storage by checkpointing and truncating WAL."""
        self.conn.execute("CHECKPOINT")
        self.conn.execute("ANALYZE")

    # ---- raw SQL query ---------------------------------------------------

    def query_sql(self, sql: str) -> pd.DataFrame:
        """Execute an arbitrary SQL query and return results as a DataFrame."""
        return self.conn.execute(sql).fetchdf()

    def list_tables(self) -> list[str]:
        """Return list of managed table names that exist."""
        existing = []
        for table_name in ALL_TABLE_DEFS:
            if self.table_exists(table_name):
                existing.append(table_name)
        return existing

    # ---- backup / restore -------------------------------------------------

    def backup(self, destination_path: str, compress: bool = False) -> str:
        """Create a full database backup via DuckDB ``ATTACH`` + ``CREATE TABLE ... AS``.

        Parameters
        ----------
        destination_path : str
            Path to the backup ``.duckdb`` file.
        compress : bool
            If True, create a gzip-compressed archive of the backup file.

        Returns
        -------
        str
            Path to the backup file (or compressed archive).
        """
        import gzip
        import shutil

        dest = Path(destination_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        backup_path = str(dest) if dest.suffix == ".duckdb" else str(dest) + ".duckdb"

        # Use DuckDB ATTACH for hot backup
        escaped_backup_path = backup_path.replace("'", "''")
        self.conn.execute(f"ATTACH '{escaped_backup_path}' AS backup_db")
        try:
            for table_name in ALL_TABLE_DEFS:
                if self.table_exists(table_name):
                    self.conn.execute(f'DROP TABLE IF EXISTS backup_db."{table_name}"')
                    self.conn.execute(
                        f'CREATE TABLE backup_db."{table_name}" AS SELECT * FROM "{table_name}"'
                    )
            self.conn.execute("CHECKPOINT")
        finally:
            self.conn.execute("DETACH backup_db")

        if compress:
            archive_path = str(dest) if dest.suffix == ".gz" else str(dest) + ".gz"
            with open(backup_path, "rb") as f_in:
                with gzip.open(archive_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            logger = logging.getLogger(__name__)
            logger.info("Compressed backup → %s", archive_path)
            return archive_path
        return backup_path

    def restore(self, source_path: str) -> int:
        """Restore a full database from a backup ``.duckdb`` file.

        Drops all existing managed tables and recreates them from the backup.

        Parameters
        ----------
        source_path : str
            Path to the backup ``.duckdb`` file (or ``.duckdb.gz``).

        Returns
        -------
        int
            Number of tables restored.
        """
        import gzip
        import shutil

        src = Path(source_path)
        if src.suffix == ".gz":
            decompressed = src.with_suffix(".duckdb")
            with gzip.open(src, "rb") as f_in:
                with open(decompressed, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            source_path = str(decompressed)

        source = Path(source_path)
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"backup file does not exist: {source}")

        # Validate the complete source before touching the live tables.
        escaped_source_path = str(source).replace("'", "''")
        self.conn.execute(f"ATTACH '{escaped_source_path}' AS backup_db")
        try:
            available = []
            for table_name in ALL_TABLE_DEFS:
                try:
                    self.conn.execute(f'SELECT 1 FROM backup_db."{table_name}" LIMIT 0')
                    available.append(table_name)
                except Exception:
                    continue
            if not available:
                raise ValueError("backup contains no managed tables")

            # DuckDB DDL is transactional.  If any table copy fails, rollback
            # leaves the active database untouched instead of half-restored.
            self.conn.execute("BEGIN TRANSACTION")
            try:
                for table_name in available:
                    self.conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
                    self.conn.execute(
                        f'CREATE TABLE "{table_name}" AS SELECT * FROM backup_db."{table_name}"'
                    )
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise
            count = len(available)
            self.conn.execute("CHECKPOINT")
        finally:
            self.conn.execute("DETACH backup_db")
        return count

    def backup_to_parquet(self, output_dir: str = ".", compression: str = "snappy") -> dict[str, str]:
        """Export the entire database as Parquet files (one per table).

        Returns ``{table_name: file_path}``.
        """
        import pyarrow.parquet as pq

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        result: dict[str, str] = {}
        for table_name in ALL_TABLE_DEFS:
            if not self.table_exists(table_name):
                continue
            df = self.conn.execute(f'SELECT * FROM "{table_name}"').fetchdf()
            if df.empty:
                continue
            file_path = os.path.join(output_dir, f"{table_name}.parquet")
            df.to_parquet(file_path, compression=compression, index=False)
            result[table_name] = file_path
        return result

    def restore_from_parquet(self, input_dir: str) -> dict[str, int]:
        """Import Parquet files back into the database.

        Parameters
        ----------
        input_dir : str
            Directory containing ``{table_name}.parquet`` files.

        Returns
        -------
        dict
            ``{table_name: row_count}``.
        """
        import pyarrow.parquet as pq

        inp = Path(input_dir)
        if not inp.is_dir():
            raise FileNotFoundError(f"Directory not found: {input_dir}")

        imported: dict[str, int] = {}
        for parquet_file in inp.glob("*.parquet"):
            table_name = parquet_file.stem
            if table_name not in ALL_TABLE_DEFS:
                continue
            df = pq.read_table(str(parquet_file)).to_pandas()
            count = self.insert_table_rows(table_name, df)
            imported[table_name] = count
        return imported


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def init_astock_db(db_path: str = "~/.tradingagents/astock/astock.duckdb") -> AStockStore:
    """Create an ``AStockStore``, call ``init_schema()``, and return it."""
    store = AStockStore(db_path)
    store.connect()
    store.init_schema()
    return store
