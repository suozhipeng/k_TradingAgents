#!/usr/bin/env python3
"""
AStock ClickHouse sync — bulk-copy data from DuckDB/PostgreSQL to ClickHouse.

Usage:
    # One-shot sync (cron-friendly)
    python3 scripts/astock_sync_ch.py --source duckdb --table kline_bars
    
    # Continuous watch (every 60s)
    python3 scripts/astock_sync_ch.py --source postgresql --watch

Configuration via env vars:
    CH_HOST, CH_PORT, CH_USER, CH_PASSWORD, CH_DB (default localhost:8123)
    PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD (for --source postgresql)
    DUCKDB_PATH (for --source duckdb, default ~/.tradingagents/astock/astock.duckdb)
"""

import argparse
import hashlib
import json
import logging
import os
import time
from datetime import datetime
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)

TABLE_MAP = {
    "kline_bars": "astock.kline_bars_ch",
    "valuations": "astock.valuations_ch",
    "order_book_snapshots": "astock.order_book_snapshots_ch",
    "trade_tape": "astock.trade_tape_ch",
    "market_indicators": "astock.market_indicators_ch",
    "technical_indicators": "astock.technical_indicators_ch",
    "adjust_factors": "astock.adjust_factors_ch",
    "security_status_history": "astock.security_status_history_ch",
    "industry_classification_history": "astock.industry_classification_history_ch",
    "suspension_events": "astock.suspension_events_ch",
    "corporate_actions": "astock.corporate_actions_ch",
}

CLICKHOUSE_BASE = os.environ.get("CH_HOST", "http://localhost:8123")
CLICKHOUSE_USER = os.environ.get("CH_USER", "astock")
CLICKHOUSE_PASSWORD = os.environ.get("CH_PASSWORD", "astock_ch_2026")


def _ch_query(sql: str) -> requests.Response:
    """Execute a ClickHouse query via HTTP interface."""
    url = f"{CLICKHOUSE_BASE}/?user={CLICKHOUSE_USER}&password={CLICKHOUSE_PASSWORD}"
    resp = requests.post(url, data=sql.encode("utf-8"), timeout=300)
    resp.raise_for_status()
    return resp


def _get_source_store(source: str):
    """Return a store object (DuckDB AStockStore or PGStore sync)."""
    if source == "duckdb":
        from tradingagents.astock.store.schema import init_astock_db
        path = os.environ.get("DUCKDB_PATH", "~/.tradingagents/astock/astock.duckdb")
        return init_astock_db(path)
    elif source == "postgresql":
        from tradingagents.astock.store.pg_store import PGConfig, PGStore
        config = PGConfig(
            host=os.environ.get("PG_HOST", "localhost"),
            port=int(os.environ.get("PG_PORT", "5432")),
            database=os.environ.get("PG_DB", "astock"),
            user=os.environ.get("PG_USER", "astock"),
            password=os.environ.get("PG_PASSWORD", "astock_prod_2026"),
        )
        store = PGStore(config, sync=True)
        import asyncio
        asyncio.run(store.connect())
        return store
    raise ValueError(f"Unknown source: {source}")


def _validate_date(date_str: str) -> str:
    """Validate date string is YYYY-MM-DD format. Returns the validated string or raises."""
    import re
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise ValueError(f"Invalid date format: {date_str!r}. Expected YYYY-MM-DD")
    # Verify it parses correctly
    from datetime import datetime
    datetime.strptime(date_str, "%Y-%m-%d")
    return date_str


