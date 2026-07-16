"""CSV/SQLite cache layer for TDX market data.

Provides a persistent local cache for TDX-sourced kline data to avoid repeated
network calls and to enable offline backtesting use.  Uses SQLite as the
primary backend with a fallback to CSV files when SQLite is unavailable.

Cache directory
---------------
Default: ``~/.tradingagents/tdx_cache/``

Cache entries have:
- ``symbol`` — canonical A-share symbol (e.g. ``600519.SH``)
- ``capability`` — e.g. ``kline``
- ``interval`` — e.g. ``1d``, ``5m``, etc.
- ``source`` — e.g. ``tdx_vipdoc``, ``tdx_pytdx``
- ``data`` — JSON-serialised payload
- ``updated_at`` — ISO-8601 timestamp of last write
- ``stale`` — 0 = fresh, 1 = stale
"""

from __future__ import annotations

import csv
import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from tradingagents.astock.time_utils import utc_now, utc_now_iso
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .errors import AStockNoDataError, AStockSourceUnavailableError

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────

_CACHE_DIR = Path.home() / ".tradingagents" / "tdx_cache"
_DB_FILENAME = "tdx_cache.db"
_CSV_SUBDIR = "csv"
_TABLE_NAME = "tdx_cache"

# Default max age per capability (seconds)
# - Daily kline: 1 hour (safe to reuse during trading day)
# - Minute kline: 5 minutes
_DEFAULT_MAX_AGE: Dict[str, float] = {
    "kline": 3600.0,  # 1 hour
    "kline_1d": 3600.0,
    "kline_5m": 300.0,
    "kline_30m": 600.0,
    "kline_60m": 900.0,
    "order_book": 15.0,
    "trade_tape": 300.0,
    "valuation": 3600.0,
    "f10": 86400.0,  # 24 hours
    "fundamentals": 86400.0,
}


def _default_max_age(capability: str, interval: str = "") -> float:
    """Look up the max age (seconds) for a capability + interval pair."""
    if interval:
        key = "{0}_{1}".format(capability, interval)
        if key in _DEFAULT_MAX_AGE:
            return _DEFAULT_MAX_AGE[key]
    return _DEFAULT_MAX_AGE.get(capability, 3600.0)


# ── SQLite backend ────────────────────────────────────────────────────────


def _init_sqlite(db_path: Path) -> sqlite3.Connection:
    """Create/open the SQLite database and ensure the schema exists."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS {0} (
            symbol      TEXT NOT NULL,
            capability  TEXT NOT NULL,
            interval    TEXT NOT NULL DEFAULT '1d',
            source      TEXT,
            data        TEXT,
            updated_at  TEXT NOT NULL,
            stale       INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (symbol, capability, interval)
        )
        """.format(_TABLE_NAME)
    )
    conn.commit()
    return conn


# ── CSV backend ───────────────────────────────────────────────────────────


def _csv_path(base_dir: Path, symbol: str, capability: str, interval: str) -> Path:
    """Return the CSV file path for a cache entry."""
    csv_dir = base_dir / _CSV_SUBDIR
    csv_dir.mkdir(parents=True, exist_ok=True)
    # Sanitise symbol for filename
    safe_symbol = symbol.replace(".", "_").replace("/", "_")
    return csv_dir / "{0}_{1}_{2}.csv".format(safe_symbol, capability, interval)


# ── Cache class ──────────────────────────────────────────────────────────


@dataclass
class _CacheMeta:
    symbol: str
    capability: str
    interval: str
    source: str
    updated_at: str
    stale: int = 0


