"""TDX (通达信) local vipdoc file reader.

Reads daily kline data directly from the TDX client's local ``vipdoc``
directory, avoiding network calls for historical daily data.  Works on both
Windows (``C:/new_tdx/vipdoc/``) and macOS/Linux (configurable via env var).

File layout (per exchange)
--------------------------
- ``vipdoc/sh/lday/sh{code}.day`` — Shanghai daily kline
- ``vipdoc/sz/lday/sz{code}.day`` — Shenzhen daily kline
- ``vipdoc/sh/lday/sh{code}.min`` — Shanghai minute kline (5/30/60min)
- ``vipdoc/sz/lday/sz{code}.min`` — Shenzhen minute kline (5/30/60min)

Binary record format (32 bytes per record)
------------------------------------------
| Offset | Size | Type   | Description            |
|--------|------|--------|------------------------|
| 0-3    | 4    | int16×2| year + month           |
| 4-7    | 4    | int16×2| day + (unused)         |
| 8-11   | 4    | int32  | open price   (×100)    |
| 12-15  | 4    | int32  | high price   (×100)    |
| 16-19  | 4    | int32  | low price    (×100)    |
| 20-23  | 4    | int32  | close price  (×100)    |
| 24-27  | 4    | float32| volume                 |
| 28-31  | 4    | float32| amount                 |

Configuration
-------------
- ``ASTOCK_TDX_VIPDOC_PATH`` — path to TDX vipdoc directory
  (default: ``/Applications/new_tdx/vipdoc/`` on macOS)
"""

from __future__ import annotations

import logging
import os
import struct
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .errors import AStockNoDataError, AStockSourceUnavailableError
from .symbols import astock_code, split_astock_symbol

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────

RECORD_SIZE = 32  # bytes per daily-kline record

# Minute-file subtypes (the .min file contains a header byte that identifies
# the minute interval)
MINUTE_INTERVAL_5 = 5   # 5-minute
MINUTE_INTERVAL_30 = 30  # 30-minute
MINUTE_INTERVAL_60 = 60  # 60-minute

# ── Platform default paths ────────────────────────────────────────────────

if os.name == "nt":
    _DEFAULT_VIPDOC = Path("C:/new_tdx/vipdoc/")
elif sys.platform == "darwin":
    _DEFAULT_VIPDOC = Path.home() / "Applications" / "new_tdx" / "vipdoc"
else:
    _DEFAULT_VIPDOC = Path.home() / ".tdx" / "vipdoc"


def _resolve_vipdoc_path() -> Path:
    """Return the resolved TDX vipdoc directory.

    Checks ``ASTOCK_TDX_VIPDOC_PATH`` env var first, then falls back to the
    platform default.  Returns the path even if it doesn't exist yet (so the
    caller can emit a descriptive ``AStockSourceUnavailableError``).
    """
    env_path = os.environ.get("ASTOCK_TDX_VIPDOC_PATH")
    if env_path:
        return Path(env_path)
    return _DEFAULT_VIPDOC


# ── Binary parsing ────────────────────────────────────────────────────────


def _parse_day_record(data: bytes, offset: int) -> Dict[str, Any]:
    """Parse one 32-byte daily kline record from ``data`` at ``offset``."""
    chunk = data[offset : offset + RECORD_SIZE]
    if len(chunk) < RECORD_SIZE:
        raise ValueError(
            "truncated record at offset {0}: got {1} bytes, expected {2}".format(
                offset, len(chunk), RECORD_SIZE
            )
        )

    year_raw, month_raw = struct.unpack_from("<hh", chunk, 0)
    day_raw, _unused = struct.unpack_from("<hh", chunk, 4)
    open_raw, high_raw, low_raw, close_raw = struct.unpack_from("<iiii", chunk, 8)
    volume = struct.unpack_from("<f", chunk, 24)[0]
    amount = struct.unpack_from("<f", chunk, 28)[0]

    year = year_raw
    month = month_raw
    day = day_raw

    # Some TDX files store year as e.g. 2026, some as 2000+offset.
    # We handle both by normalising to 4-digit.
    if 0 <= year <= 99:
        year += 2000

    open_px = open_raw / 100.0
    high_px = high_raw / 100.0
    low_px = low_raw / 100.0
    close_px = close_raw / 100.0

    return {
        "date": "{0:04d}-{1:02d}-{2:02d}".format(year, month, day),
        "open": open_px,
        "high": high_px,
        "low": low_px,
        "close": close_px,
        "volume": volume,
        "amount": amount,
    }


