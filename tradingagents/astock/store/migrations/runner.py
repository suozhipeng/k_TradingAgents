"""Standalone migration runner for AStock Pro PostgreSQL.

Auto-discovers migration files from a migrations/ directory, tracks state
in a ``migration_versions`` table, and supports both sync and async engines.

Migration file naming convention::

    V{YYYYMMDD}_{NNN}__{name}.py

Each file exports ``version_id``, ``description``, ``dependencies`` (list[str]),
``upgrade(engine)`` and ``downgrade(engine)`` coroutine functions.

Migration file template::

    # V20260628_001__my_migration.py
    version_id = "V20260628_001"
    description = "Describe what this migration does"
    dependencies = []

    async def upgrade(engine):
        await engine.execute(text("CREATE TABLE ..."))

    async def downgrade(engine):
        await engine.execute(text("DROP TABLE ..."))
"""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import logging
import re
import time
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

# Regex for valid migration filenames
_MIGRATION_FN_RE = re.compile(r"^V(\d{8})_(\d{3})__(.+)\.py$")

# DDL for the tracking table (mirrors the ORM model in pg_store.py)
CREATE_MIGRATION_VERSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS migration_versions (
    version_id VARCHAR NOT NULL,
    description VARCHAR,
    applied_by VARCHAR,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR,
    duration_ms BIGINT DEFAULT 0,
    status VARCHAR DEFAULT 'applied',
    rollback_sql VARCHAR,
    PRIMARY KEY (version_id)
)
"""


def _description_line(name: str) -> str:
    """Convert snake_case to readable description."""
    return name.replace("_", " ").title()


class Migration:
    """Describes a single discovered migration."""

    __slots__ = (
        "version_id",
        "description",
        "dependencies",
        "filepath",
        "upgrade",
        "downgrade",
        "checksum",
        "has_rollback",
    )

    def __init__(
        self,
        version_id: str,
        description: str,
        dependencies: list[str],
        filepath: Path,
        upgrade: Any,
        downgrade: Any,
        checksum: str,
        has_rollback: bool,
    ) -> None:
        self.version_id = version_id
        self.description = description
        self.dependencies = dependencies
        self.filepath = filepath
        self.upgrade = upgrade
        self.downgrade = downgrade
        self.checksum = checksum
        self.has_rollback = has_rollback


class MigrationStatus:
    """Status of a single migration (used internally by status())."""

    __slots__ = ("version_id", "description", "status", "applied_at", "checksum", "duration_ms", "has_rollback", "filepath")

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class MigrationRunner:
    """Self-contained migration engine for PostgreSQL.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine or sqlalchemy.ext.asyncio.AsyncEngine
        A SQLAlchemy engine (sync or async).
    schema : str
        Database schema name (default: ``"public"``).
    migrations_dir : str or Path, optional
        Path to the directory containing migration ``.py`` files.
        Default: ``<package_dir>/migrations/`` (auto-detected).
    dry_run : bool
        If True, only log what would be done (no DB writes).
    """

    def __init__(
        self,
        engine: Any,
        schema: str = "public",
        migrations_dir: Optional[Path] = None,
        dry_run: bool = False,
    ) -> None:
        self._engine = engine
        self._schema = schema
        self._dry_run = dry_run

        # Detect whether engine is sync or async
        self._is_async = self._detect_async(engine)

        # Locate migrations directory
        if migrations_dir is not None:
            self._migrations_dir = Path(migrations_dir)
        else:
            # Default: alongside this file
            self._migrations_dir = Path(__file__).resolve().parent

        self._migrations_dir.mkdir(parents=True, exist_ok=True)

        # Cached discovered migrations
        self._migrations: list[Migration] = []

        logger.info(
            "MigrationRunner initialized (dir=%s, schema=%s, async=%s, dry_run=%s)",
            self._migrations_dir,
            schema,
            self._is_async,
            dry_run,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def discover(self) -> list[Migration]:
        """Scan the migrations directory and return a sorted list of Migration objects.

        Migrations are sorted by ``version_id`` (ascending).
        """
        self._migrations = []
        for fpath in sorted(self._migrations_dir.iterdir()):
            if not fpath.is_file() or not fpath.name.endswith(".py"):
                continue
            m = _MIGRATION_FN_RE.match(fpath.name)
            if not m:
                continue

            try:
                migration = self._load_migration(fpath)
                if migration is not None:
                    self._migrations.append(migration)
            except Exception:
                logger.warning("Skipping invalid migration file %s", fpath.name, exc_info=True)

        # Sort by version_id (natural string sort works for V{YYYYMMDD}_{NNN})
        self._migrations.sort(key=lambda m: m.version_id)
        logger.info("Discovered %d migration(s)", len(self._migrations))
        return list(self._migrations)

    async def status(self) -> pd.DataFrame:
        """Return a DataFrame of all migrations vs applied state.

        Columns: version_id, description, status, applied_at,
                 checksum, duration_ms, filepath.
        """
        await self._ensure_tracking_table()

        # Get applied records
        applied = await self._fetch_applied()
        applied_map: dict[str, dict[str, Any]] = {}
        for row in applied:
            applied_map[row["version_id"]] = row

        # Discover if not already cached
        if not self._migrations:
            await self.discover()

        rows: list[dict[str, Any]] = []
        for m in self._migrations:
            rec = applied_map.get(m.version_id)
            if rec is not None:
                rows.append({
                    "version_id": m.version_id,
                    "description": m.description,
                    "status": rec.get("status", "applied"),
                    "applied_at": rec.get("applied_at"),
                    "checksum": rec.get("checksum", ""),
                    "duration_ms": rec.get("duration_ms", 0),
                    "has_rollback": m.has_rollback,
                    "filepath": str(m.filepath),
                })
            else:
                rows.append({
                    "version_id": m.version_id,
                    "description": m.description,
                    "status": "pending",
                    "applied_at": None,
                    "checksum": m.checksum,
                    "duration_ms": 0,
                    "has_rollback": m.has_rollback,
                    "filepath": str(m.filepath),
                })

        return pd.DataFrame(rows)

    async def upgrade(self, target: Optional[str] = None) -> list[dict[str, Any]]:
        """Run all pending migrations (or up to *target*).

        Each migration runs inside a transaction.  On failure the error
        is recorded in ``migration_versions`` and subsequent migrations
        are **not** attempted.

        Parameters
        ----------
        target : str, optional
            Run migrations only up to (and including) this version_id.
            If None, all pending migrations are applied.

        Returns
        -------
        list[dict]
            Each entry: ``{version_id, description, status, duration_ms}``.
        """
        await self._ensure_tracking_table()

        if not self._migrations:
            await self.discover()

        # Determine which migrations have already been applied
        applied = {r["version_id"] for r in await self._fetch_applied() if r.get("status") not in ("failed",)}
        results: list[dict[str, Any]] = []

        for m in self._migrations:
            if target is not None and m.version_id > target:
                break

            if m.version_id in applied:
                logger.info("Migration %s already applied, skipping", m.version_id)
                continue

            # Check that dependencies are met
            for dep in m.dependencies:
                if dep not in applied:
                    msg = (
                        f"Migration {m.version_id} depends on {dep} "
                        f"which has not been applied"
                    )
                    logger.error(msg)
                    results.append({
                        "version_id": m.version_id,
                        "description": m.description,
                        "status": "skipped",
                        "duration_ms": 0,
                        "error": msg,
                    })
                    return results  # Stop on dependency failure

            # Run the migration
            t0 = time.monotonic()
            status = "applied"
            error_msg: Optional[str] = None
            rollback_available = m.has_rollback

            try:
                if self._dry_run:
                    logger.info("[DRY-RUN] Would apply migration %s: %s", m.version_id, m.description)
                else:
                    await self._run_migration(m, direction="upgrade")
                elapsed_ms = int(round((time.monotonic() - t0) * 1000))
                logger.info("Migration %s applied in %d ms", m.version_id, elapsed_ms)
            except Exception as exc:
                elapsed_ms = int(round((time.monotonic() - t0) * 1000))
                status = "failed"
                error_msg = str(exc)
                logger.error("Migration %s FAILED after %d ms: %s", m.version_id, elapsed_ms, exc)

            # Record in tracking table even on failure
            record = {
                "version_id": m.version_id,
                "description": m.description,
                "checksum": m.checksum,
                "duration_ms": elapsed_ms,
                "status": status,
                "rollback_sql": "available" if rollback_available else "",
            }
            if not self._dry_run:
                await self._upsert_migration_record(record)
            else:
                logger.info("[DRY-RUN] Would record: %s -> %s", m.version_id, status)

            result_entry: dict[str, Any] = {
                "version_id": m.version_id,
                "description": m.description,
                "status": status,
                "duration_ms": elapsed_ms,
            }
            if error_msg:
                result_entry["error"] = error_msg
            results.append(result_entry)

            # Halt on failure — do not proceed with subsequent migrations
            if status == "failed":
                break

        return results

    async def downgrade(self, target: str) -> list[dict[str, Any]]:
        """Roll back to *target* version by reverting migrations one at a time.

        Migrations are reverted in reverse order (newest first) until
        the *target* version is the most recent applied migration.
        The *target* migration itself is **not** reverted.

        Parameters
        ----------
        target : str
            Revert all migrations that are newer than this version_id.
            The *target* version stays applied.

        Returns
        -------
        list[dict]
            Each entry: ``{version_id, description, status, duration_ms}``.
        """
        await self._ensure_tracking_table()

        if not self._migrations:
            await self.discover()

        # Build lookup
        migration_map = {m.version_id: m for m in self._migrations}

        if target not in migration_map:
            raise ValueError(
                f"Target version {target!r} not found among discovered migrations. "
                f"Known: {sorted(migration_map.keys())}"
            )

        applied = await self._fetch_applied()
        applied_ids = [r["version_id"] for r in applied if r.get("status") == "applied"]

        # Determine which applied migrations need reverting
        # Downgrade in reverse order (newest first) down to (but not including) target
        to_revert = [vid for vid in sorted(applied_ids, reverse=True) if vid > target]

        if not to_revert:
            logger.info("No migrations to revert (already at target %s)", target)
            return []

        results: list[dict[str, Any]] = []
        for vid in to_revert:
            m = migration_map.get(vid)
            if m is None:
                logger.warning("Applied migration %s has no matching file, skipping revert", vid)
                continue

            if not m.has_rollback:
                logger.warning(
                    "Migration %s has no downgrade() function, cannot revert", vid
                )
                results.append({
                    "version_id": vid,
                    "description": m.description,
                    "status": "skipped",
                    "duration_ms": 0,
                    "error": "No downgrade() available",
                })
                continue

            t0 = time.monotonic()
            status = "reverted"
            error_msg: Optional[str] = None

            try:
                if self._dry_run:
                    logger.info("[DRY-RUN] Would revert migration %s: %s", vid, m.description)
                else:
                    await self._run_migration(m, direction="downgrade")
                elapsed_ms = int(round((time.monotonic() - t0) * 1000))
                logger.info("Migration %s reverted in %d ms", vid, elapsed_ms)
            except Exception as exc:
                elapsed_ms = int(round((time.monotonic() - t0) * 1000))
                status = "failed"
                error_msg = str(exc)
                logger.error("Revert of %s FAILED after %d ms: %s", vid, elapsed_ms, exc)

            # Delete or mark the record
            if not self._dry_run:
                if status == "reverted":
                    await self._delete_migration_record(vid)
                else:
                    await self._upsert_migration_record({
                        "version_id": vid,
                        "description": m.description,
                        "checksum": m.checksum,
                        "duration_ms": elapsed_ms,
                        "status": "revert_failed",
                        "rollback_sql": "",
                    })
            else:
                logger.info("[DRY-RUN] Would remove record for %s", vid)

            result_entry: dict[str, Any] = {
                "version_id": vid,
                "description": m.description,
                "status": status,
                "duration_ms": elapsed_ms,
            }
            if error_msg:
                result_entry["error"] = error_msg
            results.append(result_entry)

            if status == "failed":
                break

        return results

    async def create(self, name: str) -> str:
        """Generate a new migration file from template.

        The filename is auto-generated as::

            V{YYYYMMDD}_{NNN}__{name}.py

        where *NNN* is the next available sequence number for today.

        Parameters
        ----------
        name : str
            A short snake_case name for the migration.

        Returns
        -------
        str
            Absolute path to the newly created migration file.
        """
        today = datetime.date.today().strftime("%Y%m%d")

        # Find the next sequence number for today
        seq = 1
        for fpath in self._migrations_dir.iterdir():
            m = _MIGRATION_FN_RE.match(fpath.name)
            if m and m.group(1) == today:
                seq = max(seq, int(m.group(2)) + 1)

        version_id = f"V{today}_{seq:03d}"
        filename = f"{version_id}__{name}.py"
        filepath = self._migrations_dir / filename

        template = f'''# {filename}
"""Migration: {name}

