"""Schema introspection, statistics, raw SQL, migrations, and maintenance APIs."""

from __future__ import annotations

from .pg_common import *


class PGAdminMixin:
    """Schema introspection, statistics, raw SQL, migrations, and maintenance APIs."""

    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        sql = (
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = :name AND table_schema = :schema"
        )
        params = {"name": table_name, "schema": self._config.schema}
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params).scalar()
                return result is not None and result > 0
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                val = result.scalar()
                return val is not None and val > 0

    async def list_symbols(self, table_name: str | None = None) -> list[str]:
        """Return known symbols from managed tables."""
        tables = [table_name] if table_name else ALL_TABLE_NAMES
        symbols: set[str] = set()
        for tbl in tables:
            if not tbl or not await self.table_exists(tbl):
                continue
            try:
                sql = f'SELECT DISTINCT symbol FROM "{tbl}" WHERE symbol IS NOT NULL'
                if self._sync:
                    with self._sync_engine.connect() as conn:
                        rows = conn.execute(text(sql)).fetchall()
                else:
                    async with self._async_engine.connect() as conn:
                        result = await conn.execute(text(sql))
                        rows = result.fetchall()
                for (sym,) in rows:
                    if sym:
                        symbols.add(str(sym))
            except Exception:
                continue
        return sorted(symbols)

    async def list_tables(self) -> list[str]:
        """Return list of managed table names that exist."""
        existing = []
        for table_name in ALL_TABLE_NAMES:
            if await self.table_exists(table_name):
                existing.append(table_name)
        return existing

    async def _table_columns(self, table_name: str) -> list[str]:
        """Return column names for a table via information_schema."""
        sql = (
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :name AND table_schema = :schema "
            "ORDER BY ordinal_position"
        )
        params = {"name": table_name, "schema": self._config.schema}
        if self._sync:
            with self._sync_engine.connect() as conn:
                rows = conn.execute(text(sql), params).fetchall()
                return [str(r[0]) for r in rows]
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return [str(r[0]) for r in rows]

    # ---- stats --------------------------------------------------------------

    async def get_table_stats(self) -> dict[str, dict[str, Any]]:
        """Return per-table row counts and latest date info."""
        stats: dict[str, dict[str, Any]] = {}
        for table_name in ALL_TABLE_NAMES:
            if not await self.table_exists(table_name):
                stats[table_name] = {"rows": 0, "latest_date": None}
                continue
            try:
                row_count = 0
                latest: Any = None
                if self._sync:
                    with self._sync_engine.connect() as conn:
                        row_result = conn.execute(
                            text(f'SELECT count(*) FROM "{table_name}"')
                        ).scalar()
                        row_count = row_result if row_result else 0
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
                                date_result = conn.execute(
                                    text(f'SELECT max({date_col}) FROM "{table_name}"')
                                ).scalar()
                                if date_result is not None:
                                    latest = str(date_result)
                                    break
                            except Exception:
                                continue
                else:
                    async with self._async_engine.connect() as conn:
                        row_result = await conn.execute(
                            text(f'SELECT count(*) FROM "{table_name}"')
                        )
                        row_count = row_result.scalar() or 0
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
                                date_result = await conn.execute(
                                    text(f'SELECT max({date_col}) FROM "{table_name}"')
                                )
                                val = date_result.scalar()
                                if val is not None:
                                    latest = str(val)
                                    break
                            except Exception:
                                continue
                stats[table_name] = {"rows": row_count, "latest_date": latest}
            except Exception:
                stats[table_name] = {"rows": 0, "latest_date": None}
        return stats

    # ---- raw SQL query ------------------------------------------------------

    async def query_sql(self, sql_str: str) -> pd.DataFrame:
        """Execute an arbitrary SQL query and return results as a DataFrame."""
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql_str))
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql_str))
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- migration engine ---------------------------------------------------

    async def migrate(self, *names: str) -> list[dict[str, Any]]:
        """Apply a named, versioned migration if it has not been run before.

        Each migration is a ``(name, description, sql_or_none, rollback_sql_or_none)``
        entry defined in ``_MIGRATIONS``. After the SQL is executed (if any), a
        row is inserted into ``migration_versions``.

        If *names* is empty, all un-applied migrations are run in order.
        Returns a list of ``{version_id, description, status, duration_ms}`` records.
        """
        if not await self.table_exists("migration_versions"):
            async with self._async_engine.begin() as conn:
                await conn.run_sync(MigrationVersion.__table__.create)

        # Get applied migrations
        if self._sync:
            with self._sync_engine.connect() as conn:
                applied = {
                    str(row[0])
                    for row in conn.execute(text("SELECT version_id FROM migration_versions")).fetchall()
                }
        else:
            async with self._async_engine.connect() as conn:
                rows = await conn.execute(text("SELECT version_id FROM migration_versions"))
                applied = {str(r[0]) for r in rows.fetchall()}

        results: list[dict[str, Any]] = []
        candidates = list(self._MIGRATIONS)
        if names:
            candidates = [n for n in candidates if n[0] in names]
            missing = set(names) - {n[0] for n in candidates}
            if missing:
                raise ValueError(f"Unknown migration(s): {missing}. Known: {[m[0] for m in self._MIGRATIONS]}")

        for vid, desc, migration_sql, rollback_sql in candidates:
            if vid in applied:
                continue
            t0 = _time.time()
            status = "applied"
            duration_ms = 0
            try:
                if migration_sql:
                    if self._sync:
                        with self._sync_engine.connect() as conn:
                            conn.execute(text(migration_sql))
                            conn.commit()
                    else:
                        async with self._async_engine.connect() as conn:
                            await conn.execute(text(migration_sql))
                            await conn.commit()
                elapsed = _time.time() - t0
                duration_ms = int(round(elapsed * 1000))
            except Exception as exc:
                status = "failed"
                elapsed = _time.time() - t0
                duration_ms = int(round(elapsed * 1000))
                version_record = {
                    "version_id": vid,
                    "description": desc,
                    "status": status,
                    "duration_ms": duration_ms,
                    "checksum": repr(migration_sql) if migration_sql else "",
                }
                columns = list(version_record.keys())
                pk_cols = ["version_id"]
                sql = self._build_upsert_sql("migration_versions", columns, pk_cols)
                if self._sync:
                    with self._sync_engine.connect() as conn:
                        conn.execute(text(sql), version_record)
                        conn.commit()
                else:
                    async with self._async_session_factory() as session:
                        await session.execute(text(sql), version_record)
                        await session.commit()
                raise RuntimeError(f"Migration {vid!r} failed: {exc}") from exc

            version_record = {
                "version_id": vid,
                "description": desc,
                "status": status,
                "duration_ms": duration_ms,
                "checksum": repr(migration_sql) if migration_sql else "",
                "rollback_sql": rollback_sql,
            }
            columns = list(version_record.keys())
            pk_cols = ["version_id"]
            sql = self._build_upsert_sql("migration_versions", columns, pk_cols)
            if self._sync:
                with self._sync_engine.connect() as conn:
                    conn.execute(text(sql), version_record)
                    conn.commit()
            else:
                async with self._async_session_factory() as session:
                    await session.execute(text(sql), version_record)
                    await session.commit()

            results.append({
                "version_id": vid,
                "description": desc,
                "status": status,
                "duration_ms": duration_ms,
            })
        return results

    async def list_migrations(self) -> pd.DataFrame:
        """Return all applied migration records."""
        return await self.query_sql("SELECT * FROM migration_versions ORDER BY applied_at")

    async def rollback_migration(self, version_id: str) -> None:
        """Roll back a previously applied migration if rollback_sql is set."""
        sql = "SELECT rollback_sql FROM migration_versions WHERE version_id = :vid"
        params = {"vid": version_id}
        if self._sync:
            with self._sync_engine.connect() as conn:
                row = conn.execute(text(sql), params).fetchone()
                if row is None:
                    raise ValueError(f"Migration {version_id!r} not found")
                if not row[0]:
                    raise ValueError(f"Migration {version_id!r} has no rollback SQL defined")
                conn.execute(text(str(row[0])))
                conn.execute(text("DELETE FROM migration_versions WHERE version_id = :vid"), params)
                conn.commit()
        else:
            async with self._async_engine.connect() as conn:
                row = (await conn.execute(text(sql), params)).fetchone()
                if row is None:
                    raise ValueError(f"Migration {version_id!r} not found")
                if not row[0]:
                    raise ValueError(f"Migration {version_id!r} has no rollback SQL defined")
                await conn.execute(text(str(row[0])))
                await conn.execute(text("DELETE FROM migration_versions WHERE version_id = :vid"), params)
                await conn.commit()

    # Migration registry — discoverable class variable
    _MIGRATIONS: list[tuple[str, str, str | None, str | None]] = []

    def discover_migrations(self, migrations_dir: str | None = None) -> int:
        """Auto-discover migration files from the migrations/ directory (mirrors AStockStore)."""
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

            # Callable migration functions often have prose docstrings.  This
            # compatibility registry accepts only explicitly declared SQL;
            # callable migrations are handled by migrations.runner instead.
            upgrade_sql = None
            sql_assign = re.search(r'(?:upgrade_sql|ddl)\s*=\s*"""(.*?)"""', content, re.DOTALL)
            if sql_assign:
                upgrade_sql = sql_assign.group(1).strip() or None

            rollback_sql = None
            sql_assign = re.search(r'(?:rollback_sql|rollback_ddl)\s*=\s*"""(.*?)"""', content, re.DOTALL)
            if sql_assign:
                rollback_sql = sql_assign.group(1).strip() or None

            discovered[version_id] = (version_id, description, upgrade_sql, rollback_sql)

        existing = [entry for entry in self._MIGRATIONS if entry[0] not in discovered]
        self._MIGRATIONS = sorted(existing + list(discovered.values()), key=lambda x: x[0])
        return len(discovered)

    # ---- maintenance --------------------------------------------------------

    async def vacuum(self) -> None:
        """Reclaim storage (PostgreSQL VACUUM ANALYZE)."""
        if self._sync:
            with self._sync_engine.connect() as conn:
                conn.execute(text("VACUUM ANALYZE"))
                conn.commit()
        else:
            async with self._async_engine.connect() as conn:
                await conn.execute(text("VACUUM ANALYZE"))
                await conn.commit()

    async def drop_all_tables(self) -> None:
        """Drop all managed tables (for test teardown)."""
        if self._sync:
            Base.metadata.drop_all(self._sync_engine)
        else:
            async with self._async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)

    # ---- industry classification / security master / etc. -------------------