def _parse_minute_record(data: bytes, offset: int, interval: int) -> Dict[str, Any]:
    """Parse one 32-byte minute kline record.

    The minute-file format is the same 32-byte structure as the daily file,
    but the year/month/day fields encode the date **and** the intraday time
    depends on the interval.
    """
    chunk = data[offset : offset + RECORD_SIZE]
    if len(chunk) < RECORD_SIZE:
        raise ValueError(
            "truncated minute record at offset {0}: got {1} bytes, expected {2}".format(
                offset, len(chunk), RECORD_SIZE
            )
        )

    year_raw, month_raw = struct.unpack_from("<hh", chunk, 0)
    day_raw, _unused = struct.unpack_from("<hh", chunk, 4)
    open_raw, high_raw, low_raw, close_raw = struct.unpack_from("<iiii", chunk, 8)
    volume = struct.unpack_from("<f", chunk, 24)[0]
    amount = struct.unpack_from("<f", chunk, 28)[0]

    year = year_raw
    month = month_raw
    if 0 <= year <= 99:
        year += 2000

    # For minute kline, day_raw encodes both the day (first part) and the
    # time-of-day index.  The exact encoding varies, but a common scheme is:
    # day_raw = day + index * 100, where index is the bar number within the
    # trading day for the given interval.
    bar_index = day_raw // 100
    day = day_raw % 100

    # Calculate the time from bar_index
    # 5-min: bar 0 = 09:30, bar 1 = 09:35, ...
    # 30-min: bar 0 = 09:30, bar 1 = 10:00, ...
    # 60-min: bar 0 = 09:30, bar 1 = 10:30, ...
    minutes_per_bar = interval
    base_minutes = 9 * 60 + 30  # 09:30 = market open
    elapsed_minutes = bar_index * minutes_per_bar
    total_minutes = base_minutes + elapsed_minutes
    hour = total_minutes // 60
    minute = total_minutes % 60

    open_px = open_raw / 100.0
    high_px = high_raw / 100.0
    low_px = low_raw / 100.0
    close_px = close_raw / 100.0

    return {
        "date": "{0:04d}-{1:02d}-{2:02d} {3:02d}:{4:02d}:00".format(
            year, month, day, hour, minute
        ),
        "open": open_px,
        "high": high_px,
        "low": low_px,
        "close": close_px,
        "volume": volume,
        "amount": amount,
    }


def _read_day_file(path: Path) -> List[Dict[str, Any]]:
    """Read an entire ``.day`` file and return parsed records."""
    data = path.read_bytes()
    records: List[Dict[str, Any]] = []
    for offset in range(0, len(data), RECORD_SIZE):
        if offset + RECORD_SIZE > len(data):
            break
        records.append(_parse_day_record(data, offset))
    return records


def _read_minute_file(path: Path, interval: int) -> List[Dict[str, Any]]:
    """Read an entire ``.min`` (or ``.5``/``.30``/``.60``) file.

    The file starts with a 1-byte header identifying the interval type.
    """
    data = path.read_bytes()
    # Some minute files have a 1-byte header; skip it if present.
    start_offset = 0
    if len(data) > 0:
        header = data[0]
        if header in (5, 30, 60):
            start_offset = 1

    records: List[Dict[str, Any]] = []
    for offset in range(start_offset, len(data), RECORD_SIZE):
        if offset + RECORD_SIZE > len(data):
            break
        records.append(_parse_minute_record(data, offset, interval))
    return records


# ── Exchange → prefix mapping ────────────────────────────────────────────

_EXCHANGE_DIR_MAP = {
    "SH": "sh",
    "SZ": "sz",
    "BJ": "sz",  # Beijing stocks share Shenzhen directory in TDX
}

