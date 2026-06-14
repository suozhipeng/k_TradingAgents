"""DuckDB table definitions and AStockStore — the local database storage layer.

All tables use ``INSERT OR REPLACE`` semantics for upsert-style writes, with
``PRIMARY KEY`` constraints ensuring idempotent re-insertion.
"""

from __future__ import annotations

import csv
import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

import duckdb
import pandas as pd

# ---------------------------------------------------------------------------
# DDL for each table (IF NOT EXISTS, created in init_schema)
# ---------------------------------------------------------------------------

CREATE_KLINE_BARS = """
CREATE TABLE IF NOT EXISTS kline_bars (
    symbol VARCHAR,
    trade_date DATE,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,
    amount DOUBLE,
    turnover_rate DOUBLE,
    interval VARCHAR DEFAULT '1d',
    source VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, trade_date, interval)
)
"""

CREATE_VALUATIONS = """
CREATE TABLE IF NOT EXISTS valuations (
    symbol VARCHAR,
    trade_date DATE,
    pe DOUBLE,
    pb DOUBLE,
    market_cap DOUBLE,
    source VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, trade_date)
)
"""

CREATE_ORDER_BOOK_SNAPSHOTS = """
CREATE TABLE IF NOT EXISTS order_book_snapshots (
    symbol VARCHAR,
    timestamp TIMESTAMP,
    bid_price DOUBLE,
    bid_volume DOUBLE,
    ask_price DOUBLE,
    ask_volume DOUBLE,
    source VARCHAR,
    PRIMARY KEY (symbol, timestamp)
)
"""

CREATE_TRADE_TAPE = """
CREATE TABLE IF NOT EXISTS trade_tape (
    symbol VARCHAR,
    timestamp TIMESTAMP,
    price DOUBLE,
    volume DOUBLE,
    direction VARCHAR,
    source VARCHAR,
    PRIMARY KEY (symbol, timestamp)
)
"""

CREATE_RESEARCH_REPORTS = """
CREATE TABLE IF NOT EXISTS research_reports (
    symbol VARCHAR,
    report_date DATE,
    title VARCHAR,
    institution VARCHAR,
    analyst VARCHAR,
    rating VARCHAR,
    pdf_url VARCHAR,
    source VARCHAR,
    PRIMARY KEY (symbol, report_date, title)
)
"""

CREATE_NEWS_ITEMS = """
CREATE TABLE IF NOT EXISTS news_items (
    symbol VARCHAR,
    publish_date DATE,
    title VARCHAR,
    summary VARCHAR,
    url VARCHAR,
    source VARCHAR,
    PRIMARY KEY (symbol, publish_date, url)
)
"""

CREATE_ANNOUNCEMENTS = """
CREATE TABLE IF NOT EXISTS announcements (
    symbol VARCHAR,
    publish_date DATE,
    title VARCHAR,
    summary VARCHAR,
    url VARCHAR,
    PRIMARY KEY (symbol, publish_date, url)
)
"""

CREATE_BACKTEST_RESULTS = """
CREATE TABLE IF NOT EXISTS backtest_results (
    run_id VARCHAR,
    symbol VARCHAR,
    strategy_name VARCHAR,
    start_date DATE,
    end_date DATE,
    total_return DOUBLE,
    annualized_return DOUBLE,
    sharpe_ratio DOUBLE,
    max_drawdown DOUBLE,
    win_rate DOUBLE,
    total_trades INTEGER,
    params_json VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id)
)
"""

CREATE_PAPER_TRADES = """
CREATE TABLE IF NOT EXISTS paper_trades (
    trade_id VARCHAR,
    symbol VARCHAR,
    direction VARCHAR,
    price DOUBLE,
    volume DOUBLE,
    fees DOUBLE,
    trade_date DATE,
    strategy_name VARCHAR,
    actionable BOOLEAN DEFAULT FALSE,
    decision_scope VARCHAR DEFAULT 'paper_trading_only',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_id)
)
"""

CREATE_MARKET_INDICATORS = """
CREATE TABLE IF NOT EXISTS market_indicators (
    symbol VARCHAR,
    trade_date DATE,
    ma_5 DOUBLE,
    ma_20 DOUBLE,
    ma_60 DOUBLE,
    rsi_14 DOUBLE,
    atr_14 DOUBLE,
    volume_ma_5 DOUBLE,
    PRIMARY KEY (symbol, trade_date)
)
"""

# All tables in creation order
ALL_TABLE_DEFS: dict[str, str] = {
    "kline_bars": CREATE_KLINE_BARS,
    "valuations": CREATE_VALUATIONS,
    "order_book_snapshots": CREATE_ORDER_BOOK_SNAPSHOTS,
    "trade_tape": CREATE_TRADE_TAPE,
    "research_reports": CREATE_RESEARCH_REPORTS,
    "news_items": CREATE_NEWS_ITEMS,
    "announcements": CREATE_ANNOUNCEMENTS,
    "backtest_results": CREATE_BACKTEST_RESULTS,
    "paper_trades": CREATE_PAPER_TRADES,
    "market_indicators": CREATE_MARKET_INDICATORS,
}

