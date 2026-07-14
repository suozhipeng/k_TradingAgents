"""Regression tests for production-readiness fixes.

Tests cover:
1. asyncio.run() event loop conflict fix in executor.py / validated_store.py
2. Threading lock on PaperTrader
3. Scheduler timeout protection (ThreadPoolExecutor + per-symbol timeout)
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from tests.astock_import_helpers import load_astock_submodule

_REPO = Path(__file__).resolve().parent.parent
_EXEC = _REPO / "tradingagents" / "astock" / "execution"
_QUAL = _REPO / "tradingagents" / "astock" / "quality"
_PKG_EXEC = "tradingagents.astock.execution"
_PKG_QUAL = "tradingagents.astock.quality"


def _load(rel_name: str, pkg_parent: str, base_dir: Path):
    return load_astock_submodule(rel_name, pkg_parent, base_dir)


# Load modules
_fm = _load("backtest.fee_model", _PKG_EXEC, _EXEC)
_pt = _load("paper_trader", _PKG_EXEC, _EXEC)
_eb = _load("infrastructure.event_bus", _PKG_EXEC, _EXEC)
_sc = _load("scheduler", _PKG_EXEC, _EXEC)

# Quality modules are flat files
_sys_modules_backup = dict(sys.modules)
try:
    _qe_mod = _load("executor", "tradingagents.astock.quality", _QUAL)
    _qe = _qe_mod
    _vs_mod = _load("validated_store", "tradingagents.astock.quality", _QUAL)
    _vs = _vs_mod
except ImportError:
    sys.path.insert(0, str(_QUAL.parent))
    import quality.executor as _qe_raw
    import quality.validated_store as _vs_raw
    _qe = _qe_raw
    _vs = _vs_raw
finally:
    sys.modules.update(_sys_modules_backup)

PaperTrader = _pt.PaperTrader
EventBus = _eb.EventBus
PaperTradeScheduler = _sc.PaperTradeScheduler
QualityExecutor = _qe.QualityExecutor
ValidatedStore = _vs.ValidatedStore
AStockFeeConfig = _fm.AStockFeeConfig


# ===================================================================
# Fix 1: asyncio.run() event loop conflict
# ===================================================================


class TestAsyncioEventLoopConflict(unittest.TestCase):

    def test_executor_run_async_without_loop(self):
        result = QualityExecutor._run_async(asyncio.sleep(0.01, result=42))
        self.assertEqual(result, 42)

    def test_executor_run_async_inside_loop(self):
        async def _inner():
            sub_result = QualityExecutor._run_async(asyncio.sleep(0.01, result="nested_ok"))
            return sub_result

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_inner())
            self.assertEqual(result, "nested_ok")
        finally:
            loop.close()

    def test_validated_store_sync_run_without_loop(self):
        async def _async_fn(x):
            await asyncio.sleep(0.01)
            return x * 2

        result = _vs._sync_run(_async_fn, 21)
        self.assertEqual(result, 42)

    def test_validated_store_sync_run_inside_loop(self):
        async def _async_fn(x):
            await asyncio.sleep(0.01)
            return x * 3

        async def _outer():
            return _vs._sync_run(_async_fn, 7)

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_outer())
            self.assertEqual(result, 21)
        finally:
            loop.close()


# ===================================================================
# Fix 2: Threading lock on PaperTrader
# ===================================================================


class TestPaperTraderThreadSafety(unittest.TestCase):

    def test_has_lock_attribute(self):
        trader = PaperTrader()
        self.assertTrue(hasattr(trader, "_lock"))
        self.assertIsInstance(trader._lock, type(threading.Lock()))

    def test_concurrent_execute_cycle_and_place_order(self):
        """Concurrent execute_cycle + place_order should not corrupt state."""
        trader = PaperTrader(initial_cash=100000.0)
        cfg = AStockFeeConfig(commission_rate=0.0, stamp_tax_rate=0.0, slippage_rate=0.0, min_commission=0.0)
        trader._fee_config = cfg

        errors = []
        results = {"cycle": None, "order": None}

        def _do_cycle():
            try:
                state = trader.execute_cycle(
                    {"600519.SH": 0.0},  # hold signal — no trade
                    {"600519.SH": 10.0},
                )
                results["cycle"] = state.total_value
            except Exception as e:
                errors.append(("cycle", e))

        def _do_order():
            try:
                order = trader.place_order("000001.SH", "buy", 100.0, 50)
                results["order"] = order.status.value
            except Exception as e:
                errors.append(("order", e))

        t1 = threading.Thread(target=_do_cycle)
        t2 = threading.Thread(target=_do_order)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        self.assertEqual(len(errors), 0, f"Errors during concurrent access: {errors}")
        self.assertIsNotNone(results["cycle"])
        self.assertEqual(results["order"], "filled")

    def test_concurrent_execute_cycles(self):
        """Two concurrent execute_cycle calls should not corrupt state."""
        trader = PaperTrader(initial_cash=100000.0)
        cfg = AStockFeeConfig(commission_rate=0.0, stamp_tax_rate=0.0, slippage_rate=0.0, min_commission=0.0)
        trader._fee_config = cfg

        errors = []

        def _do_cycle(symbol, price):
            try:
                trader.execute_cycle({symbol: 1.0}, {symbol: price})
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=_do_cycle, args=("A", 100.0))
        t2 = threading.Thread(target=_do_cycle, args=("B", 200.0))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        self.assertEqual(len(errors), 0)
        state = trader.get_state()
        self.assertGreaterEqual(len(state.positions), 1)

    def test_concurrent_get_state_reads_consistent(self):
        """get_state should return a consistent snapshot during concurrent writes."""
        trader = PaperTrader(initial_cash=100000.0)
        cfg = AStockFeeConfig(commission_rate=0.0, stamp_tax_rate=0.0, slippage_rate=0.0, min_commission=0.0)
        trader._fee_config = cfg

        inconsistent = []

        def _writer():
            for _ in range(20):
                trader.execute_cycle({"A": 1.0}, {"A": 100.0})

        def _reader():
            for _ in range(20):
                state = trader.get_state()
                if state.total_value < state.cash - 0.01:
                    inconsistent.append(
                        f"total_value={state.total_value} < cash={state.cash}"
                    )

        t1 = threading.Thread(target=_writer)
        t2 = threading.Thread(target=_reader)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        self.assertEqual(len(inconsistent), 0, f"Inconsistent reads: {inconsistent}")


# ===================================================================
# Fix 3: Scheduler timeout protection
# ===================================================================


class TestSchedulerTimeoutProtection(unittest.TestCase):

    def setUp(self):
        EventBus.clear()
        self.mock_store = MagicMock()
        dates = pd.bdate_range(end="2026-06-12", periods=60)
        df = pd.DataFrame({
            "trade_date": dates,
            "open": [100.0 + i * 0.1 for i in range(len(dates))],
            "high": [101.0 + i * 0.1 for i in range(len(dates))],
            "low": [99.0 + i * 0.1 for i in range(len(dates))],
            "close": [100.0 + i * 0.1 for i in range(len(dates))],
            "volume": [1000000 for _ in range(len(dates))],
        })
        self.mock_store.query_kline.return_value = df
        self.trader = PaperTrader(initial_cash=100000.0)
        self.scheduler = PaperTradeScheduler(
            paper_trader=self.trader,
            store=self.mock_store,
            interval_minutes=1,
            symbols=["600519.SH", "000001.SH"],
        )

    def tearDown(self):
        if self.scheduler.running:
            self.scheduler.stop()
        EventBus.clear()

    def test_cycle_completes_with_timeout(self):
        self.scheduler._execute_scheduled_cycle()
        self.assertGreater(self.scheduler.cycle_count, 0)
        events = EventBus.peek_all()
        complete_events = [e for e in events if e.get("type") == "cycle_complete"]
        self.assertTrue(len(complete_events) > 0)

    def test_slow_symbol_does_not_block_others(self):
        """A slow symbol should timeout and not block other symbols."""
        slow_call = {"fired": False}

        def slow_query_kline(symbol):
            if symbol == "SLOW":
                slow_call["fired"] = True
                time.sleep(5)
            dates = pd.bdate_range(end="2026-06-12", periods=60)
            return pd.DataFrame({
                "trade_date": dates,
                "open": [100.0] * len(dates),
                "high": [101.0] * len(dates),
                "low": [99.0] * len(dates),
                "close": [100.5] * len(dates),
                "volume": [1000000] * len(dates),
            })

        self.mock_store.query_kline.side_effect = slow_query_kline
        self.scheduler._symbols = ["FAST", "SLOW"]
        self.scheduler.SYMBOL_TIMEOUT = 1.0

        start = time.time()
        self.scheduler._execute_scheduled_cycle()
        elapsed = time.time() - start

        # If SLOW was processed normally it would take 5s+.
        # With timeout it should complete in ~1-2s.
        self.assertLess(elapsed, 3.0, f"Cycle took {elapsed:.1f}s — SLOW symbol was not timed out")
        self.assertTrue(slow_call["fired"], "SLOW symbol query was never attempted")

    def test_process_symbol_returns_correct_tuple(self):
        result = self.scheduler._process_symbol("600519.SH")
        self.assertIsNotNone(result)
        price, signal = result
        self.assertIsInstance(price, float)
        self.assertIsInstance(signal, float)
        self.assertIn(signal, [-1.0, 0.0, 1.0])

    def test_process_symbol_returns_none_for_empty(self):
        self.mock_store.query_kline.return_value = pd.DataFrame()
        result = self.scheduler._process_symbol("EMPTY")
        self.assertIsNone(result)

    def test_class_has_timeout_attributes(self):
        self.assertTrue(hasattr(PaperTradeScheduler, "SYMBOL_TIMEOUT"))
        self.assertTrue(hasattr(PaperTradeScheduler, "CYCLE_TIMEOUT"))
        self.assertIsInstance(PaperTradeScheduler.SYMBOL_TIMEOUT, float)
        self.assertIsInstance(PaperTradeScheduler.CYCLE_TIMEOUT, float)


if __name__ == "__main__":
    unittest.main()
