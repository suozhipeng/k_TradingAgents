#!/usr/bin/env python3
"""
kline_engine — K 线数据引擎

从 baostock（免费/无限流/无反爬）拉取全市场 A 股 K 线（日/分钟），
写入 DuckDB（项目集成）和 SQLite（便携备份）。

参考：Sequoia-X (https://github.com/sngyai/Sequoia-X)
  · 多线程并行拉取（baostock 内部有 GIL 阻塞，多线程更安全）
  · 增量同步（检查 MAX(date)）
  · 指数退避重试
  · 定期重连防止长连接超时
  · 双后端写入
"""

from __future__ import annotations

import logging
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — 项目根目录下的 kline/ 目录
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
KLINE_DIR = _PROJECT_ROOT / "kline"
DEFAULT_DUCKDB_PATH = KLINE_DIR / "kline.duckdb"
DEFAULT_SQLITE_PATH = KLINE_DIR / "kline.sqlite"

# Baostock K 线字段（日/分钟通用）
BAOSTOCK_FIELDS = "date,open,high,low,close,volume,amount"

# 频率映射：CLI 参数 → baostock frequency 值 → 归一化 interval
FREQUENCY_MAP: dict[str, tuple[str, str]] = {
    "d":    ("d",  "1d"),
    "1d":   ("d",  "1d"),
    "day":  ("d",  "1d"),
    "daily":("d",  "1d"),
    "5m":   ("5",  "5m"),
    "5min": ("5",  "5m"),
    "15m":  ("15", "15m"),
    "15min":("15", "15m"),
    "30m":  ("30", "30m"),
    "30min":("30", "30m"),
    "60m":  ("60", "60m"),
    "60min":("60", "60m"),
}


def resolve_frequency(freq: str) -> tuple[str, str]:
    """将用户输入的频率解析为 (baostock_freq, normalized_interval)。"""
    key = freq.strip().lower()
    if key in FREQUENCY_MAP:
        return FREQUENCY_MAP[key]
    raise ValueError(f"不支持的频率: {freq!r}，支持: {', '.join(FREQUENCY_MAP)}")


def is_daily_freq(freq: str) -> bool:
    """判断是否为日线频率。"""
    return freq in ("d", "1d", "day", "daily")


# SQLite schema — 加入 freq 列以区分日/分钟数据
SQLITE_TABLE = "stock_daily"
SQLITE_CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {SQLITE_TABLE} (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol   TEXT    NOT NULL,
    date     TEXT    NOT NULL,
    open     REAL,
    high     REAL,
    low      REAL,
    close    REAL,
    volume   REAL,
    turnover REAL,
    freq     TEXT    NOT NULL DEFAULT 'd',
    UNIQUE (symbol, date, freq)
);
"""
SQLITE_INDEX_SQL = f"""
CREATE INDEX IF NOT EXISTS idx_symbol_date_freq ON {SQLITE_TABLE} (symbol, date, freq);
"""
SQLITE_INSERT_SQL = f"""
INSERT OR REPLACE INTO {SQLITE_TABLE} (symbol, date, open, high, low, close, volume, turnover, freq)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

# ---------------------------------------------------------------------------
# Helpers — stock code conversion
# ---------------------------------------------------------------------------
# Project uses "600519.SH" format. Baostock uses "sh.600519".
# Pure numeric codes: 6xx/9xx → sh, the rest → sz


def _to_baostock_code(symbol: str) -> str:
    """Convert project symbol (600519.SH) to baostock format (sh.600519)."""
    raw = symbol.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    prefix = "sh" if raw.startswith(("6", "9")) else "sz"
    return f"{prefix}.{raw}"


def _to_project_code(bs_symbol: str) -> str:
    """Convert baostock code (sh.600519) to project format (600519.SH)."""
    parts = bs_symbol.split(".")
    return f"{parts[1]}.{parts[0].upper()}"


# ---------------------------------------------------------------------------
# Stock list from baostock
# ---------------------------------------------------------------------------
QUERY_SYMBOLS_CACHE: list[str] | None = None


