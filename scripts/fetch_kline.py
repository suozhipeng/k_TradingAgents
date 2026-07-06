#!/usr/bin/env python3
"""Fetch K-line data from the network (akshare) and save to local DuckDB.

STATUS: Legacy — kept as fallback data source.
For daily use, prefer ``scripts/kline_cli.py`` (baostock, dual backend,
multiprocess, no anti-crawl restrictions).

Convention
----------
DB is stored at the project ``kline/`` directory — the canonical data
directory so other tools can discover it by convention.
Override with ``--db`` for one-off exports.

Usage
-----
    # Fetch today's kline (default)
    python3 scripts/fetch_kline.py --symbol 600519.SH

    # Fetch all historical kline
    python3 scripts/fetch_kline.py --symbol 600519.SH --all

    # Multiple symbols
    python3 scripts/fetch_kline.py --symbol 600519.SH,300750.SZ

    # Weekly kline, custom DB
    python3 scripts/fetch_kline.py --symbol 600519.SH --interval 1w --all --db ./export.duckdb
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

# Ensure the tradingagents package is importable
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tradingagents.astock.data_sources.schema import AStockRequest
from tradingagents.astock.data_sources.adapters import AkshareAdapter
from tradingagents.astock.store.schema import init_astock_db

# ---------------------------------------------------------------------------
# Constants — canonical path: project root /kline/
# ---------------------------------------------------------------------------
_REPO_ROOT = _THIS_DIR.parent
KLINE_DIR = _REPO_ROOT / "kline"
DEFAULT_DB_PATH = KLINE_DIR / "kline.duckdb"


def fetch_and_save(
    store,
    adapter: AkshareAdapter,
    symbol: str,
    start_date: str | None,
    end_date: str | None = None,
    interval: str = "1d",
) -> int:
    """Fetch kline from network and insert into store. Returns row count."""
    request = AStockRequest(
        capability="kline",
        raw_symbol=symbol,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
    )

    response = adapter.get_kline(request)
    bars = (response or {}).get("data", response) or {}
    bar_list = bars.get("bars", [])
    if not bar_list:
        return 0

    import pandas as pd

    df = pd.DataFrame(bar_list)
    return store.insert_kline(symbol, df, interval=interval, source="akshare")


def cmd_fetch(args: argparse.Namespace) -> None:
    symbols = [s.strip() for s in args.symbol.split(",") if s.strip()]
    if not symbols:
        print("Error: at least one --symbol is required")
        sys.exit(1)

    # Ensure parent directory exists
    db_path = Path(args.db).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_str = str(db_path)

    interval = args.interval

    # Compute date range
    if args.all:
        start_date = None  # akshare defaults to earliest available
        end_date = None
        mode_label = "ALL dates"
    else:
        today_str = date.today().strftime("%Y%m%d")
        start_date = today_str
        end_date = today_str
        mode_label = f"today ({today_str})"

    store = init_astock_db(db_str)
    try:
        adapter = AkshareAdapter(timeout=30)

        from tqdm import tqdm

        total_rows = 0
        for sym in tqdm(symbols, desc="Symbols", unit="sym"):
            try:
                rows = fetch_and_save(
                    store, adapter, sym, start_date, end_date, interval
                )
                total_rows += rows
                if rows > 0:
                    tqdm.write(f"  ✓ {sym}: {rows} bars saved")
                else:
                    tqdm.write(f"  - {sym}: no data (market closed or invalid symbol)")
            except Exception as exc:
                tqdm.write(f"  ✗ {sym}: {exc}")

        print(f"\nDone: {total_rows} total rows written to {db_str}")
        print(
            f"  Mode: {mode_label} | Interval: {interval} | Symbols: {len(symbols)}"
        )

        # Quick summary
        stats = store.query_sql(
            "SELECT symbol, count(*) AS bars, min(bar_time) AS earliest, "
            "max(bar_time) AS latest "
            "FROM kline_bars WHERE source='akshare' "
            "GROUP BY symbol ORDER BY symbol"
        )
        if not stats.empty:
            print("\nSummary:")
            print(stats.to_string(index=False))

    finally:
        store.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch K-line data from network (akshare) → save to local DuckDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "-s",
        "--symbol",
        default="600519.SH",
        help="Stock symbol(s), comma-separated (default: 600519.SH)",
    )
    parser.add_argument(
        "-i",
        "--interval",
        default="1d",
        choices=["1m", "5m", "15m", "30m", "60m", "1d", "1w", "1mo"],
        help="K-line interval (default: 1d)",
    )
    parser.add_argument(
        "-d",
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"Path to DuckDB file (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Fetch ALL available historical bars (default: only today)",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    cmd_fetch(args)


if __name__ == "__main__":
    main()
