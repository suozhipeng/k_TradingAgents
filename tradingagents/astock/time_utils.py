"""Canonical clock helpers for the China A-share market.

Replaces deprecated ``datetime.utcnow()`` throughout the codebase with
timezone-aware ``datetime.now(timezone.utc)``.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

MARKET_TIMEZONE = ZoneInfo("Asia/Shanghai")


def market_now() -> datetime:
    return datetime.now(MARKET_TIMEZONE)


def market_today() -> date:
    return market_now().date()


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string (timezone-aware).

    Drop-in replacement for ``datetime.utcnow().isoformat()``.
    """
    return datetime.now(UTC).isoformat()


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)