def fetch_all_symbols(force_refresh: bool = False) -> list[str]:
    """通过 baostock 获取全市场 A 股代码列表，缓存到进程全局变量。
    
    返回 project 格式的代码列表（如 600519.SH）。
    """
    global QUERY_SYMBOLS_CACHE
    if QUERY_SYMBOLS_CACHE is not None and not force_refresh:
        return QUERY_SYMBOLS_CACHE

    import baostock as bs

    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")

    try:
        rs = bs.query_stock_basic(code_name="", code="")
        symbols = []
        while rs.next():
            row = rs.get_row_data()
            code = row[0]       # "sh.600000" or "sz.000001"
            status = row[4]     # "1" = 上市
            stock_type = row[5] # "1" = 股票
            if status == "1" and stock_type == "1":
                symbols.append(_to_project_code(code))
        logger.info("获取股票列表: %d 只", len(symbols))
        QUERY_SYMBOLS_CACHE = symbols
        return symbols
    finally:
        bs.logout()


# ---------------------------------------------------------------------------
# Baostock thread-safe worker — per-thread login/logout, exponential retry
# ---------------------------------------------------------------------------
import threading

_thread_local = threading.local()


def _get_bs_conn():
    """Get or create a baostock connection for the current thread."""
    if not hasattr(_thread_local, 'bs'):
        import baostock as bs
        lg = bs.login()
        if lg.error_code != "0":
            raise RuntimeError(f"baostock login failed: {lg.error_msg}")
        _thread_local.bs = bs
    return _thread_local.bs


def _release_bs():
    """Logout baostock for the current thread."""
    if hasattr(_thread_local, 'bs'):
        try:
            _thread_local.bs.logout()
        except Exception:
            pass
        del _thread_local.bs


def _fetch_single(symbol: str, bs_code: str, start: str, end: str,
                  bs_freq: str, adjust: str, max_retries: int = 3) -> list[list[str]]:
    """Fetch K-line for one stock with exponential backoff retry."""
    import time as _time
    results = []
    for attempt in range(max_retries):
        try:
            bs = _get_bs_conn()
            rs = bs.query_history_k_data_plus(
                bs_code, BAOSTOCK_FIELDS,
                start_date=start, end_date=end,
                frequency=bs_freq, adjustflag=adjust,
            )
            if rs.error_code != "0":
                raise RuntimeError(rs.error_msg)
            while rs.next():
                results.append([symbol] + rs.get_row_data())
            return results
        except Exception as exc:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "[%s] attempt %d failed: %s, retrying in %ds",
                    symbol, attempt + 1, exc, wait,
                )
                _release_bs()
                _time.sleep(wait)
                # Force re-login on next attempt
                if hasattr(_thread_local, 'bs'):
                    del _thread_local.bs
            else:
                logger.warning("[%s] %d retries exhausted: %s", symbol, max_retries, exc)
    return results


