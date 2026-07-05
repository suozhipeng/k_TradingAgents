"""Test T+1 settlement constraint for PaperTrader."""

from datetime import datetime, timedelta
import pytest
from tradingagents.astock.execution.paper_trader import PaperTrader
from tradingagents.astock.schemas.trading_execution import OrderStatus


class TestPaperTraderSettlement:
    """T+1: A-share stocks cannot be sold on the same day they are bought."""

    def test_buy_records_purchase_date(self) -> None:
        """Buying a stock records the purchase date when t_plus_1 is enabled."""
        pt = PaperTrader(t_plus_1=True)
        pt.execute_cycle({"600519.SH": 1}, {"600519.SH": 150.0})
        assert "600519.SH" in pt._purchase_dates
        assert pt._purchase_dates["600519.SH"] == datetime.utcnow().strftime("%Y-%m-%d")

    def test_execute_cycle_sell_same_day_blocked(self) -> None:
        """execute_cycle sell on same day as buy is blocked (T+1)."""
        pt = PaperTrader(t_plus_1=True)
        pt.execute_cycle({"600519.SH": 1}, {"600519.SH": 150.0})
        assert "600519.SH" in pt._state.positions
        pt.execute_cycle({"600519.SH": -1}, {"600519.SH": 155.0})
        # Position should still exist (sell was blocked)
        assert pt._state.positions.get("600519.SH", 0) > 0

    def test_execute_cycle_sell_next_day_allowed(self) -> None:
        """execute_cycle sell on next day is allowed."""
        pt = PaperTrader(t_plus_1=True)
        pt.execute_cycle({"600519.SH": 1}, {"600519.SH": 150.0})
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        pt._purchase_dates["600519.SH"] = yesterday
        pt.execute_cycle({"600519.SH": -1}, {"600519.SH": 155.0})
        assert pt._state.positions.get("600519.SH", 0) == 0

    def test_place_order_sell_same_day_allowed(self) -> None:
        """Manual place_order is exempt from T+1 (user override)."""
        pt = PaperTrader(t_plus_1=True)
        result = pt.place_order("600519.SH", "buy", 150.0, 100)
        assert result.status == OrderStatus.FILLED
        result = pt.place_order("600519.SH", "sell", 155.0, 100)
        assert result.status == OrderStatus.FILLED

    def test_place_buy_always_allowed(self) -> None:
        """Buy orders are never blocked by T+1."""
        pt = PaperTrader(t_plus_1=True)
        result = pt.place_order("000001.SZ", "buy", 10.0, 100)
        assert result.status == OrderStatus.FILLED

    def test_t_plus_1_opt_out(self) -> None:
        """t_plus_1=False (default) allows same-day execute_cycle sell."""
        pt = PaperTrader()  # default: t_plus_1=False
        pt.execute_cycle({"600519.SH": 1}, {"600519.SH": 150.0})
        pt.execute_cycle({"600519.SH": -1}, {"600519.SH": 155.0})
        # Position should be gone (sell succeeded)
        assert pt._state.positions.get("600519.SH", 0) == 0