def sync_table(store, table: str, ch_table: str, since: str | None = None, limit: int = 100000) -> dict[str, Any]:
    """Sync one table from source store to ClickHouse."""
    # Use explicit column projection excluding PG admin columns
    if table == "kline_bars":
        cols = "symbol, bar_time, trade_date, open, high, low, close, volume, amount, turnover_rate, interval, adjust, quality, source"
    elif table == "valuations":
        cols = "symbol, trade_date, pe, pb, market_cap, source"
    else:
        cols = "*"
    sql = f"SELECT {cols} FROM {table}"
    if since:
        _validate_date(since)
        if table == "kline_bars":
            sql += f" WHERE bar_time >= '{since}'"
        elif table in ("valuations", "market_indicators"):
            sql += f" WHERE trade_date >= '{since}'"
    sql += f" LIMIT {limit}"

    import asyncio
    if hasattr(store, "query_sql"):
        df = store.query_sql(sql) if not asyncio.iscoroutinefunction(store.query_sql) else asyncio.run(store.query_sql(sql))
    else:
        df = store.conn.execute(sql).fetchdf() if hasattr(store, "conn") else pd.DataFrame()

    if df.empty:
        return {"table": table, "rows": 0, "status": "no_data"}

    # Clean NaN/NaT/None to CH-compatible NULL representation
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].fillna("").astype(str).replace("", "\\N").replace("nan", "\\N").replace("None", "\\N")
        elif df[col].dtype.kind in ("M",):  # datetime
            df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
        elif df[col].dtype.kind == "O":  # object (could be dates)
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

    # Convert to CSV (ClickHouse native format for HTTP bulk insert)
    csv_buffer = df.to_csv(index=False, header=False, na_rep="\\N").encode("utf-8")

    resp = requests.post(
        f"{CLICKHOUSE_BASE}/?user={CLICKHOUSE_USER}&password={CLICKHOUSE_PASSWORD}",
        params={"query": f"INSERT INTO {ch_table} ({cols}) FORMAT CSV"},
        data=csv_buffer,
        timeout=300,
    )
    resp.raise_for_status()
    return {"table": table, "ch_table": ch_table, "rows": len(df), "status": "ok"}


def sync_all(store, since: str | None = None) -> list[dict[str, Any]]:
    """Sync all mapped tables."""
    results = []
    for table, ch_table in TABLE_MAP.items():
        try:
            r = sync_table(store, table, ch_table, since=since)
            results.append(r)
            logger.info("Synced %s → %s: %d rows (%s)", table, ch_table, r["rows"], r["status"])
        except Exception as exc:
            logger.error("Failed to sync %s → %s: %s", table, ch_table, exc)
            results.append({"table": table, "status": "error", "error": str(exc)})
    return results


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="AStock → ClickHouse sync")
    parser.add_argument("--source", default=None, choices=["duckdb", "postgresql", "auto"],
                        help="Source database (auto = read from backend.json config)")
    parser.add_argument("--table", default=None, help="Specific table to sync")
    parser.add_argument("--since", default=None, help="Sync data since this date (YYYY-MM-DD)")
    parser.add_argument("--watch", action="store_true", help="Continuous sync every 60s")
    parser.add_argument("--interval", type=int, default=60, help="Watch interval in seconds")
    args = parser.parse_args()

    # Resolve source: auto → read from BackendManager
    source = args.source
    if source is None or source == "auto":
        try:
            from tradingagents.astock.store.backend import backend_mgr
            source = backend_mgr.current_backend
            logger.info("Auto-detected backend: %s", source)
        except Exception:
            source = "duckdb"
            logger.info("Falling back to: %s", source)

    store = _get_source_store(source)

    if args.watch:
        logger.info("Starting continuous sync (every %ds)...", args.interval)
        while True:
            results = sync_all(store, since=args.since)
            logger.info("Sync complete: %d/%d OK", sum(1 for r in results if r["status"] == "ok"), len(results))
            time.sleep(args.interval)
    elif args.table:
        ch_table = TABLE_MAP.get(args.table)
        if not ch_table:
            print(f"Unknown table: {args.table}. Known: {list(TABLE_MAP)}")
            return
        result = sync_table(store, args.table, ch_table, since=args.since)
        print(json.dumps(result, indent=2))
    else:
        results = sync_all(store, since=args.since)
        print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