# ---------------------------------------------------------------------------
# KlineStore — 双后端存储
# ---------------------------------------------------------------------------
class KlineStore:
    """K 线数据存储：同时管理 DuckDB（项目集成）和 SQLite（便携备份）。"""

    def __init__(
        self,
        duckdb_path: str | Path | None = None,
        sqlite_path: str | Path | None = None,
    ):
        self.duckdb_path = Path(duckdb_path or DEFAULT_DUCKDB_PATH)
        self.sqlite_path = Path(sqlite_path or DEFAULT_SQLITE_PATH)
        self._duckdb_store = None
        self._sqlite_conn: sqlite3.Connection | None = None

    # ── DuckDB ──────────────────────────────────────────────────────

    @property
    def duckdb_store(self):
        if self._duckdb_store is None:
            self.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
            from tradingagents.astock.store.schema import init_astock_db
            self._duckdb_store = init_astock_db(str(self.duckdb_path))
        return self._duckdb_store

    # ── SQLite ──────────────────────────────────────────────────────

    @property
    def sqlite_conn(self) -> sqlite3.Connection:
        if self._sqlite_conn is None:
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.sqlite_path))
            conn.execute(SQLITE_CREATE_SQL)
            conn.execute(SQLITE_INDEX_SQL)
            # ── 自动迁移：兼容旧版无 freq 列的 schema ──────────────
            try:
                conn.execute(f"ALTER TABLE {SQLITE_TABLE} ADD COLUMN freq TEXT NOT NULL DEFAULT 'd'")
            except sqlite3.OperationalError:
                pass  # 列已存在，忽略
            conn.commit()
            self._sqlite_conn = conn
        return self._sqlite_conn

    # ── Insert ──────────────────────────────────────────────────────

    def insert_kline(
        self,
        symbol: str,
        df: pd.DataFrame,
        interval: str = "1d",
        source: str = "baostock",
        write_duckdb: bool = True,
        write_sqlite: bool = True,
    ) -> int:
        """写入 K 线 DataFrame 到指定后端。返回写入行数。"""
        if df.empty:
            return 0

        rows = 0
        if write_duckdb:
            ddf = df.copy()
            rows = self.duckdb_store.insert_kline(symbol, ddf, interval=interval, source=source)

        if write_sqlite:
            self._insert_sqlite(symbol, df, interval)

        return rows

    def _insert_sqlite(self, symbol: str, df: pd.DataFrame, interval: str = "1d") -> int:
        conn = self.sqlite_conn
        freq_val = "d" if interval in ("1d", "day", "daily") else interval
        # 批量构建参数列表，避免逐行 execute 的 SQLite 往返开销
        params = [
            (
                symbol,
                str(row.get("date", "")),
                _safe_float(row.get("open")),
                _safe_float(row.get("high")),
                _safe_float(row.get("low")),
                _safe_float(row.get("close")),
                _safe_float(row.get("volume")),
                _safe_float(row.get("amount", row.get("turnover"))),
                freq_val,
            )
            for _, row in df.iterrows()
        ]
        conn.executemany(SQLITE_INSERT_SQL, params)
        conn.commit()
        logger.debug("[SQLite] %s freq=%s: %d rows", symbol, freq_val, len(params))
        return len(params)

    # ── Query ────────────────────────────────────────────────────────

    def query_kline(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
        interval: str = "1d",
        source_db: str = "duckdb",
    ) -> pd.DataFrame:
        """查询 K 线数据。"""
        if source_db == "duckdb":
            return self._query_duckdb(symbol, start, end, limit, interval)
        else:
            return self._query_sqlite(symbol, start, end, limit, interval)

    def _query_duckdb(
        self, symbol: str, start: str | None, end: str | None,
        limit: int | None, interval: str = "1d",
    ) -> pd.DataFrame:
        s = start.replace("-", "") if start else None
        e = end.replace("-", "") if end else None
        if s and len(s) == 8:
            s = f"{s[:4]}-{s[4:6]}-{s[6:]}"
        if e and len(e) == 8:
            e = f"{e[:4]}-{e[4:6]}-{e[6:]}"
        return self.duckdb_store.query_kline(symbol, start=s, end=e, limit=limit)

    def _query_sqlite(
        self, symbol: str, start: str | None, end: str | None,
        limit: int | None, interval: str = "1d",
    ) -> pd.DataFrame:
        conn = self.sqlite_conn
        freq_val = "d" if interval in ("1d", "day", "daily") else interval
        sql = f"SELECT * FROM {SQLITE_TABLE} WHERE symbol = ? AND freq = ?"
        params: list[Any] = [symbol, freq_val]

        if start:
            sql += " AND date >= ?"
            params.append(start.replace("-", ""))
        if end:
            sql += " AND date <= ?"
            params.append(end.replace("-", ""))
        sql += " ORDER BY date"

        if limit is not None:
            sql += " DESC LIMIT ?"
            params.append(limit)
            df = pd.read_sql(sql, conn, params=tuple(params))
            return df.sort_values("date").reset_index(drop=True)

        return pd.read_sql(sql, conn, params=tuple(params))

    # ── Stats ────────────────────────────────────────────────────────

    def get_stats(
        self, source_db: str = "duckdb", interval: str = "1d"
    ) -> pd.DataFrame:
        """返回各股票的条数、最早/最晚日期统计。"""
        freq_val = "d" if interval in ("1d", "day", "daily") else interval
        if source_db == "duckdb":
            return self.duckdb_store.query_sql(
                f"SELECT symbol, count(*) AS bars, min(bar_time) AS earliest, "
                f"max(bar_time) AS latest "
                f"FROM kline_bars WHERE interval='{interval}' "
                f"GROUP BY symbol ORDER BY symbol"
            )
        else:
            conn = self.sqlite_conn
            return pd.read_sql(
                f"SELECT symbol, count(*) AS bars, min(date) AS earliest, "
                f"max(date) AS latest "
                f"FROM {SQLITE_TABLE} WHERE freq='{freq_val}' "
                f"GROUP BY symbol ORDER BY symbol",
                conn,
            )

    def get_local_symbols(
        self, source_db: str = "duckdb", interval: str = "1d"
    ) -> list[str]:
        """返回本地已有数据的股票代码列表。"""
        freq_val = "d" if interval in ("1d", "day", "daily") else interval
        if source_db == "duckdb":
            df = self.duckdb_store.query_sql(
                f"SELECT DISTINCT symbol FROM kline_bars "
                f"WHERE interval='{interval}' ORDER BY symbol"
            )
        else:
            conn = self.sqlite_conn
            df = pd.read_sql(
                f"SELECT DISTINCT symbol FROM {SQLITE_TABLE} "
                f"WHERE freq='{freq_val}' ORDER BY symbol", conn
            )
        return df["symbol"].tolist() if not df.empty else []

    def get_last_date(
        self, symbol: str, source_db: str = "duckdb", interval: str = "1d"
    ) -> str | None:
        """返回某只股票本地最新日期（按 interval 过滤）。"""
        if source_db == "duckdb":
            df = self.duckdb_store.query_sql(
                f"SELECT max(bar_time) AS latest FROM kline_bars "
                f"WHERE symbol = '{symbol}' AND interval = '{interval}'"
            )
        else:
            freq_val = "d" if interval in ("1d", "day", "daily") else interval
            df = pd.read_sql(
                f"SELECT max(date) AS latest FROM {SQLITE_TABLE} "
                f"WHERE symbol = ? AND freq = ?",
                self.sqlite_conn,
                params=(symbol, freq_val),
            )
        val = df["latest"].iloc[0] if not df.empty else None
        if val is None:
            return None
        try:
            if hasattr(val, "strftime"):
                return val.strftime("%Y%m%d")
            return str(val).replace("-", "")[:8]
        except (ValueError, AttributeError):
            return None

    # ── Cleanup ─────────────────────────────────────────────────────

    def close(self) -> None:
        if self._duckdb_store is not None:
            try:
                self._duckdb_store.close()
            except Exception:
                pass
            self._duckdb_store = None
        if self._sqlite_conn is not None:
            try:
                self._sqlite_conn.close()
            except Exception:
                pass
            self._sqlite_conn = None