class TdxCache:
    """Persistent local cache for TDX market data.

    Uses SQLite as the primary backend.  Falls back to CSV when SQLite
    initialisation fails.

    Parameters
    ----------
    cache_dir : str or Path, optional
        Override the cache directory.  Defaults to ``~/.tradingagents/tdx_cache/``.
    max_age : dict, optional
        Per-capability max age in seconds.  Merged with ``_DEFAULT_MAX_AGE``.
    """

    def __init__(
        self,
        cache_dir: Optional[os.PathLike] = None,
        max_age: Optional[Dict[str, float]] = None,
    ) -> None:
        self._base_dir = Path(cache_dir) if cache_dir else _CACHE_DIR
        self._max_age: Dict[str, float] = dict(_DEFAULT_MAX_AGE)
        if max_age:
            self._max_age.update(max_age)

        self._db_path = self._base_dir / _DB_FILENAME
        self._conn: Optional[sqlite3.Connection] = None
        self._use_csv = False
        self._lock = threading.RLock()

        # Try initialising SQLite
        try:
            self._conn = _init_sqlite(self._db_path)
            logger.debug("tdx_cache: using SQLite at %s", self._db_path)
        except Exception as exc:
            logger.warning(
                "tdx_cache: SQLite init failed (%s), falling back to CSV", exc
            )
            self._use_csv = True
            self._base_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────

    def get(
        self, symbol: str, capability: str, interval: str = "1d"
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a cache entry.

        Returns ``None`` if the entry is missing, stale, or expired.
        """
        key = self._cache_key(capability, interval)

        with self._lock:
            if self._use_csv:
                return self._get_csv(symbol, capability, interval, key)
            return self._get_sqlite(symbol, capability, interval, key)

    def set(
        self,
        symbol: str,
        capability: str,
        interval: str,
        data: Dict[str, Any],
        source: str = "tdx",
    ) -> None:
        """Write a cache entry.

        Parameters
        ----------
        symbol : str
            Canonical symbol.
        capability : str
            Router capability name (e.g. ``kline``).
        interval : str
            Bar interval (e.g. ``1d``, ``5m``).
        data : dict
            The payload to cache (serialised to JSON).
        source : str
            Source identifier (e.g. ``tdx_pytdx``, ``tdx_vipdoc``).
        """
        now = utc_now().isoformat() + "Z"

        with self._lock:
            if self._use_csv:
                self._set_csv(symbol, capability, interval, data, source, now)
            else:
                self._set_sqlite(symbol, capability, interval, data, source, now)

    def is_stale(
        self, symbol: str, capability: str, interval: str = "1d"
    ) -> bool:
        """Check if a cached entry is past its max age."""
        entry = self.get(symbol, capability, interval)
        if entry is None:
            return True  # No entry is effectively stale
        # The get() already filters expired entries, so if we got one it
        # should be fresh.  Double-check the meta.
        meta = entry.get("_meta")
        if meta is None:
            return True
        return bool(meta.get("stale", 1))

    def clear(self, symbol: Optional[str] = None) -> None:
        """Clear all cache entries, or entries for a specific symbol."""
        with self._lock:
            if self._use_csv:
                self._clear_csv(symbol)
            else:
                self._clear_sqlite(symbol)

    def close(self) -> None:
        """Close the SQLite connection if open."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception as e:
                    logger.debug("Operation failed: {0}", e)
                self._conn = None

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _cache_key(capability: str, interval: str) -> str:
        return "{0}_{1}".format(capability, interval)

    def _is_expired(self, updated_at_str: str, key: str) -> bool:
        """Return True if the entry is past its max age."""
        max_age = self._max_age.get(key, 3600.0)
        if max_age <= 0:
            return False  # No expiry
        try:
            updated_dt = datetime.fromisoformat(updated_at_str.replace("Z", ""))
            age = (utc_now() - updated_dt).total_seconds()
            return age > max_age
        except (ValueError, TypeError):
            return True  # Can't parse timestamp — treat as expired

    # ── SQLite operations ─────────────────────────────────────────────

    def _get_sqlite(
        self, symbol: str, capability: str, interval: str, key: str
    ) -> Optional[Dict[str, Any]]:
        if self._conn is None:
            return None
        cursor = self._conn.execute(
            "SELECT source, data, updated_at, stale FROM {0} "
            "WHERE symbol=? AND capability=? AND interval=?".format(_TABLE_NAME),
            (symbol, capability, interval),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        source, data_json, updated_at, stale = row

        # Check expiry
        if self._is_expired(updated_at, key) or stale:
            return None

        try:
            data = json.loads(data_json) if data_json else {}
        except (json.JSONDecodeError, TypeError):
            return None

        # Attach metadata
        data["_meta"] = {
            "symbol": symbol,
            "capability": capability,
            "interval": interval,
            "source": source,
            "updated_at": updated_at,
            "stale": stale,
        }
        return data

    def _set_sqlite(
        self,
        symbol: str,
        capability: str,
        interval: str,
        data: Dict[str, Any],
        source: str,
        now: str,
    ) -> None:
        if self._conn is None:
            return

        # Strip any _meta from data before serialising
        clean_data = {k: v for k, v in data.items() if k != "_meta"}
        data_json = json.dumps(clean_data, ensure_ascii=False, default=str)

        self._conn.execute(
            "INSERT OR REPLACE INTO {0} (symbol, capability, interval, source, data, updated_at, stale) "
            "VALUES (?, ?, ?, ?, ?, ?, 0)".format(_TABLE_NAME),
            (symbol, capability, interval, source, data_json, now),
        )
        self._conn.commit()

    def _clear_sqlite(self, symbol: Optional[str] = None) -> None:
        if self._conn is None:
            return
        if symbol:
            self._conn.execute(
                "DELETE FROM {0} WHERE symbol=?".format(_TABLE_NAME), (symbol,)
            )
        else:
            self._conn.execute("DELETE FROM {0}".format(_TABLE_NAME))
        self._conn.commit()

    # ── CSV fallback operations ───────────────────────────────────────

    def _get_csv(
        self, symbol: str, capability: str, interval: str, key: str
    ) -> Optional[Dict[str, Any]]:
        csv_file = _csv_path(self._base_dir, symbol, capability, interval)
        if not csv_file.exists():
            return None

        try:
            with csv_file.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if not rows:
                    return None
                last_row = rows[-1]
                updated_at = last_row.get("updated_at", "")
                source = last_row.get("source", "tdx")
                data_json = last_row.get("data", "{}")
        except Exception:
            return None

        # Check expiry
        if self._is_expired(updated_at, key):
            return None

        try:
            data = json.loads(data_json) if data_json else {}
        except (json.JSONDecodeError, TypeError):
            return None

        data["_meta"] = {
            "symbol": symbol,
            "capability": capability,
            "interval": interval,
            "source": source,
            "updated_at": updated_at,
            "stale": 0,
        }
        return data

    def _set_csv(
        self,
        symbol: str,
        capability: str,
        interval: str,
        data: Dict[str, Any],
        source: str,
        now: str,
    ) -> None:
        csv_file = _csv_path(self._base_dir, symbol, capability, interval)
        clean_data = {k: v for k, v in data.items() if k != "_meta"}
        data_json = json.dumps(clean_data, ensure_ascii=False, default=str)

        fieldnames = ["symbol", "capability", "interval", "source", "data", "updated_at"]
        row = {
            "symbol": symbol,
            "capability": capability,
            "interval": interval,
            "source": source,
            "data": data_json,
            "updated_at": now,
        }

        try:
            # Rewrite the CSV with a single row (we could append, but for
            # simplicity and to avoid duplication, rewrite).
            with csv_file.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(row)
        except Exception as exc:
            logger.warning("tdx_cache: failed to write CSV %s: %s", csv_file, exc)

    def _clear_csv(self, symbol: Optional[str] = None) -> None:
        csv_dir = self._base_dir / _CSV_SUBDIR
        if not csv_dir.exists():
            return

        if symbol:
            safe_symbol = symbol.replace(".", "_").replace("/", "_")
            for f in csv_dir.glob("{0}_*.csv".format(safe_symbol)):
                try:
                    f.unlink()
                except Exception as e:

                    logger.debug("Operation failed: {0}", e)

        else:
            for f in csv_dir.glob("*.csv"):
                try:
                    f.unlink()
                except Exception as e:

                    logger.debug("Operation failed: {0}", e)


    # ── Cleanup ───────────────────────────────────────────────────────

    def __enter__(self) -> "TdxCache":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __del__(self) -> None:
        """Safety net: ensure connection is closed on garbage collection."""
        try:
            self.close()
        except Exception:
            pass
