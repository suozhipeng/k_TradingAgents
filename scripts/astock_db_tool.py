#!/usr/bin/env python3
"""Unified CLI tool for managing the AStock DuckDB local database.

Usage
-----
    python3 scripts/astock_db_tool.py list-tables
    python3 scripts/astock_db_tool.py stats
    python3 scripts/astock_db_tool.py export --table kline_bars --format csv --output ./data/
    python3 scripts/astock_db_tool.py import --table kline_bars --format csv --file ./data/bars.csv
    python3 scripts/astock_db_tool.py query --sql "SELECT symbol, count(*) FROM kline_bars GROUP BY symbol"
    python3 scripts/astock_db_tool.py vacuum
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure we can resolve the tradingagents package
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent  # scripts/ -> repo root
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tradingagents.astock.store.schema import AStockStore, init_astock_db


def _get_store(args: argparse.Namespace) -> AStockStore:
    db_path = args.db or "~/.tradingagents/astock/astock.duckdb"
    # If --memory is passed, use :memory:
    if getattr(args, "memory", False):
        db_path = ":memory:"
    store = init_astock_db(db_path)
    return store


def cmd_list_tables(args: argparse.Namespace) -> None:
    store = _get_store(args)
    tables = store.list_tables()
    if not tables:
        print("No tables found (database may be empty).")
    else:
        print("Tables:")
        for t in tables:
            print(f"  - {t}")
    store.close()


def cmd_stats(args: argparse.Namespace) -> None:
    store = _get_store(args)
    stats = store.get_table_stats()
    print(f"{'Table':<25} {'Rows':<10} {'Latest':<20}")
    print("-" * 55)
    for table_name, info in sorted(stats.items()):
        latest = info["latest_date"] or "-"
        print(f"{table_name:<25} {info['rows']:<10} {latest:<20}")
    store.close()


def cmd_export(args: argparse.Namespace) -> None:
    store = _get_store(args)
    output = args.output or f"./{args.table}.{args.format}"
    if os.path.isdir(output):
        output = os.path.join(output, f"{args.table}.{args.format}")
    result = store.export_table(args.table, fmt=args.format, output_path=output)
    print(f"Exported {args.table} → {result}")
    store.close()


def cmd_import(args: argparse.Namespace) -> None:
    store = _get_store(args)
    count = store.import_table(args.table, fmt=args.format, file_path=args.file)
    print(f"Imported {count} rows into {args.table}")
    store.close()


def cmd_query(args: argparse.Namespace) -> None:
    store = _get_store(args)
    df = store.query_sql(args.sql)
    print(df.to_string(index=False))
    store.close()


def cmd_vacuum(args: argparse.Namespace) -> None:
    store = _get_store(args)
    store.vacuum()
    print("Vacuum complete.")
    store.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AStock DuckDB local database tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to DuckDB database (default: ~/.tradingagents/astock/astock.duckdb)",
    )
    parser.add_argument(
        "--memory",
        action="store_true",
        help="Use in-memory database (for testing)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-tables
    subparsers.add_parser("list-tables", help="List all managed tables")

    # stats
    subparsers.add_parser("stats", help="Show row counts and latest dates per table")

    # export
    export_p = subparsers.add_parser("export", help="Export a table to file")
    export_p.add_argument("--table", required=True, help="Table name")
    export_p.add_argument(
        "--format",
        default="csv",
        choices=["csv", "parquet", "json"],
        help="Export format",
    )
    export_p.add_argument("--output", default=None, help="Output file or directory")

    # import
    import_p = subparsers.add_parser("import", help="Import data from file into table")
    import_p.add_argument("--table", required=True, help="Table name")
    import_p.add_argument(
        "--format",
        default="csv",
        choices=["csv", "parquet", "json"],
        help="Import format",
    )
    import_p.add_argument("--file", required=True, help="Source file path")

    # query
    query_p = subparsers.add_parser("query", help="Run a raw SQL query")
    query_p.add_argument("--sql", required=True, help="SQL query string")

    # vacuum
    subparsers.add_parser("vacuum", help="Reclaim storage / vacuum DB")

    args = parser.parse_args()

    command_map = {
        "list-tables": cmd_list_tables,
        "stats": cmd_stats,
        "export": cmd_export,
        "import": cmd_import,
        "query": cmd_query,
        "vacuum": cmd_vacuum,
    }

    handler = command_map.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
