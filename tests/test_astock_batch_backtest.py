"""Batch backtest runner tests — at least 8 tests.

Tests verify:
1. run_batch returns correct columns
2. run_batch handles empty symbols
3. run_batch handles empty strategies
4. rank_strategies sorts by avg_return
5. rank_strategies handles empty results
6. best_performing returns top N
7. best_performing handles empty results
8. Store results flag works (True/False)
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from tests.astock_import_helpers import load_astock_submodule

_REPO = Path(__file__).resolve().parent.parent
_EXEC = _REPO / "tradingagents" / "astock" / "execution"
_PKG_PARENT = "tradingagents.astock.execution"

def _load_submodule(rel_name: str):
    """Load a module without polluting sys.modules with fake packages."""
    return load_astock_submodule(rel_name, _PKG_PARENT, _EXEC)

# Load dependencies
_fm = _load_submodule("backtest.fee_model")
_sb = _load_submodule("strategy_base")
_be = _load_submodule("backtest_engine")
_bb = _load_submodule("batch_backtest")

AStockFeeConfig = _fm.AStockFeeConfig
StrategyBase = _sb.StrategyBase
MovingAverageTrendStrategy = _sb.MovingAverageTrendStrategy
BullTrendStrategy = _sb.BullTrendStrategy
MeanReversionStrategy = _sb.MeanReversionStrategy
BatchBacktestRunner = _bb.BatchBacktestRunner


class TestBatchBacktestRunner(unittest.TestCase):
    """Test suite for BatchBacktestRunner."""

    def setUp(self):
        self.store = MagicMock()
        self.store.store_backtest_result.return_value = 1
        self.runner = BatchBacktestRunner(store=self.store, use_mock_data=True)
        self.symbols = ["600519.SH", "000858.SZ", "000300.SH"]
        self.strategies = [
            MovingAverageTrendStrategy(),
            BullTrendStrategy(),
            MeanReversionStrategy(),
        ]

    def test_run_batch_returns_correct_columns(self):
        """run_batch returns DataFrame with expected columns."""
        results = self.runner.run_batch(
            symbols=self.symbols,
            strategies=self.strategies,
            start_date="2024-01-02",
            end_date="2024-03-29",
            store_results=False,
        )
        expected_cols = {
            "symbol", "strategy_name", "total_return",
            "sharpe", "max_drawdown", "win_rate", "total_trades",
        }
        self.assertEqual(set(results.columns), expected_cols)
        self.assertGreater(len(results), 0)
        # Number of rows = symbols * strategies
        self.assertEqual(len(results), len(self.symbols) * len(self.strategies))

    def test_run_batch_empty_symbols(self):
        """run_batch returns empty DataFrame when symbols list is empty."""
        results = self.runner.run_batch(
            symbols=[],
            strategies=self.strategies,
            start_date="2024-01-02",
            end_date="2024-03-29",
            store_results=False,
        )
        self.assertTrue(results.empty)

    def test_run_batch_empty_strategies(self):
        """run_batch returns empty DataFrame when strategies list is empty."""
        results = self.runner.run_batch(
            symbols=self.symbols,
            strategies=[],
            start_date="2024-01-02",
            end_date="2024-03-29",
            store_results=False,
        )
        self.assertTrue(results.empty)

    def test_rank_strategies_sorts_by_avg_return(self):
        """rank_strategies returns strategies sorted by avg_return descending."""
        results = self.runner.run_batch(
            symbols=self.symbols,
            strategies=self.strategies,
            start_date="2024-01-02",
            end_date="2024-03-29",
            store_results=False,
        )
        ranked = self.runner.rank_strategies(results)
        self.assertIn("avg_return", ranked.columns)
        self.assertIn("strategy_name", ranked.columns)
        # Verify descending order
        returns = ranked["avg_return"].tolist()
        self.assertEqual(returns, sorted(returns, reverse=True))
        # Each strategy appears once
        self.assertEqual(len(ranked), len(self.strategies))

    def test_rank_strategies_empty_results(self):
        """rank_strategies returns empty DataFrame for empty input."""
        empty_df = pd.DataFrame()
        ranked = self.runner.rank_strategies(empty_df)
        self.assertTrue(ranked.empty)

    def test_best_performing_returns_top_n(self):
        """best_performing returns top N (symbol, strategy) combinations."""
        results = self.runner.run_batch(
            symbols=self.symbols,
            strategies=self.strategies,
            start_date="2024-01-02",
            end_date="2024-03-29",
            store_results=False,
        )
        top3 = self.runner.best_performing(results, top_n=3)
        self.assertEqual(len(top3), 3)
        # Verify sorted descending
        returns = top3["total_return"].tolist()
        self.assertEqual(returns, sorted(returns, reverse=True))

    def test_best_performing_top_n_greater_than_results(self):
        """best_performing returns all rows when top_n > total rows."""
        results = self.runner.run_batch(
            symbols=["600519.SH"],
            strategies=[self.strategies[0]],
            start_date="2024-01-02",
            end_date="2024-03-29",
            store_results=False,
        )
        top100 = self.runner.best_performing(results, top_n=100)
        self.assertEqual(len(top100), len(results))

    def test_best_performing_empty_results(self):
        """best_performing returns empty DataFrame for empty input."""
        empty_df = pd.DataFrame()
        best = self.runner.best_performing(empty_df, top_n=5)
        self.assertTrue(best.empty)

    def test_store_results_true(self):
        """When store_results=True, store_backtest_result is called."""
        self.runner.run_batch(
            symbols=["600519.SH"],
            strategies=[self.strategies[0]],
            start_date="2024-01-02",
            end_date="2024-03-29",
            store_results=True,
        )
        # store_backtest_result should have been called at least once
        self.assertGreater(self.store.store_backtest_result.call_count, 0)

    def test_store_results_false(self):
        """When store_results=False, store_backtest_result is not called."""
        store = MagicMock()
        runner = BatchBacktestRunner(store=store, use_mock_data=True)
        runner.run_batch(
            symbols=["600519.SH"],
            strategies=[self.strategies[0]],
            start_date="2024-01-02",
            end_date="2024-03-29",
            store_results=False,
        )
        store.store_backtest_result.assert_not_called()


if __name__ == "__main__":
    unittest.main()
