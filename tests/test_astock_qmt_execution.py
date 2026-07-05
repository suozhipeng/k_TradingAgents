"""Tests for the QMT controlled execution engine (qmt_execution.py).

Uses the same direct importlib module-loading pattern as existing tests.
All QmtBridge interactions are done via mock mode (``use_mock=True``).
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from tests.astock_import_helpers import load_astock_submodule

try:
    import pandas as pd  # noqa: F401
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False

# ---------------------------------------------------------------------------
# Direct module imports
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parent.parent
_EXEC = _REPO / "tradingagents" / "astock" / "execution"
_PKG_PARENT = "tradingagents.astock.execution"


def _load_submodule(rel_name: str):
    """Load a module without polluting sys.modules with fake packages."""
    return load_astock_submodule(rel_name, _PKG_PARENT, _EXEC)


# Load modules (dependency order: risk_gate → qmt_bridge → qmt_execution)
_rg = _load_submodule("risk_gate")
_qb = _load_submodule("qmt_bridge")
_qe = _load_submodule("qmt_execution")

QmtBridge = _qb.QmtBridge
ExecutionMode = _qe.ExecutionMode
QmtExecutionConfig = _qe.QmtExecutionConfig
QmtExecutionEngine = _qe.QmtExecutionEngine
RiskGate = _rg.RiskGate
ATRStopLoss = _rg.ATRStopLoss
TrailingStop = _rg.TrailingStop
calculate_atr = _rg.calculate_atr


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine(
    mode: ExecutionMode = ExecutionMode.SAFETY,
    atr_stop_loss_pct: float = 0.10,
) -> QmtExecutionEngine:
    """Create a QmtExecutionEngine with mock bridge for testing."""
    bridge = QmtBridge(use_mock=True)
    config = QmtExecutionConfig(
        mode=mode,
        atr_stop_loss_pct=atr_stop_loss_pct,
        max_position_pct=0.25,
        max_position_volume=10000,
    )
    return QmtExecutionEngine(bridge=bridge, risk_gate=RiskGate(), config=config)


class TestExecutionMode(unittest.TestCase):
    """ExecutionMode enum."""

    def test_safety_value(self) -> None:
        self.assertEqual(ExecutionMode.SAFETY.value, "safety")

    def test_auto_value(self) -> None:
        self.assertEqual(ExecutionMode.AUTO.value, "auto")


class TestQmtExecutionConfig(unittest.TestCase):
    """QmtExecutionConfig defaults and custom values."""

    def test_default_config(self) -> None:
        cfg = QmtExecutionConfig()
        self.assertEqual(cfg.mode, ExecutionMode.SAFETY)
        self.assertEqual(cfg.atr_stop_loss_pct, 0.10)
        self.assertEqual(cfg.trailing_stop_pct, 0.03)
        self.assertEqual(cfg.max_position_pct, 0.25)
        self.assertIsNone(cfg.max_position_volume)
        self.assertIsNone(cfg.log_dir)

    def test_custom_config(self) -> None:
        cfg = QmtExecutionConfig(
            mode=ExecutionMode.AUTO,
            atr_stop_loss_pct=0.15,
            trailing_stop_pct=0.05,
            max_position_pct=0.5,
            max_position_volume=5000,
            log_dir="/tmp/qmt_logs",
        )
        self.assertEqual(cfg.mode, ExecutionMode.AUTO)
        self.assertEqual(cfg.atr_stop_loss_pct, 0.15)
        self.assertEqual(cfg.max_position_volume, 5000)
        self.assertEqual(cfg.log_dir, "/tmp/qmt_logs")


class TestSafetyModeBlocking(unittest.TestCase):
    """SAFETY mode enforcement (default)."""

    def test_safety_mode_blocks_unconfirmed(self) -> None:
        engine = _make_engine(mode=ExecutionMode.SAFETY)
        result = engine.execute(
            signal={"symbol": "000001.SZ", "signal": 1},
            price=10.50,
            volume=1000,
            confirmed=False,
        )
        self.assertFalse(result.get("filled", True))
        self.assertEqual(result.get("blocked"), "safety_mode")

    def test_safety_mode_allows_confirmed(self) -> None:
        engine = _make_engine(mode=ExecutionMode.SAFETY)
        result = engine.execute(
            signal={"symbol": "000001.SZ", "signal": 1},
            price=10.50,
            volume=1000,
            confirmed=True,
        )
        self.assertTrue(result.get("filled", False))
        self.assertIn("order_id", result)

    def test_safety_mode_sell_unconfirmed_blocked(self) -> None:
        engine = _make_engine(mode=ExecutionMode.SAFETY)
        result = engine.execute(
            signal={"symbol": "000001.SZ", "signal": -1},
            price=10.80,
            volume=500,
            confirmed=False,
        )
        self.assertFalse(result.get("filled", True))
        self.assertEqual(result.get("blocked"), "safety_mode")


class TestAutoModeExecution(unittest.TestCase):
    """AUTO mode execution."""

    def test_auto_mode_execute_without_confirm(self) -> None:
        """In AUTO mode, execute() still works (confirmed is optional)."""
        engine = _make_engine(mode=ExecutionMode.AUTO)
        result = engine.execute(
            signal={"symbol": "000001.SZ", "signal": 1},
            price=10.50,
            volume=1000,
            confirmed=False,
        )
        self.assertTrue(result.get("filled", False))

    def test_auto_execute_multiple_signals(self) -> None:
        engine = _make_engine(mode=ExecutionMode.AUTO)
        signals = [
            {"symbol": "000001.SZ", "signal": 1},
            {"symbol": "600519.SH", "signal": 1},
        ]
        prices = {"000001.SZ": 10.50, "600519.SH": 1850.0}
        results = engine.auto_execute(signals, prices)
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].get("filled", False))
        self.assertTrue(results[1].get("filled", False))

    def test_auto_execute_fails_in_safety_mode(self) -> None:
        engine = _make_engine(mode=ExecutionMode.SAFETY)
        signals = [{"symbol": "000001.SZ", "signal": 1}]
        prices = {"000001.SZ": 10.50}
        results = engine.auto_execute(signals, prices)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].get("filled", True))
        self.assertEqual(results[0].get("blocked"), "not_auto")

    def test_auto_execute_missing_price(self) -> None:
        engine = _make_engine(mode=ExecutionMode.AUTO)
        signals = [{"symbol": "000001.SZ", "signal": 1}]
        prices: Dict[str, float] = {}
        results = engine.auto_execute(signals, prices)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].get("filled", True))
        self.assertEqual(results[0].get("reason"), "no_price")


class TestModeSwitching(unittest.TestCase):
    """Mode switching with confirmation requirement."""

    def test_safety_to_auto_needs_confirm(self) -> None:
        engine = _make_engine(mode=ExecutionMode.SAFETY)
        # First call without confirm → pending
        result = engine.set_mode(ExecutionMode.AUTO)
        self.assertEqual(result["status"], "pending_confirm")
        self.assertEqual(engine.mode, ExecutionMode.SAFETY)

    def test_safety_to_auto_confirm_success(self) -> None:
        engine = _make_engine(mode=ExecutionMode.SAFETY)
        # Step 1: request
        engine.set_mode(ExecutionMode.AUTO)
        # Step 2: confirm
        result = engine.set_mode(ExecutionMode.AUTO, confirm=True)
        self.assertEqual(result["status"], "switched")
        self.assertEqual(engine.mode, ExecutionMode.AUTO)

    def test_auto_to_safety_no_confirm_needed(self) -> None:
        engine = _make_engine(mode=ExecutionMode.AUTO)
        result = engine.set_mode(ExecutionMode.SAFETY)
        self.assertEqual(result["status"], "switched")
        self.assertEqual(engine.mode, ExecutionMode.SAFETY)

    def test_switch_to_same_mode_noop(self) -> None:
        engine = _make_engine(mode=ExecutionMode.SAFETY)
        result = engine.set_mode(ExecutionMode.SAFETY)
        self.assertEqual(result["status"], "unchanged")

    def test_cancel_auto_switch(self) -> None:
        engine = _make_engine(mode=ExecutionMode.SAFETY)
        engine.set_mode(ExecutionMode.AUTO)  # pending
        result = engine.set_mode(ExecutionMode.AUTO, confirm=False)  # cancel
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(engine.mode, ExecutionMode.SAFETY)


class TestExecutionLog(unittest.TestCase):
    """Execution log tracking."""

    def test_execution_log_records_trade(self) -> None:
        engine = _make_engine(mode=ExecutionMode.SAFETY)
        engine.execute(
            signal={"symbol": "000001.SZ", "signal": 1},
            price=10.50,
            volume=1000,
            confirmed=True,
        )
        log = engine.execution_log
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["symbol"], "000001.SZ")
        self.assertEqual(log[0]["direction"], "buy")
        self.assertEqual(log[0]["volume"], 1000)

    def test_blocked_trade_not_logged(self) -> None:
        engine = _make_engine(mode=ExecutionMode.SAFETY)
        engine.execute(
            signal={"symbol": "000001.SZ", "signal": 1},
            price=10.50,
            volume=1000,
            confirmed=False,  # blocked
        )
        self.assertEqual(len(engine.execution_log), 0)


class TestRiskGateIntegration(unittest.TestCase):
    """Integration with RiskGate for position caps and ATR stop-loss."""

    def test_position_cap_blocks(self) -> None:
        """Position cap is enforced via risk gate with bridge positions."""
        engine = _make_engine(mode=ExecutionMode.SAFETY)
        # The mock bridge returns positions with 000001.SZ at 1000 shares.
        # With total_asset=1_500_000 and price 10.50, 1000 shares = 10500 value
        # which is < 25% cap, so this won't trigger.
        # Let's lower the cap to intercept.
        engine._config.max_position_pct = 0.0001  # 0.01% — mock position of 0.067% exceeds this
        result = engine.execute(
            signal={"symbol": "000001.SZ", "signal": 1},
            price=10.50,
            volume=1000,
            confirmed=True,
        )
        self.assertFalse(result.get("filled", True))
        self.assertEqual(result.get("blocked"), "risk_gate")

    def test_zero_signal_skipped(self) -> None:
        engine = _make_engine(mode=ExecutionMode.SAFETY)
        result = engine.execute(
            signal={"symbol": "000001.SZ", "signal": 0},
            price=10.50,
            volume=1000,
            confirmed=True,
        )
        self.assertFalse(result.get("filled", True))
        self.assertEqual(result.get("reason"), "no_signal")

    def test_empty_symbol_skipped(self) -> None:
        engine = _make_engine(mode=ExecutionMode.SAFETY)
        result = engine.execute(
            signal={"symbol": "", "signal": 1},
            price=10.50,
            volume=1000,
            confirmed=True,
        )
        self.assertFalse(result.get("filled", True))


class TestUpdateStopLoss(unittest.TestCase):
    """update_stop_loss behaviour."""

    def test_update_stop_loss_tracks_highest(self) -> None:
        engine = _make_engine(mode=ExecutionMode.SAFETY)
        result = engine.update_stop_loss("000001.SZ", 10.50)
        self.assertIn("symbol", result)
        self.assertEqual(result["symbol"], "000001.SZ")
        self.assertEqual(result["current_price"], 10.50)

    def test_update_stop_loss_updates_highest(self) -> None:
        engine = _make_engine(mode=ExecutionMode.SAFETY)
        engine.update_stop_loss("000001.SZ", 10.00)
        result = engine.update_stop_loss("000001.SZ", 10.50)
        self.assertEqual(result["highest_price"], 10.50)


class TestBridgeErrorDegradation(unittest.TestCase):
    """Graceful degradation when bridge calls fail."""

    def test_order_failure_returns_bridge_error(self) -> None:
        """When bridge.place_order raises, execution returns blocked."""
        bridge = QmtBridge(use_mock=True)
        # Patch place_order to raise
        original_place = bridge.place_order

        def _failing_place(*args: Any, **kwargs: Any) -> Any:
            raise ConnectionError("bridge offline")

        bridge.place_order = _failing_place  # type: ignore[assignment]

        engine = QmtExecutionEngine(bridge=bridge, risk_gate=RiskGate())
        result = engine.execute(
            signal={"symbol": "000001.SZ", "signal": 1},
            price=10.50,
            volume=1000,
            confirmed=True,
        )
        self.assertFalse(result.get("filled", True))
        self.assertEqual(result.get("blocked"), "bridge_error")


class TestATRStopLoss(unittest.TestCase):
    """ATRStopLoss standalone tests."""

    def test_atr_stop_loss_not_triggered(self) -> None:
        atr = ATRStopLoss(atr_multiplier=2.0)
        # stop_price = 10.0 - 2*0.2 = 9.6
        # current 9.7 > 9.6 → not triggered
        result = atr.check(entry_price=10.0, current_price=9.7, atr_value=0.2)
        self.assertTrue(result.allowed)

    def test_atr_stop_loss_triggered(self) -> None:
        atr = ATRStopLoss(atr_multiplier=2.0)
        # stop_price = 10.0 - 2*0.2 = 9.6
        # current 9.5 <= 9.6 → trigger
        result = atr.check(entry_price=10.0, current_price=9.5, atr_value=0.2)
        # Actually 9.5 < 9.6, so stop triggered
        self.assertFalse(result.allowed)

    def test_atr_stop_price_calculation(self) -> None:
        atr = ATRStopLoss(atr_multiplier=3.0)
        stop = atr.stop_price(entry_price=100.0, atr_value=2.0)
        self.assertEqual(stop, 94.0)

    def test_atr_stop_default_multiplier(self) -> None:
        atr = ATRStopLoss()
        self.assertEqual(atr.atr_multiplier, 2.0)
        self.assertEqual(atr.atr_period, 14)

    def test_atr_stop_custom_params(self) -> None:
        atr = ATRStopLoss(atr_multiplier=3.5, atr_period=20)
        self.assertEqual(atr.atr_multiplier, 3.5)
        self.assertEqual(atr.atr_period, 20)


class TestCalculateATR(unittest.TestCase):
    """calculate_atr standalone tests."""

    @unittest.skipIf(not _HAS_PANDAS, "pandas not installed")
    def test_calculate_atr_insufficient_data(self) -> None:
        import pandas as pd

        prices = pd.Series([10.0, 10.1])
        atr = calculate_atr(prices, period=14)
        self.assertEqual(atr, 0.0)

    @unittest.skipIf(not _HAS_PANDAS, "pandas not installed")
    def test_calculate_atr_sufficient_data(self) -> None:
        import pandas as pd

        # 20 prices with increasing volatility
        prices = pd.Series([100.0 + i * 0.5 for i in range(20)])
        atr = calculate_atr(prices, period=14)
        self.assertGreater(atr, 0.0)
        self.assertAlmostEqual(atr, 0.5, delta=0.01)

    @unittest.skipIf(not _HAS_PANDAS, "pandas not installed")
    def test_calculate_atr_flat_prices(self) -> None:
        import pandas as pd

        prices = pd.Series([50.0] * 20)
        atr = calculate_atr(prices, period=14)
        self.assertEqual(atr, 0.0)


class TestTrailingStop(unittest.TestCase):
    """TrailingStop standalone tests."""

    def test_trailing_stop_not_activated(self) -> None:
        ts = TrailingStop(activation_pct=0.05, trail_pct=0.02)
        triggered, stop_price = ts.update("000001.SZ", 10.00, 10.00)
        self.assertFalse(triggered)
        self.assertEqual(stop_price, 9.80)

    def test_trailing_stop_activated_not_triggered(self) -> None:
        ts = TrailingStop(activation_pct=0.03, trail_pct=0.02)
        # Start at 10, move to 10.50 (5% gain > 3% activation)
        ts.update("000001.SZ", 10.00, 10.50)
        triggered, stop_price = ts.update("000001.SZ", 10.40, 10.50)
        self.assertFalse(triggered)
        # stop_price = 10.50 * 0.98 = 10.29
        self.assertAlmostEqual(stop_price, 10.29, places=2)

    def test_trailing_stop_triggered(self) -> None:
        ts = TrailingStop(activation_pct=0.03, trail_pct=0.02)
        # Move from 10 to 10.50 (activated)
        ts.update("000001.SZ", 10.00, 10.50)
        # Then drop to 10.20 (which is < 10.29 stop_price)
        triggered, stop_price = ts.update("000001.SZ", 10.20, 10.50)
        self.assertTrue(triggered)

    def test_trailing_stop_reset(self) -> None:
        ts = TrailingStop()
        ts.update("000001.SZ", 10.00, 10.50)
        ts.reset("000001.SZ")
        # After reset, should start fresh
        triggered, _ = ts.update("000001.SZ", 10.00, 10.00)
        self.assertFalse(triggered)

    def test_trailing_stop_default_params(self) -> None:
        ts = TrailingStop()
        self.assertEqual(ts.activation_pct, 0.03)
        self.assertEqual(ts.trail_pct, 0.02)


if __name__ == "__main__":
    unittest.main()