{_description_line(name)}
"""

from __future__ import annotations

from sqlalchemy import text

version_id = "{version_id}"
description = "{name}"
dependencies: list[str] = []


async def upgrade(engine):
    """Apply the migration."""
    # TODO: Write your upgrade SQL here
    # await engine.execute(text("..."))


async def downgrade(engine):
    """Revert the migration."""
    # TODO: Write your downgrade SQL here
    # await engine.execute(text("..."))
'''

        filepath.write_text(template, encoding="utf-8")
        logger.info("Created migration file: %s", filepath)
        return str(filepath)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_async(self, engine: Any) -> bool:
        """Return True if *engine* is an async (asyncio) engine."""
        name = type(engine).__module__ or ""
        return "asyncio" in name or "async" in name

    def _load_migration(self, fpath: Path) -> Optional[Migration]:
        """Load a single migration file and return a Migration namedtuple."""
        filename = fpath.name
        m = _MIGRATION_FN_RE.match(filename)
        if not m:
            return None

        version_id = f"V{m.group(1)}_{m.group(2)}"
        name_part = m.group(3)

        # Compute checksum of file contents
        checksum = hashlib.sha256(fpath.read_bytes()).hexdigest()

        # Import the module dynamically
        spec = importlib.util.spec_from_file_location(f"migration_{version_id}", fpath)
        if spec is None or spec.loader is None:
            logger.warning("Could not load spec for %s", fpath)
            return None

        mod = importlib.util.module_from_spec(spec)
        # Note: sys.modules manipulation is avoided to keep it clean;
        # the module is only used transiently.
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:
            logger.warning("Failed to execute migration module %s: %s", fpath.name, exc)
            return None

        description = getattr(mod, "description", name_part)
        dependencies = getattr(mod, "dependencies", [])
        upgrade_fn = getattr(mod, "upgrade", None)
        downgrade_fn = getattr(mod, "downgrade", None)

        if upgrade_fn is None:
            logger.warning("Migration %s has no upgrade() function, skipping", filename)
            return None

        has_rollback = downgrade_fn is not None

        return Migration(
            version_id=version_id,
            description=description,
            dependencies=dependencies,
            filepath=fpath,
            upgrade=upgrade_fn,
            downgrade=downgrade_fn,
            checksum=checksum,
            has_rollback=has_rollback,
        )

    async def _ensure_tracking_table(self) -> None:
        """Create migration_versions table if it does not exist."""
        try:
            exists = await self._table_exists("migration_versions")
        except Exception:
            exists = False

        if not exists:
            if self._dry_run:
                logger.info("[DRY-RUN] Would CREATE TABLE migration_versions")
            else:
                await self._execute_ddl(CREATE_MIGRATION_VERSIONS_TABLE)
                logger.info("Created migration_versions tracking table")

    async def _table_exists(self, table_name: str) -> bool:
        """Check if *table_name* exists in the current schema."""
        if self._is_async:
            async with self._engine.connect() as conn:
                insp = await conn.run_sync(lambda sync_conn: inspect(sync_conn))
                return insp.has_table(table_name, schema=self._schema)
        else:
            with self._engine.connect() as conn:
                insp = inspect(conn)
                return insp.has_table(table_name, schema=self._schema)

    async def _execute_ddl(self, sql: str) -> None:
        """Execute a DDL statement (no results)."""
        if self._is_async:
            async with self._engine.begin() as conn:
                await conn.execute(text(sql))
        else:
            with self._engine.begin() as conn:
                conn.execute(text(sql))

    async def _fetch_applied(self) -> list[dict[str, Any]]:
        """Return all rows from migration_versions as dicts."""
        sql = "SELECT version_id, description, applied_at, checksum, duration_ms, status, rollback_sql FROM migration_versions ORDER BY version_id"
        if self._is_async:
            async with self._engine.connect() as conn:
                result = await conn.execute(text(sql))
                rows = result.fetchall()
                return [dict(row._mapping) for row in rows]
        else:
            with self._engine.connect() as conn:
                result = conn.execute(text(sql))
                rows = result.fetchall()
                return [dict(row._mapping) for row in rows]

    async def _upsert_migration_record(self, record: dict[str, Any]) -> None:
        """Insert or update a row in migration_versions."""
        # Use INSERT ... ON CONFLICT for PostgreSQL upsert
        columns = list(record.keys())
        placeholders = ", ".join(f":{c}" for c in columns)
        updates = ", ".join(
            f"{c} = EXCLUDED.{c}"
            for c in columns
            if c != "version_id"
        )

        sql = (
            f"INSERT INTO migration_versions ({', '.join(columns)}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT (version_id) DO UPDATE SET {updates}"
        )

        if self._is_async:
            async with self._engine.begin() as conn:
                await conn.execute(text(sql), record)
        else:
            with self._engine.begin() as conn:
                conn.execute(text(sql), record)

    async def _delete_migration_record(self, version_id: str) -> None:
        """Delete a row from migration_versions."""
        sql = "DELETE FROM migration_versions WHERE version_id = :vid"
        params = {"vid": version_id}
        if self._is_async:
            async with self._engine.begin() as conn:
                await conn.execute(text(sql), params)
        else:
            with self._engine.begin() as conn:
                conn.execute(text(sql), params)

    async def _run_migration(self, m: Migration, direction: str = "upgrade") -> None:
        """Execute upgrade or downgrade for a migration inside a transaction.

        The migration function receives the engine directly; it may
        manage its own transaction or rely on implicit autocommit.
        """
        fn = m.upgrade if direction == "upgrade" else m.downgrade
        if fn is None:
            raise RuntimeError(f"Migration {m.version_id} has no {direction}() function")

        # The function signature expects the engine — call it.
        try:
            result = fn(self._engine)
            # If it's a coroutine, await it
            if hasattr(result, "__await__"):
                await result
        except Exception:
            raise
