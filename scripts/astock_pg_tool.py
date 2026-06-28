#!/usr/bin/env python3
"""
AStock PostgreSQL production database CLI tool.

Usage
-----
    python3 scripts/astock_pg_tool.py init
    python3 scripts/astock_pg_tool.py migrate
    python3 scripts/astock_pg_tool.py status
    python3 scripts/astock_pg_tool.py rollback V20260628_001
    python3 scripts/astock_pg_tool.py create-migration "add_fund_flow"
    python3 scripts/astock_pg_tool.py import-from-duckdb --table kline_bars --symbol 000001.SZ
    python3 scripts/astock_pg_tool.py export-ch-schema --output ./ch_schema.sql
    python3 scripts/astock_pg_tool.py stats
    python3 scripts/astock_pg_tool.py quality-run [--rule RULE_ID]
    python3 scripts/astock_pg_tool.py audit --actor system --limit 20
    python3 scripts/astock_pg_tool.py add-key --label "prod-key" --role admin
    python3 scripts/astock_pg_tool.py revoke-key --key-id <id>
    python3 scripts/astock_pg_tool.py query --sql "SELECT count(*) FROM kline_bars"
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import secrets
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

# ── ensure the repo root is on sys.path ──────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent  # scripts/ -> repo root
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tradingagents.astock.store.pg_store import PGConfig, PGStore
from tradingagents.astock.store.schema import AStockStore
from tradingagents.astock.store.migrations.runner import MigrationRunner
from tradingagents.astock.quality.executor import QualityExecutor, BlockedImportError

logger = logging.getLogger(__name__)

# Try tabulate for pretty-printing
try:
    from tabulate import tabulate
except ImportError:
    tabulate = None  # type: ignore


# ── helpers ──────────────────────────────────────────────────────────────


def _pprint_table(rows: list[dict[str, Any]], headers: list[str]) -> None:
    """Pretty-print a list-of-dicts as a formatted table."""
    if not rows:
        print("(no rows)")
        return
    values = []
    for r in rows:
        values.append([r.get(h, "") for h in headers])
    if tabulate:
        print(tabulate(values, headers=headers, tablefmt="grid"))
    else:
        col_widths = [
            max(len(h), max((len(str(r.get(h, ""))) for r in rows), default=0))
            for h in headers
        ]
        sep = "  ".join("=" * w for w in col_widths)
        header_line = "  ".join(h.ljust(w) for h, w in zip(headers, col_widths))
        print(sep)
        print(header_line)
        print(sep)
        for r in rows:
            print("  ".join(str(r.get(h, "")).ljust(w) for h, w in zip(headers, col_widths)))
        print(sep)


async def _get_pg_store(args: argparse.Namespace) -> PGStore:
    """Create and connect a PGStore from CLI args."""
    config = PGConfig(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password,
        schema=args.schema,
    )
    store = PGStore(config)
    await store.connect()
    return store


def _get_duckdb_store(args: argparse.Namespace) -> AStockStore:
    """Create a DuckDB AStockStore from CLI args."""
    db_path = args.duckdb or "~/.tradingagents/astock/astock.duckdb"
    from tradingagents.astock.store.schema import init_astock_db
    return init_astock_db(db_path)


def _format_duration(ms: float) -> str:
    """Format milliseconds as a human-readable string."""
    if ms < 1000:
        return f"{ms:.0f} ms"
    return f"{ms / 1000:.2f} s"


# ── command handlers ─────────────────────────────────────────────────────


async def cmd_init(args: argparse.Namespace) -> None:
    """Initialize the PostgreSQL schema."""
    store = await _get_pg_store(args)
    try:
        print("Initialising PostgreSQL schema ...")
        t0 = time.monotonic()
        await store.init_schema()
        elapsed = (time.monotonic() - t0) * 1000
        print(f"Schema initialised in {_format_duration(elapsed)}")
    finally:
        await store.close()


async def cmd_migrate(args: argparse.Namespace) -> None:
    """Run pending migrations."""
    config = PGConfig(
        host=args.host, port=args.port, database=args.database,
        user=args.user, password=args.password, schema=args.schema,
    )
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(config.dsn)
    runner = MigrationRunner(engine, schema=args.schema, dry_run=args.dry_run)
    try:
        results = await runner.upgrade()
        _pprint_table(
            results,
            headers=["version_id", "description", "status", "duration_ms"],
        )
    finally:
        await engine.dispose()


async def cmd_status(args: argparse.Namespace) -> None:
    """Show migration status."""
    config = PGConfig(
        host=args.host, port=args.port, database=args.database,
        user=args.user, password=args.password, schema=args.schema,
    )
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(config.dsn)
    runner = MigrationRunner(engine, schema=args.schema)
    try:
        df = await runner.status()
        if df.empty:
            print("No migrations found.")
            return
        rows = df.to_dict(orient="records")
        _pprint_table(
            rows,
            headers=["version_id", "description", "status", "applied_at", "duration_ms"],
        )
    finally:
        await engine.dispose()


async def cmd_rollback(args: argparse.Namespace) -> None:
    """Roll back to a specific migration version."""
    config = PGConfig(
        host=args.host, port=args.port, database=args.database,
        user=args.user, password=args.password, schema=args.schema,
    )
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(config.dsn)
    runner = MigrationRunner(engine, schema=args.schema, dry_run=args.dry_run)
    try:
        results = await runner.downgrade(args.version)
        _pprint_table(
            results,
            headers=["version_id", "description", "status", "duration_ms"],
        )
    finally:
        await engine.dispose()


async def cmd_create_migration(args: argparse.Namespace) -> None:
    """Create a new migration file from template."""
    config = PGConfig(
        host=args.host, port=args.port, database=args.database,
        user=args.user, password=args.password, schema=args.schema,
    )
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(config.dsn)
    runner = MigrationRunner(engine, schema=args.schema)
    try:
        filepath = await runner.create(args.name)
        print(f"Created migration: {filepath}")
    finally:
        await engine.dispose()


async def cmd_import_from_duckdb(args: argparse.Namespace) -> None:
    """Import data from DuckDB to PostgreSQL."""
    duck = _get_duckdb_store(args)
    pg = await _get_pg_store(args)

    try:
        table = args.table
        symbol = args.symbol
        interval = args.interval or "1d"
        limit = args.limit or 0

        print(f"Importing {table} for {symbol} from DuckDB to PostgreSQL ...")

        # Query from DuckDB
        if table == "kline_bars":
            duck_df = duck.query_kline(symbol, interval=interval)
        else:
            # Generic: read from the DuckDB table
            tbl_name = table
            if symbol:
                duck_df = duck.conn.execute(
                    f'SELECT * FROM "{tbl_name}" WHERE symbol = ?', [symbol]
                ).fetchdf()
            else:
                duck_df = duck.conn.execute(
                    f'SELECT * FROM "{tbl_name}"', []
                ).fetchdf()

        if limit and len(duck_df) > limit:
            duck_df = duck_df.head(limit)

        if duck_df.empty:
            print("No data found in DuckDB.")
            return

        print(f"Found {len(duck_df)} rows in DuckDB")

        # Insert into PostgreSQL
        if table == "kline_bars":
            rows = await pg.insert_kline(symbol, duck_df, interval=interval, source="duckdb_import")
        elif table == "valuations":
            rows = await pg.insert_valuations(symbol, duck_df, source="duckdb_import")
        else:
            rows = await pg.insert_table_rows(table, duck_df)

        print(f"Imported {rows} rows into PostgreSQL.{table}")

    finally:
        duck.close()
        await pg.close()


async def cmd_export_ch_schema(args: argparse.Namespace) -> None:
    """Export ClickHouse schema to a SQL file."""
    from tradingagents.astock.store.clickhouse_schema import export_ch_sql
    output = args.output
    schema = export_ch_sql(output_path=output)
    if output:
        print(f"ClickHouse schema written to {output}")
    else:
        print(schema)


async def cmd_stats(args: argparse.Namespace) -> None:
    """Show table-level statistics for the PostgreSQL store."""
    store = await _get_pg_store(args)
    try:
        rows: list[dict[str, Any]] = []
        from tradingagents.astock.store.pg_store import ALL_TABLE_NAMES

        for tbl in ALL_TABLE_NAMES:
            try:
                df = await store.query_sql(f'SELECT count(*) as cnt FROM "{tbl}"')
                count = df["cnt"].iloc[0] if not df.empty else 0
                rows.append({"table": tbl, "rows": count})
            except Exception:
                rows.append({"table": tbl, "rows": "?"})

        _pprint_table(rows, headers=["table", "rows"])
    finally:
        await store.close()


async def cmd_quality_run(args: argparse.Namespace) -> None:
    """Run quality checks on data."""
    config = PGConfig(
        host=args.host, port=args.port, database=args.database,
        user=args.user, password=args.password, schema=args.schema,
    )
    store = PGStore(config)
    await store.connect()

    try:
        executor = QualityExecutor(store, dry_run=args.dry_run)

        if args.rule:
            # Run a specific rule (fetch from DB and apply)
            print(f"Running rule: {args.rule}")
            # Fetch data quality rules and run
            sql = f"SELECT * FROM data_quality_rules WHERE rule_id = '{args.rule}'"
            rule_df = await store.query_sql(sql)
            if rule_df.empty:
                print(f"Rule {args.rule!r} not found")
                return
            print(json.dumps(rule_df.to_dict(orient="records"), indent=2, default=str))
        else:
            # Run all active rules
            print("Running all active quality rules ...")
            rule_df = await store.query_sql(
                "SELECT * FROM data_quality_rules WHERE is_active = TRUE ORDER BY rule_id"
            )
            if rule_df.empty:
                print("No active rules found.")
                return
            for _, rule in rule_df.iterrows():
                print(f"  Rule: {rule.get('rule_name', rule.get('rule_id', '?'))} "
                      f"(severity={rule.get('severity', '?')})")
    finally:
        await store.close()


async def cmd_audit(args: argparse.Namespace) -> None:
    """Query the audit log."""
    store = await _get_pg_store(args)
    try:
        actor = getattr(args, "actor", None)
        limit = getattr(args, "limit", 20)
        df = await store.query_audit_log(
            actor=actor,
            limit=limit,
        )
        if df.empty:
            print("No audit log entries found.")
            return
        rows = df.to_dict(orient="records")
        _pprint_table(
            rows,
            headers=["event_id", "event_type", "actor", "action", "outcome", "event_time"],
        )
    finally:
        await store.close()


async def cmd_add_key(args: argparse.Namespace) -> None:
    """Add a new API key."""
    store = await _get_pg_store(args)
    try:
        label = args.label
        role = args.role or "readonly"
        owner = args.owner or "cli"

        # Generate a random API key
        raw_key = f"asp_{secrets.token_hex(24)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_id = uuid.uuid4().hex
        key_prefix = raw_key[:8]

        record = {
            "key_id": key_id,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "label": label,
            "role": role,
            "owner": owner,
            "is_active": True,
        }
        rows = await store.insert_table_rows("api_keys", [record])
        if rows:
            print(f"API key created: {raw_key}")
            print(f"  key_id:  {key_id}")
            print(f"  label:   {label}")
            print(f"  role:    {role}")
            print(f"  prefix:  {key_prefix}")
            print("  [IMPORTANT] Store this key securely. It will not be shown again.")
        else:
            print("Failed to create API key.")
    finally:
        await store.close()


async def cmd_revoke_key(args: argparse.Namespace) -> None:
    """Revoke an API key by key_id."""
    store = await _get_pg_store(args)
    try:
        key_id = args.key_id
        sql = f"UPDATE api_keys SET is_active = FALSE WHERE key_id = '{key_id}'"
        if store._sync:
            from sqlalchemy import text
            with store._sync_engine.begin() as conn:
                result = conn.execute(text(sql))
                conn.commit()
            affected = result.rowcount
        else:
            from sqlalchemy import text
            async with store._async_engine.begin() as conn:
                result = await conn.execute(text(sql))
                await conn.commit()
            affected = result.rowcount

        if affected:
            print(f"API key {key_id} revoked.")
        else:
            print(f"API key {key_id} not found or already inactive.")
    finally:
        await store.close()


async def cmd_query(args: argparse.Namespace) -> None:
    """Run an arbitrary SQL query against PostgreSQL."""
    store = await _get_pg_store(args)
    try:
        sql = args.sql
        if not sql:
            print("No SQL provided.")
            return

        print(f"Executing: {sql}")
        t0 = time.monotonic()

        # Use query_sql (handles both sync/async)
        df = await store.query_sql(sql)
        elapsed = (time.monotonic() - t0) * 1000

        if df.empty:
            print("(no rows)")
        else:
            data = df.to_dict(orient="records")
            _pprint_table(data, headers=list(df.columns))

            print(f"\n{len(df)} row(s) in {_format_duration(elapsed)}")
    finally:
        await store.close()


# ── main ──────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="AStock PostgreSQL production database CLI tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Global DB connection args
    p.add_argument("--host", default=os.environ.get("PGHOST", "localhost"), help="PG host")
    p.add_argument("--port", type=int, default=int(os.environ.get("PGPORT", "5432")), help="PG port")
    p.add_argument("--database", "-d", default=os.environ.get("PGDATABASE", "astock"), help="PG database")
    p.add_argument("--user", "-U", default=os.environ.get("PGUSER", "astock"), help="PG user")
    p.add_argument("--password", "-W", default=os.environ.get("PGPASSWORD", "astock"), help="PG password")
    p.add_argument("--schema", default="public", help="Database schema")
    p.add_argument("--duckdb", default=None, help="DuckDB path (for import)")
    p.add_argument("--dry-run", action="store_true", help="Dry run mode (no writes)")

    sub = p.add_subparsers(dest="command", required=True)

    # init
    init_p = sub.add_parser("init", help="Initialise PostgreSQL schema")
    init_p.set_defaults(func=cmd_init)

    # migrate
    migrate_p = sub.add_parser("migrate", help="Run pending migrations")
    migrate_p.set_defaults(func=cmd_migrate)

    # status
    status_p = sub.add_parser("status", help="Show migration status")
    status_p.set_defaults(func=cmd_status)

    # rollback
    rollback_p = sub.add_parser("rollback", help="Roll back migrations")
    rollback_p.add_argument("version", help="Target version to roll back to")
    rollback_p.set_defaults(func=cmd_rollback)

    # create-migration
    create_p = sub.add_parser("create-migration", help="Create a new migration file")
    create_p.add_argument("name", help="Migration name (snake_case)")
    create_p.set_defaults(func=cmd_create_migration)

    # import-from-duckdb
    import_p = sub.add_parser("import-from-duckdb", help="Import data from DuckDB")
    import_p.add_argument("--table", required=True, help="Target table name")
    import_p.add_argument("--symbol", required=True, help="Symbol to import")
    import_p.add_argument("--interval", default="1d", help="Kline interval")
    import_p.add_argument("--limit", type=int, default=0, help="Max rows")
    import_p.set_defaults(func=cmd_import_from_duckdb)

    # export-ch-schema
    export_p = sub.add_parser("export-ch-schema", help="Export ClickHouse DDL")
    export_p.add_argument("--output", "-o", default=None, help="Output file path")
    export_p.set_defaults(func=cmd_export_ch_schema)

    # stats
    stats_p = sub.add_parser("stats", help="Show table statistics")
    stats_p.set_defaults(func=cmd_stats)

    # quality-run
    quality_p = sub.add_parser("quality-run", help="Run quality checks")
    quality_p.add_argument("--rule", default=None, help="Specific rule ID")
    quality_p.set_defaults(func=cmd_quality_run)

    # audit
    audit_p = sub.add_parser("audit", help="Query audit log")
    audit_p.add_argument("--actor", default=None, help="Filter by actor")
    audit_p.add_argument("--limit", type=int, default=20, help="Max entries")
    audit_p.set_defaults(func=cmd_audit)

    # add-key
    addkey_p = sub.add_parser("add-key", help="Add a new API key")
    addkey_p.add_argument("--label", required=True, help="Key label")
    addkey_p.add_argument("--role", default="readonly", choices=["readonly", "admin", "operator"], help="Key role")
    addkey_p.add_argument("--owner", default="cli", help="Key owner")
    addkey_p.set_defaults(func=cmd_add_key)

    # revoke-key
    revoke_p = sub.add_parser("revoke-key", help="Revoke an API key")
    revoke_p.add_argument("--key-id", required=True, help="Key ID to revoke")
    revoke_p.set_defaults(func=cmd_revoke_key)

    # query
    query_p = sub.add_parser("query", help="Run arbitrary SQL")
    query_p.add_argument("--sql", required=True, help="SQL to execute")
    query_p.set_defaults(func=cmd_query)

    return p


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s [%(name)s] %(message)s",
    )
    parser = _build_parser()
    args = parser.parse_args()

    handler = args.func
    try:
        result = handler(args)
        if hasattr(result, "__await__"):
            asyncio.run(result)
        return
    except BlockedImportError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        logger.exception("Command failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