# Column name remaps from provider payloads → DuckDB column names
# (dataframe column -> table column)
KLINE_COLUMN_MAP: dict[str, str] = {
    "date": "trade_date",
    "trade_date": "trade_date",
    "datetime": "trade_date",
    "time": "trade_date",
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
    "source": "source",
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
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._lock = threading.Lock()
        self._owns_conn = False

    # ---- connection management -------------------------------------------

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self.connect()
        assert self._conn is not None
        return self._conn

    @property
    def db_path(self) -> str:
        return self._db_path

    def connect(self) -> None:
        """Open (or reuse) the DuckDB connection."""
        if self._conn is not None:
            return
        self._conn = duckdb.connect(self._db_path)
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
        """Create all tables if they do not exist."""
        for ddl in ALL_TABLE_DEFS.values():
            self.conn.execute(ddl)

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
        # Rename known columns
        rename = {}
        for src_col in df.columns:
            if src_col in column_map:
                rename[src_col] = column_map[src_col]
        if rename:
            df = df.rename(columns=rename)
        # Keep only columns that exist in the column_map *values*
        target_cols = set(column_map.values())
        cols_to_keep = [c for c in df.columns if c in target_cols]
        df = df[cols_to_keep]
        return df

    @staticmethod
    def _canonicalise_dates(df: pd.DataFrame, date_cols: list[str]) -> pd.DataFrame:
        """Convert date-like columns to ``datetime.date``."""
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
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

    # ---- kline -----------------------------------------------------------

    def insert_kline(
        self, symbol: str, df: pd.DataFrame, interval: str = "1d", source: str = ""
    ) -> int:
        """Batch insert/replace kline bars for *symbol*."""
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "interval" not in df.columns:
            df["interval"] = interval
        if "source" not in df.columns:
            df["source"] = source
        df = self._canonicalise_dates(df, ["trade_date", "date", "datetime", "time"])
        return self._insert_df("kline_bars", df, KLINE_COLUMN_MAP)

    def query_kline(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Return kline bars as a DataFrame, sorted by trade_date."""
        sql = 'SELECT * FROM kline_bars WHERE symbol = ? AND "interval" = ?'
        params: list[Any] = [symbol, interval]
        if start:
            sql += " AND trade_date >= ?"
            params.append(start)
        if end:
            sql += " AND trade_date <= ?"
            params.append(end)
        sql += " ORDER BY trade_date"
        return self.conn.execute(sql, params).fetchdf()

    # ---- valuations ------------------------------------------------------

    def insert_valuations(
        self, symbol: str, df: pd.DataFrame, source: str = ""
    ) -> int:
        """Batch insert/replace valuation data for *symbol*."""
        if df.empty:
            return 0
        df = df.copy()
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
            "SELECT * FROM announcements WHERE symbol = ? ORDER BY publish_date",
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
                                "periods",
                                "fee_config_used",
                                "execution_signal",
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
                "SELECT * FROM backtest_results WHERE strategy_name = ? ORDER BY created_at",
                [strategy_name],
            ).fetchdf()
        return self.conn.execute(
            "SELECT * FROM backtest_results ORDER BY created_at"
        ).fetchdf()

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

    # ---- export / import (COPY TO / COPY FROM) ---------------------------

    EXPORT_FORMAT_MAP = {
        "csv": ("(FORMAT CSV, HEADER true)", ".csv"),
        "parquet": ("(FORMAT PARQUET)", ".parquet"),
        "json": ("(FORMAT JSON)", ".json"),
    }

    def export_table(
        self,
        table_name: str,
        fmt: str = "csv",
        output_path: str | None = None,
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

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn.execute(
            f'COPY (SELECT * FROM "{table_name}") TO ? {opts}',
            [output_path],
        )
        return output_path

    def import_table(
        self,
        table_name: str,
        fmt: str = "csv",
        file_path: str = "",
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
        result = self.conn.execute(
            f'INSERT OR REPLACE INTO "{table_name}" SELECT * FROM {reader_fn}(?)',
            [file_path],
        )
        row_count = result.fetchone()
        return row_count[0] if row_count else 0

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
            for date_col in ("trade_date", "report_date", "publish_date", "timestamp", "end_date", "trade_date"):
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


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def init_astock_db(db_path: str = "~/.tradingagents/astock/astock.duckdb") -> AStockStore:
    """Create an ``AStockStore``, call ``init_schema()``, and return it."""
    store = AStockStore(db_path)
    store.connect()
    store.init_schema()
    return store
