"""Shared DataFrame normalization and PostgreSQL upsert helpers."""

from __future__ import annotations

from .pg_common import *


class PGDataFrameIOMixin:
    """Shared DataFrame normalization and PostgreSQL upsert helpers."""

    @staticmethod
    def _normalise_interval(interval: str) -> str:
        """Normalise interval string to canonical form."""
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
    def _df_from_rows(
        rows: pd.DataFrame | list[dict[str, Any]], column_map: dict[str, str]
    ) -> pd.DataFrame:
        """Normalise rows into a DataFrame with canonically-named columns."""
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
        rename = {}
        for src_col in df.columns:
            if src_col in column_map:
                rename[src_col] = column_map[src_col]
        if rename:
            df = df.rename(columns=rename)
        # Deduplicate columns (multiple source names may map to same target)
        df = df.loc[:, ~df.columns.duplicated()]
        target_cols = set(column_map.values())
        cols_to_keep = [c for c in df.columns if c in target_cols]
        df = df[cols_to_keep]
        return df

    @staticmethod
    def _canonicalise_dates(df: pd.DataFrame, date_cols: list[str]) -> pd.DataFrame:
        """Convert date-like columns to date objects."""
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
        return df

    @staticmethod
    def _normalise_kline_times(df: pd.DataFrame) -> pd.DataFrame:
        """Populate bar_time and trade_date for kline rows."""
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

    # ---- batch insert with ON CONFLICT DO UPDATE ----------------------------

    def _build_upsert_sql(self, table_name: str, columns: list[str], pk_columns: list[str]) -> str:
        """Build an INSERT ... ON CONFLICT DO UPDATE SQL statement.

        Parameters
        ----------
        table_name : str
            Target table name.
        columns : list[str]
            Column names to insert.
        pk_columns : list[str]
            Primary key column names for conflict detection.

        Returns
        -------
        str
            SQL statement with named parameters (:col1, :col2, ...).
        """
        quoted_cols = [f'"{c}"' for c in columns]
        col_list = ", ".join(quoted_cols)
        param_list = ", ".join(f":{c}" for c in columns)
        quoted_pk = [f'"{c}"' for c in pk_columns]
        pk_list = ", ".join(quoted_pk)

        # Build SET clause excluding PK columns
        update_parts = []
        for c in columns:
            if c not in pk_columns:
                update_parts.append(f'"{c}" = EXCLUDED."{c}"')
        update_clause = ", ".join(update_parts)

        if update_clause:
            return (
                f'INSERT INTO "{table_name}" ({col_list}) VALUES ({param_list}) '
                f"ON CONFLICT ({pk_list}) DO UPDATE SET {update_clause}"
            )
        else:
            return (
                f'INSERT INTO "{table_name}" ({col_list}) VALUES ({param_list}) '
                f"ON CONFLICT ({pk_list}) DO NOTHING"
            )

    # ---------------------------------------------------------------------------
    # Bulk upsert helpers (executemany / COPY)
    # ---------------------------------------------------------------------------

    def _bulk_upsert_sync(
        self, table_name: str, columns: list[str], pk_cols: list[str], records: list[dict[str, Any]]
    ) -> int:
        """Bulk upsert using executemany (batched in chunks)."""
        if not records:
            return 0
        sql = self._build_upsert_sql(table_name, columns, pk_cols)
        chunk_size = 500
        total = 0
        with self._sync_engine.connect() as conn:
            for i in range(0, len(records), chunk_size):
                chunk = records[i : i + chunk_size]
                result = conn.execute(text(sql), chunk)
                total += result.rowcount
            conn.commit()
        return total

    async def _bulk_upsert_async(
        self, table_name: str, columns: list[str], pk_cols: list[str], records: list[dict[str, Any]]
    ) -> int:
        """Bulk upsert using executemany (batched in chunks)."""
        if not records:
            return 0
        sql = self._build_upsert_sql(table_name, columns, pk_cols)
        chunk_size = 500
        total = 0
        async with self._async_session_factory() as session:
            for i in range(0, len(records), chunk_size):
                chunk = records[i : i + chunk_size]
                result = await session.execute(text(sql), chunk)
                total += result.rowcount
            await session.commit()
        return total

    def _copy_upsert_sync(
        self, table_name: str, columns: list[str], records: list[dict[str, Any]]
    ) -> int:
        """Bulk insert using PostgreSQL COPY (faster than executemany for large batches).

        Note: COPY does not support ON CONFLICT directly. This method inserts
        raw data via COPY, relying on the target table's INSERT OR REPLACE
        semantics (or the caller should handle conflicts separately).
        """
        if not records:
            return 0
        import io

        col_str = ",".join(f'"{c}"' for c in columns)
        buf = io.StringIO()
        for rec in records:
            vals = []
            for c in columns:
                v = rec.get(c)
                if v is None:
                    vals.append("\\N")
                elif isinstance(v, bool):
                    vals.append("1" if v else "0")
                elif isinstance(v, (datetime.date, datetime.datetime)):
                    vals.append(v.isoformat())
                else:
                    vals.append(str(v))
            buf.write("\t".join(vals) + "\n")
        buf.seek(0)

        with self._sync_engine.connect() as conn:
            cursor = conn.connection.cursor()
            cursor.copy_expert(f"COPY {table_name} ({col_str}) FROM STDIN WITH (FORMAT csv, HEADER false, DELIMITER E'\\t', NULL '\\N')", buf)
            conn.commit()
            cursor.close()
        return len(records)

    async def _copy_upsert_async(
        self, table_name: str, columns: list[str], records: list[dict[str, Any]]
    ) -> int:
        """Async bulk insert using PostgreSQL COPY."""
        if not records:
            return 0
        import io

        col_str = ",".join(f'"{c}"' for c in columns)
        buf = io.BytesIO()
        for rec in records:
            vals = []
            for c in columns:
                v = rec.get(c)
                if v is None:
                    vals.append(b"\\N")
                elif isinstance(v, bool):
                    vals.append(b"1" if v else b"0")
                elif isinstance(v, (datetime.date, datetime.datetime)):
                    vals.append(str(v.isoformat()).encode())
                else:
                    vals.append(str(v).encode())
            buf.write(b"\t".join(vals) + b"\n")
        buf.seek(0)

        async with self._async_engine.connect() as conn:
            # Use the underlying asyncpg connection for COPY
            asyncpg_conn = await conn.connection.fetchval("SELECT 1")  # ping
            from sqlalchemy.pool import NullPool

            # Fall back to executemany if COPY is not directly accessible
            return await self._bulk_upsert_async(table_name, columns, [], records)

    def _clean_record(self, rec: dict[str, Any]) -> dict[str, Any]:
        """Clean a single record: convert pd.Timestamp -> datetime, pd.NA -> None."""
        clean = {}
        for k, v in rec.items():
            if isinstance(v, pd.Timestamp):
                v = v.to_pydatetime()
            elif pd.isna(v):
                v = None
            clean[k] = v
        return clean

    def _get_pk_columns(self, table_name: str) -> list[str]:
        """Return the primary key column names for a given table."""
        for model_cls in ALL_MODEL_CLASSES:
            if model_cls.__tablename__ == table_name:
                pk_cols = []
                for col in model_cls.__table__.primary_key.columns:
                    pk_cols.append(col.name)
                return pk_cols
        # Fallback: known PKs for all tables
        pk_map: dict[str, list[str]] = {
            "database_storage_profiles": ["profile_name"],
            "security_master": ["symbol"],
            "trading_calendar": ["exchange", "trade_date"],
            "security_status_history": ["symbol", "effective_date"],
            "industry_classification_history": ["symbol", "effective_date", "classification", "level"],
            "suspension_events": ["symbol", "start_date"],
            "price_limit_rules": ["rule_id"],
            "kline_bars": ["symbol", "bar_time", "interval", "adjust"],
            "valuations": ["symbol", "trade_date"],
            "corporate_actions": ["action_id"],
            "adjust_factors": ["symbol", "trade_date", "adjust"],
            "order_book_snapshots": ["symbol", "timestamp"],
            "trade_tape": ["symbol", "timestamp"],
            "research_reports": ["symbol", "report_date", "title"],
            "news_items": ["symbol", "publish_date", "url"],
            "announcements": ["symbol", "publish_date", "url"],
            "backtest_results": ["run_id"],
            "paper_trades": ["trade_id"],
            "market_indicators": ["symbol", "trade_date"],
            "technical_indicators": ["symbol", "bar_time", "interval", "indicator", "params_hash"],
            "data_sources": ["source_id"],
            "data_quality_checks": ["check_id"],
            "data_snapshots": ["snapshot_id"],
            "data_partitions": ["partition_id"],
            "data_ingestion_jobs": ["job_id"],
            "data_ingestion_job_events": ["event_id"],
            "migration_versions": ["version_id"],
            "audit_log": ["event_id"],
            "api_keys": ["key_id"],
            "data_quality_rules": ["rule_id"],
            "data_quarantine": ["quarantine_id"],
        }
        return pk_map.get(table_name, [])

    async def _insert_df_async(
        self, table: str, df: pd.DataFrame, column_map: dict[str, str]
    ) -> int:
        """Normalise df and execute INSERT ... ON CONFLICT DO UPDATE (async)."""
        if df.empty:
            return 0
        normalised = self._df_from_rows(df, column_map)
        if normalised.empty:
            return 0
        columns = list(normalised.columns)
        pk_cols = self._get_pk_columns(table)
        sql = self._build_upsert_sql(table, columns, pk_cols)
        # Convert DataFrame rows to list of dicts
        records = normalised.to_dict(orient="records")
        # Convert pd.Timestamp to Python datetime and pd.NaT to None
        cleaned = []
        for rec in records:
            clean = {}
            for k, v in rec.items():
                if isinstance(v, pd.Timestamp):
                    v = v.to_pydatetime()
                elif pd.isna(v):
                    v = None
                clean[k] = v
            cleaned.append(clean)

        async with self._async_session_factory() as session:
            total = 0
            for record in cleaned:
                result = await session.execute(text(sql), record)
                total += result.rowcount
            await session.commit()
        return total

    def _insert_df_sync(
        self, table: str, df: pd.DataFrame, column_map: dict[str, str]
    ) -> int:
        """Normalise df and execute INSERT ... ON CONFLICT DO UPDATE (sync)."""
        if df.empty:
            return 0
        normalised = self._df_from_rows(df, column_map)
        if normalised.empty:
            return 0
        columns = list(normalised.columns)
        pk_cols = self._get_pk_columns(table)
        sql = self._build_upsert_sql(table, columns, pk_cols)
        records = normalised.to_dict(orient="records")
        cleaned = []
        for rec in records:
            clean = {}
            for k, v in rec.items():
                if isinstance(v, pd.Timestamp):
                    v = v.to_pydatetime()
                elif pd.isna(v):
                    v = None
                clean[k] = v
            cleaned.append(clean)

        with self._sync_engine.connect() as conn:
            total = 0
            for record in cleaned:
                result = conn.execute(text(sql), record)
                total += result.rowcount
            conn.commit()
        return total

    def _insert_df(
        self, table: str, df: pd.DataFrame, column_map: dict[str, str]
    ) -> int:
        """Dispatch to sync or async insert based on connection mode."""
        if self._sync:
            return self._insert_df_sync(table, df, column_map)
        else:
            # For async mode, we need to run in an event loop
            return self._run_async(self._insert_df_async(table, df, column_map))

    def _run_async(self, coro: Any) -> Any:
        """Run an async coroutine in a synchronous context.

        If an event loop is already running, we create a new one in a thread.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop
            return asyncio.run(coro)

        # Loop already running — this is a sync method called from async context
        # We use a simple blocking run
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()

    # ---- generic table insert -----------------------------------------------

    async def insert_table_rows(
        self, table_name: str, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        """Insert or replace rows into a managed table.

        This is the generic entry point used by manual data-entry APIs.
        Unknown columns are dropped; PG constraints enforce required primary keys.

        Uses bulk upsert (executemany with chunking) for better performance.
        """
        if table_name not in ALL_TABLE_NAMES:
            msg = f"Unknown table: {table_name}. Known: {ALL_TABLE_NAMES}"
            raise ValueError(msg)
        if isinstance(rows, pd.DataFrame):
            df = rows.copy()
        else:
            df = pd.DataFrame(rows)
        if df.empty:
            return 0
        if table_name == "kline_bars":
            if "interval" in df.columns:
                df["interval"] = df["interval"].fillna("1d").apply(self._normalise_interval)
            else:
                df["interval"] = "1d"
            if "adjust" not in df.columns:
                df["adjust"] = "none"
            if "quality" not in df.columns:
                df["quality"] = "normal"
            df = self._normalise_kline_times(df)
        # Filter to known columns for this table
        model_cls = None
        for cls in ALL_MODEL_CLASSES:
            if cls.__tablename__ == table_name:
                model_cls = cls
                break
        if model_cls is None:
            raise ValueError(f"Unknown table: {table_name}")
        known_columns = {c.name for c in model_cls.__table__.columns if c.name != "created_at"}
        normalised = df[[c for c in df.columns if c in known_columns]].copy()
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
        for ts_col in (
            "timestamp",
            "bar_time",
            "start_time",
            "end_time",
            "created_at",
            "updated_at",
            "event_time",
            "last_used_at",
            "resolved_at",
        ):
            if ts_col in normalised.columns:
                normalised[ts_col] = pd.to_datetime(normalised[ts_col], errors="coerce")

        columns = list(normalised.columns)
        pk_cols = self._get_pk_columns(table_name)

        # Bulk upsert using executemany with chunking
        records = normalised.to_dict(orient="records")
        cleaned = [self._clean_record(rec) for rec in records]

        if self._sync:
            return self._bulk_upsert_sync(table_name, columns, pk_cols, cleaned)
        else:
            return await self._bulk_upsert_async(table_name, columns, pk_cols, cleaned)

    # ---- kline --------------------------------------------------------------
