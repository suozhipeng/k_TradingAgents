"""Tests for the A-share trading calendar."""
from __future__ import annotations

import datetime
import unittest

from tradingagents.astock.data_sources.calendar import (
    is_trading_day,
    next_trading_day,
    prev_trading_day,
    trading_days_between,
)


class TestTradingCalendar(unittest.TestCase):
    """Trading calendar tests — uses static holiday data, no network calls."""

    def test_weekend_is_not_trading_day(self):
        saturday = datetime.date(2026, 6, 27)  # Saturday
        sunday = datetime.date(2026, 6, 28)  # Sunday
        self.assertFalse(is_trading_day(saturday))
        self.assertFalse(is_trading_day(sunday))

    def test_known_holiday_is_not_trading_day(self):
        # Spring Festival 2026
        spring_festival = datetime.date(2026, 2, 16)
        self.assertFalse(is_trading_day(spring_festival))

    def test_weekday_is_trading_day(self):
        monday = datetime.date(2026, 6, 29)  # Monday, no holiday
        self.assertTrue(is_trading_day(monday))

    def test_next_trading_day(self):
        friday = datetime.date(2026, 6, 26)  # Friday
        monday = datetime.date(2026, 6, 29)  # Next Monday
        self.assertEqual(next_trading_day(friday), monday)

    def test_prev_trading_day(self):
        monday = datetime.date(2026, 6, 29)  # Monday
        friday = datetime.date(2026, 6, 26)  # Previous Friday
        self.assertEqual(prev_trading_day(monday), friday)

    def test_trading_days_between_counts(self):
        start = datetime.date(2026, 6, 1)
        end = datetime.date(2026, 6, 30)
        days = trading_days_between(start, end)
        self.assertGreater(len(days), 0)
        # Should exclude weekends
        for d in days:
            self.assertLess(d.weekday(), 5)  # not weekend
            self.assertNotIn(d.isoformat(), {
                "2026-02-16", "2026-02-17", "2026-10-01",  # known holidays
            })

    def test_trading_days_are_sorted(self):
        start = datetime.date(2026, 6, 1)
        end = datetime.date(2026, 6, 10)
        days = trading_days_between(start, end)
        for i in range(1, len(days)):
            self.assertGreater(days[i], days[i - 1])

    def test_no_days_on_weekend_range(self):
        sat = datetime.date(2026, 6, 27)  # Saturday
        sun = datetime.date(2026, 6, 28)  # Sunday
        self.assertEqual(trading_days_between(sat, sun), [])

    def test_is_trading_day_defaults_to_today(self):
        # Should not crash when called without a date
        result = is_trading_day()
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
