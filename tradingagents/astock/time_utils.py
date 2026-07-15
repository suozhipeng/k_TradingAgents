"""Canonical clock helpers for the China A-share market."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

MARKET_TIMEZONE = ZoneInfo("Asia/Shanghai")


def market_now() -> datetime:
    return datetime.now(MARKET_TIMEZONE)


def market_today() -> date:
    return market_now().date()
