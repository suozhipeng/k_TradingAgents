"""Shared helpers for AStock API route files — NaN sanitisation and JSON conversion.

Every ``df_to_json`` call now passes through the :mod:`DataCleaner
<tradingagents.astock.data_sources.cleaner>` for automatic quality checks.

Also provides config-reading helpers used by ``app_factory.py`` and ``app_hooks.py``.
"""

from __future__ import annotations

import math
import os
from datetime import datetime
from typing import Any

from tradingagents.astock.data_sources.cleaner import (
    clean_records,
    summary_text,
)

# Global cleaning stats accumulated across all queries (reset on server restart)
_global_clean_stats: dict[str, int] = {}


# ---------------------------------------------------------------------------
# Data helpers (used by route files)
# ---------------------------------------------------------------------------

def sanitise_records(records: list[dict[str, Any]]) -> None:
    """Replace NaN/Inf with None and format datetimes in-place for valid JSON."""
    for record in records:
        for k, v in record.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                record[k] = None
            elif isinstance(v, datetime):
                if v.hour == 0 and v.minute == 0 and v.second == 0:
                    record[k] = v.strftime("%Y-%m-%d")
                else:
                    record[k] = v.strftime("%Y-%m-%d %H:%M")
            elif hasattr(v, "isoformat"):
                record[k] = v.isoformat()


def df_to_json(
    df: Any,
    symbol: str = "",
) -> list[dict[str, Any]]:
    """Convert a pandas DataFrame to a list of plain dicts.

    Sanitises NaN/Inf for valid JSON **and** runs :func:`clean_records`
    for data quality checks (zero prices, outlier changes, date ordering, …).
    """
    if df is None or (hasattr(df, "empty") and df.empty):
        return []
    if hasattr(df, "to_dict"):
        records = df.to_dict(orient="records")
        sanitise_records(records)

        # ── Data cleaning pass ──
        cleaned, report = clean_records(records, symbol=symbol)

        # Accumulate global stats
        if report.has_issues():
            _global_clean_stats["total"] = _global_clean_stats.get("total", 0) + 1
            for k, v in report.to_dict().items():
                _global_clean_stats[k] = _global_clean_stats.get(k, 0) + v

        return cleaned
    return list(df)


def get_clean_stats() -> dict[str, int]:
    """Return accumulated cleaning statistics since server start."""
    return dict(_global_clean_stats)


# ---------------------------------------------------------------------------
# Config helpers (used by app_factory and app_hooks)
# ---------------------------------------------------------------------------

def _as_bool(val: Any, default: bool = False) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    text = str(val).strip()
    if not text:
        return default
    return text.lower() in ("true", "1", "yes", "on")


def _bool_env(key: str, default: bool = False) -> bool:
    """Read a boolean env var."""
    val = os.environ.get(key, "")
    return _as_bool(val, default)


def _bool_config(app: Any, key: str, default: bool = False) -> bool:
    """Read a boolean from app config first, then env."""
    if key in app.config:
        return _as_bool(app.config.get(key), default)
    return _bool_env(key, default)


def _int_config(app: Any, key: str, default: int) -> int:
    """Read an integer from app config first, then env."""
    val = app.config.get(key, os.environ.get(key, ""))
    if not val:
        return default
    try:
        return int(str(val).strip())
    except (TypeError, ValueError):
        return default
