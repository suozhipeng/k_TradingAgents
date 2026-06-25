"""A-share trading calendar — trading day query with fallback.

Provides ``is_trading_day()``, ``next_trading_day()``, and
``prev_trading_day()`` using akshare's official calendar data.

Falls back to a simple weekend check (mon–fri) when akshare is unavailable.
Statically known Chinese holidays are also excluded in fallback mode so that
backtests do not accidentally trade on exchange-closed days.
"""

from __future__ import annotations

import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Statically known Chinese public holidays (exchange-closed) for fallback.
# Source: SSE / SZSE annual trading calendars.
# These cover 2023–2026.  Update annually.
# ---------------------------------------------------------------------------
_CHINESE_HOLIDAYS: set[str] = {
    # 2023
    "2023-01-02",  # New Year
    "2023-01-23", "2023-01-24", "2023-01-25", "2023-01-26", "2023-01-27",  # Spring Festival
    "2023-04-05",  # Qingming
    "2023-05-01",  # Labour Day
    "2023-06-22", "2023-06-23",  # Dragon Boat
    "2023-09-29",  # Mid-Autumn
    "2023-10-02", "2023-10-03", "2023-10-04", "2023-10-05", "2023-10-06",  # National Day
    # 2024
    "2024-01-01",  # New Year
    "2024-02-12", "2024-02-13", "2024-02-14", "2024-02-15", "2024-02-16",  # Spring Festival
    "2024-04-04", "2024-04-05",  # Qingming
    "2024-05-01", "2024-05-02", "2024-05-03",  # Labour Day
    "2024-06-10",  # Dragon Boat
    "2024-09-16", "2024-09-17",  # Mid-Autumn
    "2024-10-01", "2024-10-02", "2024-10-03", "2024-10-04", "2024-10-07",  # National Day
    # 2025
    "2025-01-01",  # New Year
    "2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31", "2025-02-03", "2025-02-04",  # Spring Festival
    "2025-04-04",  # Qingming
    "2025-05-01", "2025-05-02",  # Labour Day
    "2025-05-31", "2025-06-02",  # Dragon Boat
    "2025-10-01", "2025-10-02", "2025-10-03", "2025-10-06", "2025-10-07", "2025-10-08",  # National Day
    # 2026
    "2026-01-01",  # New Year
    "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",  # Spring Festival
    "2026-04-06",  # Qingming
    "2026-05-01",  # Labour Day
    "2026-06-19",  # Dragon Boat
    "2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09",  # National Day + Mid-Autumn
}


def _is_holiday(date: datetime.date) -> bool:
    """Check if *date* is a known Chinese public holiday."""
    return date.isoformat() in _CHINESE_HOLIDAYS


def _is_weekend(date: datetime.date) -> bool:
    """Check if *date* falls on Saturday or Sunday."""
    return date.weekday() >= 5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_trading_day(date: Optional[datetime.date] = None) -> bool:
    """Return True if *date* is an A-share trading day.

    Uses akshare for accurate data when available; otherwise falls back
    to a weekend + known-holiday check.

    Parameters
    ----------
    date : datetime.date or None
        Date to check.  Defaults to today (local time).
    """
    if date is None:
        date = datetime.date.today()

    target = date.isoformat()

    # Try akshare for authoritative answer
    # (optional dependency — may not be installed)
    try:
        import akshare as ak

        cal = ak.tool_trade_date_hist_sina()
        if cal is not None and not cal.empty:
            trade_dates = cal["trade_date"].astype(str)
            # Exact match on the date string (avoids prefix false-positives)
            match = cal[trade_dates == target]
            if not match.empty:
                is_open = bool(match.iloc[0].get("is_open", 0))
                if is_open:
                    return True
                # Akshare says closed — verify against static fallback for
                # dates akshare may not have reliable data for (e.g. future).
                # If the static calendar says it's a regular weekday, trust
                # static over potentially stale akshare data.
                if not _is_weekend(date) and not _is_holiday(date):
                    return True
                return False
            # Date not found in akshare data (year may not be covered)
    except Exception:
        pass

    # Fallback: weekend + known holidays
    if _is_weekend(date):
        return False
    if _is_holiday(date):
        return False
    return True


def next_trading_day(date: Optional[datetime.date] = None) -> datetime.date:
    """Return the next trading day strictly after *date*."""
    if date is None:
        date = datetime.date.today()
    candidate = date + datetime.timedelta(days=1)
    while not is_trading_day(candidate):
        candidate += datetime.timedelta(days=1)
    return candidate


def prev_trading_day(date: Optional[datetime.date] = None) -> datetime.date:
    """Return the previous trading day strictly before *date*."""
    if date is None:
        date = datetime.date.today()
    candidate = date - datetime.timedelta(days=1)
    while not is_trading_day(candidate):
        candidate -= datetime.timedelta(days=1)
    return candidate


def trading_days_between(start: datetime.date, end: datetime.date) -> list[datetime.date]:
    """Return a sorted list of all trading days in [start, end]."""
    days: list[datetime.date] = []
    current = start
    while current <= end:
        if is_trading_day(current):
            days.append(current)
        current += datetime.timedelta(days=1)
    return days
