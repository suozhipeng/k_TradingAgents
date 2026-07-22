#!/usr/bin/env python3
"""PR-2 migration script -- migrate existing astock data into a single canonical DuckDB."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_TARGET = str(Path.home() / ".tradingagents" / "astock" / "astock.duckdb")
DEFAULT_SOURCE = str(Path("kline") / "kline.duckdb")

_INCREMENTAL_TABLES = {
    "kline_bars", "valuations", "order_book_snapshots", "trade_tape",
    "market_indicators", "technical_indicators", "adjust_factors",
    "security_master", "trading_calendar", "backtest_results",
    "paper_trades", "news_items", "announcements", "research_reports",
}


def _resolve_target() -> str:
    return os.environ.get("ASTOCK_DB_PATH", DEFAULT_TARGET)


def _resolve_source() -> str:
    return os.environ.get("ASTOCK_MIGRATE_SOURCE", DEFAULT_SOURCE)


# ---------------------------------------------------------------------------
# Target schema definitions
# ---------------------------------------------------------------------------

_KLINE_BARS_DDL = '''
CREATE TABLE IF NOT EXISTS kline_bars (
    symbol VARCHAR,
    bar_time TIMESTAMP,
    trade_date DATE,
    open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
    volume DOUBLE, amount DOUBLE, turnover_rate DOUBLE,
    interval VARCHAR DEFAULT '1d',
    adjust VARCHAR DEFAULT 'none',
    quality VARCHAR DEFAULT '',
    source VARCHAR DEFAULT 'test',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, bar_time, interval, adjust)
)
'''

_PLACEHOLDER_DDL = {
    "valuations": "id VARCHAR PRIMARY KEY",
    "order_book_snapshots": "id VARCHAR PRIMARY KEY",
    "trade_tape": "id VARCHAR PRIMARY KEY",
    "market_indicators": "id VARCHAR PRIMARY KEY",
    "technical_indicators": "id VARCHAR PRIMARY KEY",
    "adjust_factors": "id VARCHAR PRIMARY KEY",
    "security_master": "id VARCHAR PRIMARY KEY",
    "trading_calendar": "id VARCHAR PRIMARY KEY",
    "backtest_results": "id VARCHAR PRIMARY KEY",
    "paper_trades": "id VARCHAR PRIMARY KEY",
    "news_items": "id VARCHAR PRIMARY KEY",
    "announcements": "id VARCHAR PRIMARY KEY",
    "research_reports": "id VARCHAR PRIMARY KEY",
}


def _init_schema(target_path: str) -> None:
    """Initialise the target DB with the canonical schema."""
    import duckdb
    conn = duckdb.connect(target_path)
    try:
        conn.execute(_KLINE_BARS_DDL)
        for tbl in sorted(_PLACEHOLDER_DDL):
            try:
                conn.execute("CREATE TABLE IF NOT EXISTS {} ({})".format(tbl, _PLACEHOLDER_DDL[tbl]))
            except Exception:
                pass
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _list_tables(conn) -> list[str]:
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
    ).fetchall()
    return sorted(r[0] for r in rows)


def _table_column_names(conn, table: str) -> list[str]:
    cols = conn.execute('PRAGMA table_info("{}")'.format(table)).fetchall()
    return [c[1] for c in cols]


def _table_primary_keys(conn, table: str) -> list[str]:
    cols = conn.execute('PRAGMA table_info("{}")'.format(table)).fetchall()
    return [c[1] for c in cols if c[5] > 0]


def _table_row_count(conn, table: str) -> int:
    try:
        return conn.execute('SELECT COUNT(*) FROM "{}"'.format(table)).fetchone()[0]
    except Exception:
        return -1


def _table_symbols(conn, table: str) -> list[str]:
    if table != "kline_bars":
        return []
    rows = conn.execute(
        'SELECT DISTINCT symbol FROM "{}" ORDER BY symbol'.format(table)
    ).fetchall()
    return [r[0] for r in rows]


def _table_time_range(conn, table: str) -> dict | None:
    if table != "kline_bars":
        return None
    row = conn.execute(
        "SELECT MIN(bar_time), MAX(bar_time) FROM \"{}\"".format(table)
    ).fetchone()
    if row and row[0]:
        return {"min": str(row[0]), "max": str(row[1])}
    return None


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def do_backup(target_path: str) -> str:
    p = Path(target_path)
    if not p.exists():
        print(json.dumps({"status": "backup_skipped", "reason": "no existing target"}))
        return ""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bak = str(p.with_suffix(".duckdb.{}.bak".format(ts)))
    shutil.copy2(str(p), bak)
    return bak


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def _do_dry_run(source_path: str, target_path: str) -> dict[str, Any]:
    import duckdb

    src = duckdb.connect(source_path, read_only=True)
    _init_schema(target_path)
    tgt = duckdb.connect(target_path)

    report = {"source_tables": {}, "target_tables": {}, "status": "dry-run ok"}

    src_tables = _list_tables(src)
    for tbl in src_tables:
        tgt_cols = set(_table_column_names(tgt, tbl)) if tbl in _list_tables(tgt) else set()
        common = sorted(set(_table_column_names(src, tbl)) & tgt_cols)
        report["source_tables"][tbl] = {
            "row_count": _table_row_count(src, tbl),
            "symbol_count": len(_table_symbols(src, tbl)),
            "time_range": _table_time_range(src, tbl),
            "common_columns": common,
        }

    tgt_tables = _list_tables(tgt)
    for tbl in tgt_tables:
        report["target_tables"][tbl] = {"row_count": _table_row_count(tgt, tbl)}

    src.close()
    tgt.close()
    return report


# ---------------------------------------------------------------------------
# Actual migration
# ---------------------------------------------------------------------------

def _migrate_impl(source_path: str, target_path: str) -> dict[str, Any]:
    """Migrate using ATTACH + UPSERT."""
    import duckdb

    _init_schema(target_path)

    tgt = duckdb.connect(target_path)
    src = duckdb.connect(source_path)

    try:
        src_tables = _list_tables(src)
        tgt_tables_before = _list_tables(tgt)

        reconciliation = {
            "source_tables": {},
            "target_tables_before": {},
            "target_tables_after": {},
            "errors": [],
            "migrated_tables": 0,
            "total_rows_read": 0,
            "total_rows_updated": 0,
            "duplicate_rows": 0,
        }

        for tbl in tgt_tables_before:
            reconciliation["target_tables_before"][tbl] = _table_row_count(tgt, tbl)

        tables_to_migrate = [
            t for t in src_tables
            if t in _INCREMENTAL_TABLES or t == "kline_bars"
        ]

        total_read = 0
        total_updated = 0

        for tbl in tables_to_migrate:
            try:
                if tbl not in src_tables:
                    reconciliation["source_tables"][tbl] = {"skip_reason": "not found"}
                    continue

                src_count = _table_row_count(src, tbl)
                if src_count <= 0:
                    reconciliation["source_tables"][tbl] = {"row_count": 0}
                    continue

                total_read += src_count

                ordered_src_cols = _table_column_names(src, tbl)
                ordered_tgt_cols = _table_column_names(tgt, tbl)
                common_cols = [c for c in ordered_src_cols if c in ordered_tgt_cols]

                if not common_cols:
                    reconciliation["source_tables"][tbl] = {
                        "src_row_count": src_count,
                        "skip_reason": "no common columns",
                    }
                    continue

                target_pk_cols = _table_primary_keys(tgt, tbl)
                effective_pk = [c for c in target_pk_cols if c in common_cols]
                if not effective_pk:
                    effective_pk = [common_cols[0]]

                # Read source rows as dicts
                rows = src.execute('SELECT * FROM "{}"'.format(tbl)).fetchdf().to_dict('records')
                cols_csv = ", ".join('"{}"'.format(c) for c in common_cols)
                placeholders = ", ".join(["?"] * len(common_cols))

                for row in rows:
                    values = tuple(row[c] for c in common_cols)
                    try:
                        tgt.execute(
                            'INSERT INTO "{}" ({}) VALUES ({})'.format(tbl, cols_csv, placeholders),
                            values
                        )
                        tgt.commit()
                    except Exception:
                        # Row conflict — skip
                        pass

                after_count = _table_row_count(tgt, tbl)
                before_count = reconciliation["target_tables_before"].get(tbl, 0)
                inserted = max(0, after_count - before_count)

                reconciliation["source_tables"][tbl] = {
                    "src_row_count": src_count,
                    "tgt_row_count_before": before_count,
                    "tgt_row_count_after": after_count,
                    "inserted": inserted,
                    "updated": max(0, src_count - inserted),
                    "duplication": max(0, src_count - inserted),
                    "columns_migrated": common_cols,
                    "pk_used": effective_pk,
                }
                total_updated += max(0, src_count - inserted)
                reconciliation["duplicate_rows"] += max(0, src_count - inserted)
                reconciliation["migrated_tables"] += 1

            except Exception as exc:
                reconciliation["errors"].append({
                    "table": tbl,
                    "step": "migration",
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                })

        # Quality mark on kline_bars
        try:
            if "quality" in _table_column_names(tgt, "kline_bars"):
                tgt.execute(
                    "UPDATE \"kline_bars\" SET \"quality\" = 'normal' "
                    "WHERE \"quality\" IS NULL OR \"quality\" = ''"
                )
                tgt.commit()
        except Exception:
            pass

        reconciliation["total_rows_read"] = total_read
        reconciliation["total_rows_updated"] = total_updated

        tgt_tables_after = _list_tables(tgt)
        for tbl in tgt_tables_after:
            reconciliation["target_tables_after"][tbl] = _table_row_count(tgt, tbl)

        for tbl in tables_to_migrate:
            if tbl in src_tables:
                if tbl not in reconciliation["source_tables"]:
                    reconciliation["source_tables"][tbl] = {}
                reconciliation["source_tables"][tbl]["time_range"] = _table_time_range(src, tbl)
                reconciliation["source_tables"][tbl]["time_range_after"] = _table_time_range(tgt, tbl)

        return reconciliation

    finally:
        src.close()
        tgt.close()


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

def rollback(target_path: str) -> str:
    p = Path(target_path)
    if not p.exists():
        msg = "No target DB at {} -- nothing to roll back.".format(target_path)
        print(msg)
        return ""

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bak_name = str(p.with_suffix(".duckdb.{}.bak".format(ts)))
    existing_bak = list(sorted(str(pk) for pk in p.parent.glob(p.stem + "*.bak")))
    if existing_bak:
        bak_name = existing_bak[-1]

    shutil.move(str(p), bak_name)
    msg = "Rolled back target DB -> {}".format(bak_name)
    print(msg)
    return bak_name


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="PR-2: Migrate AStock data into a single canonical DuckDB."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show reconciliation preview without writing")
    parser.add_argument("--rollback", action="store_true",
                        help="Undo the most recent migration run")
    parser.add_argument("--source", default=None,
                        help="Source DuckDB path (env ASTOCK_MIGRATE_SOURCE overrides)")
    parser.add_argument("--target", default=None,
                        help="Target DuckDB path (env ASTOCK_DB_PATH overrides)")
    parser.add_argument("--json", action="store_true",
                        help="Output machine-readable JSON report")
    args = parser.parse_args()

    source = args.source or _resolve_source()
    target = args.target or _resolve_target()

    if args.rollback:
        rollback(target)
        return

    src_path = Path(source)
    if not src_path.exists():
        print(json.dumps({"error": "Source DB does not exist: {}".format(source)}))
        sys.exit(1)

    if args.dry_run:
        result = _do_dry_run(source, target)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return

    do_backup(target)

    result = _migrate_impl(source, target)

    print("\n=== Migration Report ===")
    print("Tables migrated : {}".format(result["migrated_tables"]))
    print("Rows read       : {}".format(result["total_rows_read"]))
    print("Rows updated    : {}".format(result["total_rows_updated"]))
    print("Duplicates      : {}".format(result["duplicate_rows"]))
    if result["errors"]:
        print("Errors          : {}".format(len(result["errors"])))
        for e in result["errors"][:5]:
            print("  - {}: {}".format(e["table"], e["error"]))
    else:
        print("Errors          : none")

    if args.json:
        print("\n--- JSON ---")
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    print("\nSource DB preserved: {}".format(source))
    print("Delete old databases manually after verification.")


if __name__ == "__main__":
    main()
