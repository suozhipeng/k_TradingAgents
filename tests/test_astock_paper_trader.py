"""Paper trading simulator tests.

Uses direct importlib imports to match the repo convention.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Direct module imports
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parent.parent
_EXEC = _REPO / "tradingagents" / "astock" / "execution"

_PKG_PARENT = "tradingagents.astock.execution"


def _load_submodule(rel_name: str):
    """Load a module without polluting sys.modules with fake packages."""
    import importlib

    fname = rel_name + ".py"
    full_name = f"{_PKG_PARENT}.{rel_name}"
    path = str(_EXEC / fname)
    spec = importlib.util.spec_from_file_location(full_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {full_name} from {path}")
    for parent in ("tradingagents", "tradingagents.astock", _PKG_PARENT):
        mod = sys.modules.get(parent)
        if mod is not None and hasattr(mod, "__path__") and not getattr(mod, "__path__", []):
            del sys.modules[parent]
        if parent not in sys.modules:
            try:
                importlib.import_module(parent)
            except ImportError:
                pass
    exec_pkg = sys.modules.get(_PKG_PARENT)
    if exec_pkg:
        exec_pkg.__path__ = [str(_EXEC)]
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = _PKG_PARENT
    mod.__name__ = full_name
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


# fee_model must be loaded before paper_trader (paper_trader imports from it)
_fm = _load_submodule("fee_model")
_pt = _load_submodule("paper_trader")

PaperTradeState = _pt.PaperTradeState
PaperTrader = _pt.PaperTrader
AStockFeeConfig = _fm.AStockFeeConfig


# ===================================================================
# PaperTrader tests
# ===================================================================


class TestPaperTraderInit(unittest.TestCase):
    def test_initial_state_defaults(self) -> None:
        trader = PaperTrader()
        state = trader.get_state()
        self.assertEqual(state.cash, 100000.0)
        self.assertEqual(state.total_value, 100000.0)
        self.assertEqual(state.positions, {})
        self.assertEqual(state.trades, [])
        self.assertEqual(state.pnl, 0.0)
        self.assertNotEqual(state.last_updated, "")

    def test_initial_state_custom_cash(self) -> None:
        trader = PaperTrader(initial_cash=50000.0)
        state = trader.get_state()
        self.assertEqual(state.cash, 50000.0)
        self.assertEqual(state.total_value, 50000.0)

    def test_initial_state_execution_signal(self) -> None:
        trader = PaperTrader()
        state = trader.get_state()
        self.assertEqual(state.execution_signal, "ResearchOnly")


class TestPaperTraderExecuteCycle(unittest.TestCase):
    def test_buy_signal_adds_position(self) -> None:
        trader = PaperTrader(initial_cash=10000.0)
        signals = {"000001.SH": 1.0}
        prices = {"000001.SH": 100.0}
        state = trader.execute_cycle(signals, prices)
        self.assertIn("000001.SH", state.positions)
        self.assertGreater(state.positions["000001.SH"], 0)
        self.assertLess(state.cash, 10000.0)  # cash spent

    def test_sell_signal_reduces_position(self) -> None:
        trader = PaperTrader(initial_cash=10000.0)
        # Buy first
        trader.execute_cycle({"000001.SH": 1.0}, {"000001.SH": 100.0})
        # Then sell
        state = trader.execute_cycle({"000001.SH": -1.0}, {"000001.SH": 110.0})
        self.assertNotIn("000001.SH", state.positions)
        self.assertGreater(state.cash, 0)

    def test_hold_signal_no_change(self) -> None:
        trader = PaperTrader(initial_cash=10000.0)
        # Buy first to get a position
        trader.execute_cycle({"000001.SH": 1.0}, {"000001.SH": 100.0})
        # Hold
        state = trader.execute_cycle({"000001.SH": 0.0}, {"000001.SH": 100.0})
        self.assertIn("000001.SH", state.positions)

    def test_multiple_trades_position_and_pnl(self) -> None:
        """Buy at 100, sell at 120, verify cash and P&L."""
        trader = PaperTrader(initial_cash=20000.0)
        cfg = AStockFeeConfig(commission_rate=0.0, stamp_tax_rate=0.0, slippage_rate=0.0, min_commission=0.0)
        trader._fee_config = cfg

        state1 = trader.execute_cycle({"A": 1.0}, {"A": 100.0})
        shares = state1.positions["A"]
        self.assertAlmostEqual(state1.cash, 0.0, places=0)

        state2 = trader.execute_cycle({"A": -1.0}, {"A": 120.0})
        expected_cash = shares * 120.0
        self.assertAlmostEqual(state2.cash, expected_cash, places=1)
        self.assertGreater(state2.pnl, 0)

    def test_fee_deduction_affects_cash(self) -> None:
        """Buy with non-zero fees reduces cash more than trade value."""
        trader = PaperTrader(initial_cash=10000.0)
        signals = {"A": 1.0}
        prices = {"A": 100.0}
        state = trader.execute_cycle(signals, prices)
        # Cash should drop to near zero (all cash spent on shares + fees)
        self.assertGreaterEqual(state.cash, -0.01)
        # Total cost (spent cash) should be > shares * price due to fees
        shares = state.positions["A"]
        spent = 10000.0 - state.cash
        self.assertGreater(spent, shares * 100.0)

    def test_actionable_false_in_trade_record(self) -> None:
        trader = PaperTrader(initial_cash=10000.0)
        trader.execute_cycle({"A": 1.0}, {"A": 100.0})
        state = trader.get_state()
        for trade in state.trades:
            self.assertFalse(trade.get("actionable", True))

    def test_risk_gate_blocks_signal(self) -> None:
        """Position cap blocks buying when already at limit."""
        trader = PaperTrader(initial_cash=10000.0)
        # First buy
        trader.execute_cycle({"A": 1.0}, {"A": 100.0})
        # Second buy with tight cap should be blocked
        state = trader.execute_cycle(
            {"A": 1.0},
            {"A": 100.0},
            position_cap_pct=0.05,  # 5% cap, but already have >5% exposure
        )
        # Position should not increase (blocked)
        self.assertEqual(len(state.trades), 1)  # Only first trade

    def test_get_state_returns_copy(self) -> None:
        trader = PaperTrader(initial_cash=10000.0)
        state1 = trader.get_state()
        state1.cash = 999.0  # modify copy
        state2 = trader.get_state()
        self.assertEqual(state2.cash, 10000.0)  # original unchanged

    def test_sell_no_position_skipped(self) -> None:
        """Sell signal for non-held symbol is a no-op."""
        trader = PaperTrader(initial_cash=10000.0)
        state = trader.execute_cycle({"NONEXIST": -1.0}, {"NONEXIST": 50.0})
        self.assertEqual(state.cash, 10000.0)
        self.assertEqual(len(state.trades), 0)

    def test_buy_with_insufficient_cash_skipped(self) -> None:
        """Buy signal with zero cash is skipped."""
        trader = PaperTrader(initial_cash=0.0)
        state = trader.execute_cycle({"A": 1.0}, {"A": 100.0})
        self.assertEqual(state.cash, 0.0)
        self.assertEqual(state.positions, {})


class TestPaperTraderPlaceOrder(unittest.TestCase):
    """Tests for the individual order placement (WebUI trading page)."""

    def setUp(self):
        self.trader = PaperTrader(initial_cash=100000.0)
        cfg = AStockFeeConfig(commission_rate=0.0, stamp_tax_rate=0.0, slippage_rate=0.0, min_commission=0.0)
        self.trader._fee_config = cfg

    def test_place_buy_order(self) -> None:
        result = self.trader.place_order("600519.SH", "buy", 500.0, 100)
        self.assertTrue(result["filled"])
        self.assertEqual(result["symbol"], "600519.SH")
        self.assertEqual(result["side"], "buy")
        self.assertEqual(result["price"], 500.0)
        self.assertEqual(result["quantity"], 100)
        self.assertAlmostEqual(result["total"], 50000.0)

    def test_place_buy_order_updates_cash(self) -> None:
        initial_cash = self.trader._state.cash
        self.trader.place_order("600519.SH", "buy", 100.0, 100)
        self.assertAlmostEqual(self.trader._state.cash, initial_cash - 10000.0)
        self.assertIn("600519.SH", self.trader._state.positions)
        self.assertEqual(self.trader._state.positions["600519.SH"], 100)

    def test_place_sell_order(self) -> None:
        # Buy first
        self.trader.place_order("600519.SH", "buy", 100.0, 200)
        result = self.trader.place_order("600519.SH", "sell", 120.0, 100)
        self.assertTrue(result["filled"])
        self.assertEqual(result["side"], "sell")
        self.assertEqual(result["quantity"], 100)
        # Position should be reduced
        self.assertAlmostEqual(self.trader._state.positions["600519.SH"], 100)

    def test_place_sell_order_updates_pnl(self) -> None:
        self.trader.place_order("A", "buy", 100.0, 200)
        self.trader.place_order("A", "sell", 120.0, 200)
        # P&L should be ~ (120*200 - 100*200) = 4000 (no fees)
        self.assertGreater(self.trader._state.pnl, 3999.0)

    def test_place_order_insufficient_cash_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.trader.place_order("600519.SH", "buy", 999999.0, 100)

    def test_place_order_insufficient_shares_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.trader.place_order("600519.SH", "sell", 100.0, 100)

    def test_place_order_invalid_side_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.trader.place_order("600519.SH", "hold", 100.0, 100)

    def test_place_order_zero_quantity_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.trader.place_order("600519.SH", "buy", 100.0, 0)

    def test_place_order_trade_record(self) -> None:
        self.trader.place_order("600519.SH", "buy", 100.0, 200)
        self.assertEqual(len(self.trader._state.trades), 1)
        trade = self.trader._state.trades[0]
        self.assertEqual(trade["type"], "buy")
        self.assertEqual(trade["symbol"], "600519.SH")
        self.assertEqual(trade["shares"], 200)
        self.assertFalse(trade["actionable"])

    def test_place_order_partial_sell_keeps_cost_basis(self) -> None:
        self.trader.place_order("A", "buy", 100.0, 200)
        self.trader.place_order("A", "sell", 120.0, 100)
        # Remaining 100 shares should still be tracked
        self.assertIn("A", self.trader._state.positions)
        self.assertAlmostEqual(self.trader._state.positions["A"], 100)

    def test_place_order_full_sell_removes_position(self) -> None:
        self.trader.place_order("A", "buy", 100.0, 200)
        self.trader.place_order("A", "sell", 120.0, 200)
        self.assertNotIn("A", self.trader._state.positions)


if __name__ == "__main__":
    unittest.main()
