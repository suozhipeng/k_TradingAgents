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
    """Load a module from the execution package with correct package context."""
    fname = rel_name + ".py"
    full_name = f"{_PKG_PARENT}.{rel_name}"
    path = str(_EXEC / fname)
    spec = importlib.util.spec_from_file_location(full_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {full_name} from {path}")
    # Ensure parent packages exist in sys.modules
    for parent in ("tradingagents", "tradingagents.astock", "tradingagents.astock.execution"):
        if parent not in sys.modules:
            pkg_spec = importlib.util.spec_from_loader(parent, loader=None, is_package=True)
            parent_mod = importlib.util.module_from_spec(pkg_spec)
            parent_mod.__path__ = []
            sys.modules[parent] = parent_mod
    # Set up execution package with __path__ so relative imports resolve
    exec_pkg = sys.modules[_PKG_PARENT]
    exec_pkg.__path__ = [str(_EXEC)]

    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = _PKG_PARENT  # critical: set package for relative imports
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


if __name__ == "__main__":
    unittest.main()