# ---------------------------------------------------------------------------
# Baostock 批量同步
# ---------------------------------------------------------------------------
def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _baostock_date_str(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _today_bs() -> str:
    return _baostock_date_str(date.today())


class BaostockSync:
    """baostock 批量同步器。

    支持日 K 和分钟 K（5/15/30/60），参考 Sequoia-X 的设计：
    · 多进程并行拉取
    · 增量同步：只拉取本地缺失的数据
    · 回填模式：全历史数据逐只股票拉取（带重试 + 定期重连）
    · 自动写入 DuckDB + SQLite
    """

    def __init__(
        self,
        store: KlineStore,
        n_workers: int = 8,
        backfill_retries: int = 3,
        reconnect_interval: int = 200,
    ):
        self.store = store
        self.n_workers = n_workers
        self.backfill_retries = backfill_retries
        self.reconnect_interval = reconnect_interval

    # ── 批量拉取（通用，用于今日增量或全市场回填） ────────────────

    def fetch_batch(
        self,
        symbols: list[str],
        start: str | None = None,
        end: str | None = None,
        frequency: str = "d",
        write_duckdb: bool = True,
        write_sqlite: bool = True,
    ) -> int:
        """多进程批量拉取指定股票的 K 线数据。

        Parameters
        ----------
        symbols : list[str]
            股票代码列表。
        start, end : str | None
            日期范围（YYYY-MM-DD）。None 表示拉取全部可用数据。
        frequency : str
            baostock frequency: "d", "5", "15", "30", "60"。
        """
        if not symbols:
            return 0

        today = _today_bs()
        start_str = start or "1990-01-01"
        end_str = end or today

        # 构建任务列表
        tasks = []
        for sym in symbols:
            tasks.append((sym, _to_baostock_code(sym), start_str, end_str, frequency))

        logger.info(
            "批量拉取 %d 只股票 [freq=%s, %s ~ %s]",
            len(tasks), frequency, start_str, end_str,
        )

        return self._run_batch(tasks, frequency, write_duckdb, write_sqlite)

    def _run_batch(
        self,
        tasks: list[tuple[str, str, str, str, str]],
        bs_freq: str,
        write_duckdb: bool,
        write_sqlite: bool,
    ) -> int:
        """将任务分片，多线程拉取后统一写入。

        使用 threading 而非 multiprocessing：baostock 内部有 GIL 阻塞，
        多线程更安全，且避免了多进程间 login/logout 互相干扰的问题。
        每只股票独立指数退避重试。
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not tasks:
            return 0

        n_workers = min(self.n_workers, len(tasks))
        if n_workers == 0:
            return 0

        # 分钟线不复权，日线后复权
        adjust = "3" if not is_daily_freq(bs_freq) else "1"

        logger.info("多线程拉取 %d 只股票 [freq=%s, workers=%d, adjust=%s]",
                     len(tasks), bs_freq, n_workers, adjust)

        all_rows = []
        failed = 0

        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            future_map = {}
            for sym, bs_code, start, end, freq in tasks:
                future = executor.submit(
                    _fetch_single, sym, bs_code, start, end, freq, adjust
                )
                future_map[future] = sym

            for future in as_completed(future_map):
                sym = future_map[future]
                try:
                    rows = future.result(timeout=30)
                    if rows:
                        all_rows.extend(rows)
                except Exception as exc:
                    failed += 1
                    logger.warning("[%s] fetch failed: %s", sym, exc)

        if failed:
            logger.warning("拉取完成：%d/%d 失败", failed, len(tasks))

        if not all_rows:
            logger.info("无新数据（可能非交易日）")
            return 0

        df = pd.DataFrame(
            all_rows,
            columns=["symbol", "date", "open", "high", "low", "close", "volume", "turnover"],
        )
        for col in ["open", "high", "low", "close", "volume", "turnover"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["close"])
        df = df[df["volume"] > 0]

        if df.empty:
            return 0

        interval = resolve_frequency(bs_freq)[1]

        total = 0
        for symbol, group in df.groupby("symbol"):
            g = group.rename(columns={"turnover": "amount"}).copy()
            rows = self.store.insert_kline(
                symbol, g, interval=interval, source="baostock",
                write_duckdb=write_duckdb, write_sqlite=write_sqlite,
            )
            total += rows

        logger.info("批量拉取完成 [freq=%s]，共写入 %d 条", bs_freq, total)
        return total

    # ── 增量同步（默认：全市场今日） ──────────────────────────────

    def sync_today(
        self,
        symbols: list[str] | None = None,
        frequency: str = "d",
        write_duckdb: bool = True,
        write_sqlite: bool = True,
    ) -> int:
        """增量同步：对指定或本地已有股票，只拉取缺失的今日数据。

        Parameters
        ----------
        symbols : list[str] | None
            要同步的股票列表。None 则使用本地已有数据的股票。
        frequency : str
            baostock frequency。
        """
        today = _today_bs()

        if symbols is None:
            interval = resolve_frequency(frequency)[1]
            symbols = self.store.get_local_symbols(source_db="duckdb", interval=interval)

        if not symbols:
            logger.warning("没有需要同步的股票")
            return 0

        tasks = []
        for sym in symbols:
            last_date = self.store.get_last_date(sym, interval=resolve_frequency(frequency)[1])
            if last_date and last_date.replace("-", "") >= today.replace("-", ""):
                continue
            start = today
            if last_date:
                last = last_date.replace("-", "")
                today_clean = today.replace("-", "")
                if last < today_clean:
                    from_dt = datetime.strptime(last, "%Y%m%d") + timedelta(days=1)
                    start = from_dt.strftime("%Y-%m-%d")
            tasks.append((sym, _to_baostock_code(sym), start, today, frequency))

        if not tasks:
            logger.info("所有股票已是最新，无需增量更新")
            return 0

        logger.info("增量更新 %d 只股票 [freq=%s]", len(tasks), frequency)
        return self._run_batch(tasks, frequency, write_duckdb, write_sqlite)

    # ── 回填（全历史） ─────────────────────────────────────────────

    def backfill(
        self,
        symbols: list[str] | None = None,
        frequency: str = "d",
        write_duckdb: bool = True,
        write_sqlite: bool = True,
        start_date: str = "19900101",
    ) -> int:
        """批量回填历史 K 线数据。

        参考 Sequoia-X：
        · 单只股票自动重试
        · 定期重连 baostock（防止长连接超时）
        · 已入库自动 skip
        · 分钟线不复权，日线后复权

        Parameters
        ----------
        symbols : list[str] | None
            股票列表。None 则获取全市场。
        frequency : str
            baostock frequency: "d", "5", "15", "30", "60"。
        start_date : str
            起始日期（YYYYMMDD）。分钟线建议用较近的日期。
        """
        if symbols is None:
            symbols = fetch_all_symbols()

        today_bs = _today_bs()
        total_written = 0
        success = 0
        skipped = 0
        failed = 0
        since_reconnect = 0
        bs_freq = frequency
        interval = resolve_frequency(bs_freq)[1]

        import baostock as bs

        def _login() -> bool:
            lg = bs.login()
            if lg.error_code != "0":
                logger.error("baostock 登录失败: %s", lg.error_msg)
                return False
            return True

        logger.info("开始回填 %d 只股票 [freq=%s] 的历史 K 线...", len(symbols), bs_freq)

        if not _login():
            return 0

        try:
            for i, sym in enumerate(symbols):
                last_date = self.store.get_last_date(sym, interval=interval)
                if last_date and last_date.replace("-", "") >= today_bs.replace("-", ""):
                    skipped += 1
                    self._log_progress(i, len(symbols), success, skipped, failed)
                    continue

                since_reconnect += 1
                if since_reconnect >= self.reconnect_interval:
                    bs.logout()
                    time.sleep(1)
                    if not _login():
                        logger.error("重连失败，终止回填")
                        return total_written
                    since_reconnect = 0

                if last_date:
                    last = last_date.replace("-", "")
                    start = (datetime.strptime(last, "%Y%m%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                else:
                    start = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")

                bs_code = _to_baostock_code(sym)
                adjust = "3" if not is_daily_freq(bs_freq) else "1"

                rows = None
                query_ok = False
                for attempt in range(self.backfill_retries):
                    try:
                        rs = bs.query_history_k_data_plus(
                            bs_code, BAOSTOCK_FIELDS,
                            start_date=start, end_date=today_bs,
                            frequency=bs_freq, adjustflag=adjust,
                        )
                        if rs.error_code != "0":
                            raise RuntimeError(rs.error_msg)
                        rows = []
                        while rs.next():
                            rows.append(rs.get_row_data())
                        query_ok = True
                        break
                    except Exception as exc:
                        if attempt < self.backfill_retries - 1:
                            wait = 2 ** (attempt + 1)
                            logger.warning(
                                "[%s] 第%d次失败: %s，%ds后重试",
                                sym, attempt + 1, exc, wait,
                            )
                            time.sleep(wait)
                            bs.logout()
                            time.sleep(1)
                            _login()
                        else:
                            logger.warning("[%s] %d次重试均失败，跳过", sym, self.backfill_retries)

                if not query_ok or not rows:
                    if not query_ok:
                        failed += 1
                    else:
                        skipped += 1
                    self._log_progress(i, len(symbols), success, skipped, failed)
                    continue

                df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume", "turnover"])
                for col in ["open", "high", "low", "close", "volume", "turnover"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                df = df.dropna(subset=["close"])
                df = df[df["volume"] > 0]

                if df.empty:
                    skipped += 1
                    self._log_progress(i, len(symbols), success, skipped, failed)
                    continue

                insert_df = df.rename(columns={"turnover": "amount"}).copy()
                written = self.store.insert_kline(
                    sym, insert_df, interval=interval, source="baostock",
                    write_duckdb=write_duckdb, write_sqlite=write_sqlite,
                )
                total_written += written
                success += 1
                self._log_progress(i, len(symbols), success, skipped, failed)

        finally:
            bs.logout()

        logger.info(
            "回填完成 [freq=%s] — 总写入: %d | 成功: %d | 跳过: %d | 失败: %d",
            bs_freq, total_written, success, skipped, failed,
        )
        return total_written

    @staticmethod
    def _log_progress(current: int, total: int, success: int, skipped: int, failed: int) -> None:
        if (current + 1) % 500 == 0 or (current + 1) == total:
            logger.info(
                "进度 %d/%d — 成功: %d | 跳过: %d | 失败: %d",
                current + 1, total, success, skipped, failed,
            )

    # ── 指定股票拉取 ─────────────────────────────────────────────

    def fetch_symbol(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "d",
        write_duckdb: bool = True,
        write_sqlite: bool = True,
    ) -> int:
        """拉取单只/多只指定股票的 K 线数据。"""
        import baostock as bs

        lg = bs.login()
        if lg.error_code != "0":
            raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")

        total = 0
        interval = resolve_frequency(frequency)[1]
        adjust = "3" if not is_daily_freq(frequency) else "1"

        try:
            symbols = [s.strip() for s in symbol.split(",") if s.strip()]
            for sym in symbols:
                last_date = self.store.get_last_date(sym, interval=interval)
                today_bs = _today_bs()
                if last_date:
                    last = last_date.replace("-", "")
                    start_dt = datetime.strptime(last, "%Y%m%d") + timedelta(days=1)
                    start_str = start_dt.strftime("%Y-%m-%d")
                elif start:
                    start_str = start
                else:
                    start_str = "1990-01-01"
                end_str = end or today_bs

                bs_code = _to_baostock_code(sym)
                rs = bs.query_history_k_data_plus(
                    bs_code, BAOSTOCK_FIELDS,
                    start_date=start_str, end_date=end_str,
                    frequency=frequency, adjustflag=adjust,
                )
                if rs.error_code != "0":
                    logger.warning("[%s] 查询失败: %s", sym, rs.error_msg)
                    continue

                rows = []
                while rs.next():
                    rows.append(rs.get_row_data())
                if not rows:
                    logger.info("[%s] 无数据", sym)
                    continue

                df = pd.DataFrame(
                    rows,
                    columns=["date", "open", "high", "low", "close", "volume", "turnover"],
                )
                for col in ["open", "high", "low", "close", "volume", "turnover"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                df = df.dropna(subset=["close"])
                df = df[df["volume"] > 0]

                insert_df = df.rename(columns={"turnover": "amount"}).copy()
                written = self.store.insert_kline(
                    sym, insert_df, interval=interval, source="baostock",
                    write_duckdb=write_duckdb, write_sqlite=write_sqlite,
                )
                total += written
                logger.info("[%s] %d bars written", sym, written)
        finally:
            bs.logout()

        return total