_EXCHANGE_PREFIX_MAP = {
    "SH": "sh",
    "SZ": "sz",
    "BJ": "sz",  # Beijing uses sz prefix
}


def _exchange_and_code(symbol: str) -> Tuple[str, str]:
    """Return ``(exchange_dir, code_prefix)`` for a canonical symbol."""
    code, exchange = split_astock_symbol(symbol)
    if not code or not exchange:
        raise AStockNoDataError(
            symbol,
            detail="cannot parse exchange from {0!r}".format(symbol),
            source="tdx_vipdoc",
        )
    exchange_lower = _EXCHANGE_DIR_MAP.get(exchange.upper(), exchange.lower())
    prefix = _EXCHANGE_PREFIX_MAP.get(exchange.upper(), exchange.lower())
    return exchange_lower, prefix


# ── Reader class ─────────────────────────────────────────────────────────


class TdxVipdocReader:
    """Reads TDX local vipdoc files for historical daily/minute kline data.

    Parameters
    ----------
    tdx_path : str or Path, optional
        Path to the TDX vipdoc directory.  Defaults to the platform-specific
        path (or ``ASTOCK_TDX_VIPDOC_PATH`` env var).
    """

    def __init__(self, tdx_path: Optional[Union[str, Path]] = None) -> None:
        self._base = Path(tdx_path) if tdx_path else _resolve_vipdoc_path()

    # ── Public API ────────────────────────────────────────────────────

    def read_daily_kline(self, symbol: str) -> List[Dict[str, Any]]:
        """Parse daily kline from the local ``.day`` file for *symbol*.

        Returns
        -------
        list[dict]
            Each dict has keys: ``date``, ``open``, ``high``, ``low``,
            ``close``, ``volume``, ``amount``.

        Raises
        ------
        AStockNoDataError
            If the file is not found or is empty.
        AStockSourceUnavailableError
            If the vipdoc directory does not exist.
        """
        self._ensure_base_exists()
        code = astock_code(symbol)
        exchange_dir, prefix = _exchange_and_code(symbol)
        file_path = self._base / exchange_dir / "lday" / "{0}{1}.day".format(prefix, code)

        if not file_path.exists():
            raise AStockNoDataError(
                symbol,
                detail="vipdoc file not found: {0}".format(file_path),
                source="tdx_vipdoc",
                capability="kline",
            )

        try:
            records = _read_day_file(file_path)
        except Exception as exc:
            raise AStockNoDataError(
                symbol,
                detail="failed to parse vipdoc file {0}: {1}".format(file_path, exc),
                source="tdx_vipdoc",
                capability="kline",
            )

        if not records:
            raise AStockNoDataError(
                symbol,
                detail="empty vipdoc file: {0}".format(file_path),
                source="tdx_vipdoc",
                capability="kline",
            )

        return records

    def read_minute_kline(
        self, symbol: str, date_str: str, interval: int = 5
    ) -> List[Dict[str, Any]]:
        """Parse minute kline from the local TDX minute file.

        Parameters
        ----------
        symbol : str
            Canonical A-share symbol (e.g. ``600519.SH``).
        date_str : str
            Date string in ``YYYYMMDD`` or ``YYYY-MM-DD`` format.
        interval : int
            Minute interval: 5, 30, or 60.

        Returns
        -------
        list[dict]
            Each dict has keys: ``date`` (datetime string), ``open``,
            ``high``, ``low``, ``close``, ``volume``, ``amount``.
        """
        self._ensure_base_exists()
        code = astock_code(symbol)
        exchange_dir, prefix = _exchange_and_code(symbol)

        # Normalise date string
        clean_date = date_str.replace("-", "")

        # TDX stores minute files per date under:
        # vipdoc/{exchange}/minline/{prefix}{code}{date}.{interval}
        # or
        # vipdoc/{exchange}/lday/{prefix}{code}.min (with header)
        # Try the per-date file first, then the combined .min
        per_date_path = (
            self._base
            / exchange_dir
            / "minline"
            / "{0}{1}{2}.{3}".format(prefix, code, clean_date, interval)
        )
        combined_path = (
            self._base / exchange_dir / "lday" / "{0}{1}.min".format(prefix, code)
        )

        file_path = None
        if per_date_path.exists():
            file_path = per_date_path
        elif combined_path.exists():
            file_path = combined_path
        else:
            raise AStockNoDataError(
                symbol,
                detail="vipdoc minute file not found for {0} (tried: {1}, {2})".format(
                    symbol, per_date_path, combined_path
                ),
                source="tdx_vipdoc",
                capability="kline",
            )

        try:
            records = _read_minute_file(file_path, interval)
        except Exception as exc:
            raise AStockNoDataError(
                symbol,
                detail="failed to parse vipdoc minute file {0}: {1}".format(
                    file_path, exc
                ),
                source="tdx_vipdoc",
                capability="kline",
            )

        if not records:
            raise AStockNoDataError(
                symbol,
                detail="empty vipdoc minute file: {0}".format(file_path),
                source="tdx_vipdoc",
                capability="kline",
            )

        return records

    def get_kline(
        self, symbol: str, interval: str = "1d", start_date: str = "", end_date: str = ""
    ) -> Dict[str, Any]:
        """High-level kline fetch matching the TdxProvider interface.

        For daily data (``1d`` / ``day`` / ``daily``) this reads the local
        vipdoc file.  For intraday intervals it delegates to
        ``read_minute_kline`` and filters by the date range if provided.
        """
        interval_lower = interval.lower()

        if interval_lower in ("1d", "day", "daily"):
            records = self.read_daily_kline(symbol)
            # Filter by date range (vipdoc has all records; caller may want subset)
            filtered = _filter_by_date_range(records, start_date, end_date)
            return _format_kline_response(symbol, interval, filtered)

        # Intraday: determine interval in minutes
        minute_map = {
            "5m": 5,
            "30m": 30,
            "60m": 60,
            "5min": 5,
            "30min": 30,
            "60min": 60,
        }
        minutes = minute_map.get(interval_lower)
        if minutes is None:
            raise AStockNoDataError(
                symbol,
                detail="unsupported intraday interval: {0!r}".format(interval),
                source="tdx_vipdoc",
                capability="kline",
            )

        # For minute kline, we need a date. Use end_date or today.
        target_date = end_date or datetime.now().strftime("%Y-%m-%d")
        records = self.read_minute_kline(symbol, target_date, interval=minutes)
        filtered = _filter_by_date_range(records, start_date, end_date)
        return _format_kline_response(symbol, interval, filtered)

    # ── Internals ─────────────────────────────────────────────────────

    def _ensure_base_exists(self) -> None:
        if not self._base.exists():
            raise AStockSourceUnavailableError(
                "tdx_vipdoc",
                "vipdoc directory not found: {0}.  Set ASTOCK_TDX_VIPDOC_PATH to "
                "point to your TDX vipdoc folder.".format(self._base),
            )

    @property
    def base_path(self) -> Path:
        return self._base


