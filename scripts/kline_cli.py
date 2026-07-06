#!/usr/bin/env python3
"""
K 线数据 CLI — 一站式拉取、查询 A 股 K 线数据。

基于 baostock（免费/无限流/无反爬），写入 DuckDB（项目集成）+ SQLite（便携备份）。

Usage
-----
    # ── 拉取（默认拉取全市场当日日 K） ──

    # 拉取全市场所有股票当天日 K（默认）
    python3 scripts/kline_cli.py fetch

    # 拉取全市场所有股票的全部历史日 K（约 12 分钟）
    python3 scripts/kline_cli.py fetch --all

    # 拉取全市场今日 5 分钟 K 线
    python3 scripts/kline_cli.py fetch --frequency 5m

    # 拉取指定股票的全部历史
    python3 scripts/kline_cli.py fetch --symbol 600519.SH,300750.SZ --all

    # 指定输出后端
    python3 scripts/kline_cli.py fetch --duckdb-only

    # ── 查询 ──

    # 查询特定日期
    python3 scripts/kline_cli.py query --symbol 600519.SH --date 2025-06-01

    # 查询一段时间
    python3 scripts/kline_cli.py query --symbol 600519.SH --start 2025-01-01 --end 2025-06-30

    # 查询最近 N 条（日/分钟数据均可）
    python3 scripts/kline_cli.py query --symbol 600519.SH --latest 10
    python3 scripts/kline_cli.py query --symbol 600519.SH --frequency 5m --latest 20

    # 从 SQLite 查询
    python3 scripts/kline_cli.py query --symbol 600519.SH --from-sqlite --latest 5

    # ── 统计 ──

    python3 scripts/kline_cli.py stats
    python3 scripts/kline_cli.py stats --frequency 5m
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.kline_engine import (
    DEFAULT_DUCKDB_PATH,
    DEFAULT_SQLITE_PATH,
    BaostockSync,
    KlineStore,
    fetch_all_symbols,
    resolve_frequency,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("kline_cli")


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_fetch(args: argparse.Namespace) -> None:
    """拉取 K 线数据。

    默认行为（无任何标志）：全市场所有股票今天日 K。
    --all → 全市场全历史。
    --symbol → 指定股票。
    --frequency → 分钟线。
    """
    write_duckdb = not args.sqlite_only
    write_sqlite = not args.duckdb_only
    bs_freq, interval = resolve_frequency(args.frequency)

    store = KlineStore(duckdb_path=args.duckdb, sqlite_path=args.sqlite)
    sync = BaostockSync(store, n_workers=args.workers)

    try:
        if args.all:
            # ── 全市场全历史（回填） ──
            if args.symbol:
                symbols = [s.strip() for s in args.symbol.split(",") if s.strip()]
            else:
                logger.info("获取全市场股票列表...")
                symbols = fetch_all_symbols()

            total = sync.backfill(
                symbols=symbols, frequency=bs_freq,
                write_duckdb=write_duckdb, write_sqlite=write_sqlite,
            )
            label = f"freq={bs_freq}" if bs_freq != "d" else "daily"
            print(f"\n✅ 回填完成 [freq={bs_freq}]，共写入 {total} 条 K 线数据")

        elif args.symbol:
            # ── 指定股票 ──
            total = sync.fetch_symbol(
                symbol=args.symbol, frequency=bs_freq,
                write_duckdb=write_duckdb, write_sqlite=write_sqlite,
            )
            print(f"\n✅ 写入完成: {total} 条")

        else:
            # ── 默认：仅增量拉取本地已有数据的股票（避免全市场 5000+ 次请求超时） ──
            local_symbols = store.get_local_symbols(source_db="duckdb", interval=interval)
            if local_symbols:
                logger.info("本地已有 %d 只股票，增量拉取今日数据...", len(local_symbols))
                total = sync.sync_today(
                    symbols=local_symbols, frequency=bs_freq,
                    write_duckdb=write_duckdb, write_sqlite=write_sqlite,
                )
                print(f"\n✅ 增量拉取完成 [freq={bs_freq}]，共写入 {total} 条")
            else:
                logger.info("本地无已有数据，拉取全市场今日日 K...")
                all_symbols = fetch_all_symbols()
                total = sync.sync_today(
                    symbols=all_symbols, frequency=bs_freq,
                    write_duckdb=write_duckdb, write_sqlite=write_sqlite,
                )
                print(f"\n✅ 全市场当日增量拉取完成 [freq={bs_freq}]，共写入 {total} 条")

        # 显示统计
        print(f"\n📊 数据统计 [DuckDB, interval={interval}]:")
        stats = store.get_stats(source_db="duckdb", interval=interval)
        if not stats.empty:
            pd.set_option("display.max_rows", 20)
            print(stats.to_string(index=False))
        else:
            print("  (空)")

    finally:
        store.close()


def cmd_query(args: argparse.Namespace) -> None:
    """查询 K 线数据。"""
    source_db = "sqlite" if args.from_sqlite else "duckdb"
    _, interval = resolve_frequency(args.frequency)

    store = KlineStore(
        duckdb_path=args.duckdb if not args.from_sqlite else None,
        sqlite_path=args.sqlite if args.from_sqlite else None,
    )

    try:
        symbols = [s.strip() for s in args.symbol.split(",") if s.strip()]
        all_dfs = []

        for sym in symbols:
            if args.date:
                start = args.date.replace("-", "")
                end = start
            else:
                start = args.start.replace("-", "") if args.start else None
                end = args.end.replace("-", "") if args.end else None

            df = store.query_kline(
                symbol=sym, start=start, end=end,
                limit=args.latest, interval=interval,
                source_db=source_db,
            )
            if not df.empty:
                all_dfs.append(df)

        if not all_dfs:
            print("未找到匹配的数据")
            return

        result = pd.concat(all_dfs, ignore_index=True) if len(all_dfs) > 1 else all_dfs[0]

        pd.set_option("display.max_rows", 50)
        pd.set_option("display.width", 120)
        pd.set_option("display.float_format", lambda x: f"{x:.2f}")

        # DuckDB 和 SQLite 列名不同
        if source_db == "sqlite":
            cols = ["symbol", "date", "open", "high", "low", "close", "volume", "turnover", "freq"]
        else:
            cols = ["symbol", "bar_time", "open", "high", "low", "close", "volume", "amount"]

        display_cols = [c for c in cols if c in result.columns]
        print(result[display_cols].to_string(index=False))
        print(f"\n共 {len(result)} 条记录")

    finally:
        store.close()


def cmd_stats(args: argparse.Namespace) -> None:
    """显示数据统计。"""
    source_db = "sqlite" if args.from_sqlite else "duckdb"
    _, interval = resolve_frequency(args.frequency)

    store = KlineStore(
        duckdb_path=args.duckdb if not args.from_sqlite else None,
        sqlite_path=args.sqlite if args.from_sqlite else None,
    )

    try:
        stats = store.get_stats(source_db=source_db, interval=interval)
        if stats.empty:
            print(f"数据库为空 [{source_db}, interval={interval}]")
            return

        pd.set_option("display.max_rows", 50)
        pd.set_option("display.width", 120)

        total_bars = stats["bars"].sum()
        total_symbols = len(stats)
        print(f"\n📊 {source_db.upper()} 数据统计 [interval={interval}]:")
        print(f"   股票数: {total_symbols}")
        print(f"   总条数: {total_bars}")
        print()
        print(stats.to_string(index=False))

    finally:
        store.close()


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="K 线数据 CLI — 拉取 & 查询 A 股日 K / 分钟 K",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── 全局参数 ──
    parser.add_argument(
        "--duckdb",
        default=str(DEFAULT_DUCKDB_PATH),
        help=f"DuckDB 路径 (default: {DEFAULT_DUCKDB_PATH})",
    )
    parser.add_argument(
        "--sqlite",
        default=str(DEFAULT_SQLITE_PATH),
        help=f"SQLite 路径 (default: {DEFAULT_SQLITE_PATH})",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    def _add_freq(p):
        p.add_argument(
            "-f", "--frequency",
            default="1d",
            choices=["1d", "5m", "15m", "30m", "60m"],
            help="K 线频率: 1d (日), 5m, 15m, 30m, 60m (default: 1d)",
        )
        return p

    # ── fetch ──
    fetch_p = _add_freq(subparsers.add_parser("fetch", help="拉取 K 线数据（默认全市场当日）"))
    fetch_p.add_argument(
        "--symbol", "-s",
        default="",
        help="股票代码，逗号分隔。留空则为全市场",
    )
    fetch_p.add_argument(
        "--all", "-a",
        action="store_true",
        help="回填全市场全部历史 K 线（日 K 约 12 分钟）",
    )
    fetch_p.add_argument(
        "--workers", "-w",
        type=int,
        default=8,
        help="并行进程数 (default: 8)",
    )
    fetch_p.add_argument(
        "--duckdb-only",
        action="store_true",
        help="仅写入 DuckDB",
    )
    fetch_p.add_argument(
        "--sqlite-only",
        action="store_true",
        help="仅写入 SQLite",
    )
    fetch_p.set_defaults(func=cmd_fetch)

    # ── query ──
    query_p = _add_freq(subparsers.add_parser("query", help="查询 K 线数据"))
    query_p.add_argument(
        "--symbol", "-s",
        required=True,
        help="股票代码，逗号分隔",
    )
    date_group = query_p.add_mutually_exclusive_group()
    date_group.add_argument(
        "--date", "-d",
        help="查询特定日期 (YYYY-MM-DD 或 YYYYMMDD)",
    )
    date_group.add_argument(
        "--latest", "-n",
        type=int,
        help="查询最近 N 条",
    )
    query_p.add_argument("--start", help="起始日期 (YYYY-MM-DD)")
    query_p.add_argument("--end", help="截止日期 (YYYY-MM-DD)")
    query_p.add_argument(
        "--from-sqlite",
        action="store_true",
        help="从 SQLite 而非 DuckDB 查询",
    )
    query_p.set_defaults(func=cmd_query)

    # ── stats ──
    stats_p = _add_freq(subparsers.add_parser("stats", help="显示数据统计"))
    stats_p.add_argument(
        "--from-sqlite",
        action="store_true",
        help="显示 SQLite 而非 DuckDB 统计",
    )
    stats_p.set_defaults(func=cmd_stats)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
