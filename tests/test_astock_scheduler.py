"""Paper trade scheduler tests — at least 4 tests.

Tests verify:
1. Scheduler starts and stops cleanly
2. execute_scheduled_cycle runs without error
3. Scheduler publishes events to EventBus
4. Multiple cycles don't crash
"""

from __future__ import annotations

import importlib.util
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

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

# Load dependencies
_sb = _load_submodule("strategy_base")
_fm = _load_submodule("fee_model")
_pt = _load_submodule("paper_trader")
_eb = _load_submodule("event_bus")
_sc = _load_submodule("scheduler")

StrategyBase = _sb.StrategyBase
MovingAverageTrendStrategy = _sb.MovingAverageTrendStrategy
PaperTrader = _pt.PaperTrader
EventBus = _eb.EventBus
PaperTradeScheduler = _sc.PaperTradeScheduler


class TestPaperTradeScheduler(unittest.TestCase):
    """Test suite for PaperTradeScheduler."""

    def setUp(self):
        # Clear EventBus before each test
        EventBus.clear()
        self.mock_store = MagicMock()
        # Mock query_kline to return a small DataFrame
        dates = pd.bdate_range(end="2026-06-12", periods=60)
        df = pd.DataFrame(
            {
                "trade_date": dates,
                "open": [100.0 + i * 0.1 for i in range(len(dates))],
                "high": [101.0 + i * 0.1 for i in range(len(dates))],
                "low": [99.0 + i * 0.1 for i in range(len(dates))],
                "close": [100.0 + i * 0.1 for i in range(len(dates))],
                "volume": [1000000 for _ in range(len(dates))],
            }
        )
        self.mock_store.query_kline.return_value = df
        self.trader = PaperTrader(initial_cash=100000.0)
        self.scheduler = PaperTradeScheduler(
            paper_trader=self.trader,
            store=self.mock_store,
            interval_minutes=1,  # 1 minute for fast tests
            symbols=["600519.SH"],
        )

    def tearDown(self):
        if self.scheduler.running:
            self.scheduler.stop()
        EventBus.clear()

    def test_scheduler_start_stop(self):
        """Scheduler can be started and stopped cleanly."""
        self.assertFalse(self.scheduler.running)
        self.scheduler.start()
        self.assertTrue(self.scheduler.running)
        # Give it a moment to run the first cycle
        time.sleep(0.1)
        self.scheduler.stop()
        self.assertFalse(self.scheduler.running)
        self.assertGreaterEqual(self.scheduler.cycle_count, 1)

    def test_execute_scheduled_cycle_runs(self):
        """execute_scheduled_cycle runs without raising exceptions."""
        try:
            self.scheduler.execute_scheduled_cycle()
        except Exception as e:
            self.fail(f"execute_scheduled_cycle raised: {e}")

    def test_scheduler_publishes_events(self):
        """Scheduler publishes cycle events to EventBus."""
        self.scheduler.execute_scheduled_cycle()
        events = EventBus.peek_all()
        # Should have at least cycle_start and cycle_end events
        event_types = {e.get("type") for e in events}
        self.assertIn("cycle_start", event_types)
        self.assertIn("cycle_end", event_types)

    def test_scheduler_cycle_count_increments(self):
        """Cycle count increments with each cycle."""
        self.assertEqual(self.scheduler.cycle_count, 0)
        self.scheduler.execute_scheduled_cycle()
        self.assertEqual(self.scheduler.cycle_count, 1)
        self.scheduler.execute_scheduled_cycle()
        self.assertEqual(self.scheduler.cycle_count, 2)

    def test_scheduler_handles_empty_store(self):
        """Scheduler handles empty store gracefully."""
        empty_store = MagicMock()
        empty_store.query_kline.return_value = pd.DataFrame()
        scheduler = PaperTradeScheduler(
            paper_trader=self.trader,
            store=empty_store,
            interval_minutes=10,
            symbols=["600519.SH"],
        )
        try:
            scheduler.execute_scheduled_cycle()
        except Exception as e:
            self.fail(f"Scheduler raised on empty store: {e}")
        # Should still publish cycle events
        events = EventBus.peek_all()
        self.assertGreater(len(events), 0)


if __name__ == "__main__":
    unittest.main()