# ── Helpers ──────────────────────────────────────────────────────────────


def _filter_by_date_range(
    records: List[Dict[str, Any]],
    start_date: str = "",
    end_date: str = "",
) -> List[Dict[str, Any]]:
    """Filter records by optional start/end date string (``YYYY-MM-DD``)."""
    if not start_date and not end_date:
        return records

    start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else date.min
    end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else date.max

    result: List[Dict[str, Any]] = []
    for rec in records:
        rec_date_str = rec.get("date", "")
        if " " in rec_date_str:
            rec_date = datetime.strptime(rec_date_str.split(" ")[0], "%Y-%m-%d").date()
        else:
            rec_date = datetime.strptime(rec_date_str, "%Y-%m-%d").date()
        if start <= rec_date <= end:
            result.append(rec)
    return result


def _format_kline_response(
    symbol: str, interval: str, records: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Wrap records into the standard kline response format."""
    return {
        "bars": records,
        "count": len(records),
        "symbol": symbol,
        "interval": interval,
    }


# ── Public convenience constructor ────────────────────────────────────────


def create_vipdoc_reader(tdx_path: Optional[Union[str, Path]] = None) -> TdxVipdocReader:
    """Create a ``TdxVipdocReader``, picking up env config if available."""
    return TdxVipdocReader(tdx_path=tdx_path)
