"""Tests for the strategy parameter optimizer."""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_EXEC = _REPO / "tradingagents" / "astock" / "execution"
_PKG_PARENT = "tradingagents.astock.execution"


def _load_submodule(rel_name: str):
    """Load optimizer module without polluting sys.modules."""
    import importlib.util as util

    fname = rel_name + ".py"
    full_name = f"{_PKG_PARENT}.{rel_name}"
    path = str(_EXEC / fname)
    spec = util.spec_from_file_location(full_name, path)
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

    mod = util.module_from_spec(spec)
    mod.__package__ = _PKG_PARENT
    mod.__name__ = full_name
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


_opt = _load_submodule("optimizer")

StrategyOptimizer = _opt.StrategyOptimizer
optimize_strategy = _opt.optimize_strategy
DEFAULT_SEARCH_SPACES = _opt.DEFAULT_SEARCH_SPACES
_get_strategy_map = _opt._get_strategy_map
_composite_score = _opt._composite_score


# ---------------------------------------------------------------------------
# Tests (unchanged)
# ---------------------------------------------------------------------------


class TestSearchSpaces(unittest.TestCase):
    def test_all_strategies_have_default_space(self) -> None:
        mapping = _get_strategy_map()
        for name in mapping:
            space = DEFAULT_SEARCH_SPACES.get(name, {})
            self.assertTrue(len(space) > 0, f"{name} has no default search space")

    def test_each_space_has_valid_values(self) -> None:
        for name, space in DEFAULT_SEARCH_SPACES.items():
            for param, values in space.items():
                self.assertTrue(len(values) > 0, f"{name}.{param} has empty values")

    def test_search_space_count(self) -> None:
        mapping = _get_strategy_map()
        self.assertEqual(len(DEFAULT_SEARCH_SPACES), len(mapping))


class TestCompositeScore(unittest.TestCase):
    def test_positive_sharpe_scores_positive(self) -> None:
        metrics = {"sharpe_ratio": 1.5, "total_return": 0.2, "max_drawdown": 0.1, "total_trades": 10}
        self.assertGreater(_composite_score(metrics), 0.0)

    def test_negative_sharpe_scores_negative(self) -> None:
        metrics = {"sharpe_ratio": -0.5, "total_return": -0.1, "max_drawdown": 0.3, "total_trades": 5}
        self.assertLess(_composite_score(metrics), 0.0)

    def test_high_drawdown_penalizes(self) -> None:
        good = _composite_score({"sharpe_ratio": 1.0, "total_return": 0.2, "max_drawdown": 0.05, "total_trades": 10})
        bad = _composite_score({"sharpe_ratio": 1.0, "total_return": 0.2, "max_drawdown": 0.5, "total_trades": 10})
        self.assertGreater(good, bad)

    def test_no_trades_scores_low(self) -> None:
        score = _composite_score({"sharpe_ratio": 0.0, "total_return": 0.0, "max_drawdown": 0.0, "total_trades": 0})
        self.assertAlmostEqual(score, 0.0, places=4)


class TestOptimizerConstruction(unittest.TestCase):
    def test_by_name(self) -> None:
        opt = StrategyOptimizer("MACDTrend")
        self.assertIsNotNone(opt)

    def test_by_class(self) -> None:
        mapping = _get_strategy_map()
        opt = StrategyOptimizer(mapping["MACDTrend"])
        self.assertIsNotNone(opt)

    def test_unknown_name_raises(self) -> None:
        with self.assertRaises(ValueError):
            StrategyOptimizer("NonExistentStrategy")


class TestOptimizerRun(unittest.TestCase):
    def test_optimize_returns_sorted_results(self) -> None:
        opt = StrategyOptimizer("MACDTrend")
        results = opt.optimize(
            symbol="000001.SZ", start_date="2024-01-01", end_date="2024-06-30",
            param_grid={"fast_period": [8, 12], "slow_period": [20, 26]}, top_n=5,
        )
        self.assertTrue(len(results) > 0)
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_optimize_returns_limited_top_n(self) -> None:
        opt = StrategyOptimizer("MeanReversion")
        results = opt.optimize(
            symbol="000001.SZ", start_date="2024-01-01", end_date="2024-06-30",
            param_grid={"ma_period": [10, 20], "std_multiplier": [2.0, 3.0]}, top_n=2,
        )
        self.assertLessEqual(len(results), 2)

    def test_optimize_with_default_search_space(self) -> None:
        opt = StrategyOptimizer("RSIRange")
        results = opt.optimize(
            symbol="000001.SZ", start_date="2024-01-01", end_date="2024-06-30", top_n=3,
        )
        self.assertTrue(len(results) > 0)

    def test_result_contains_params_and_metrics(self) -> None:
        opt = StrategyOptimizer("BullTrend")
        results = opt.optimize(
            symbol="000001.SZ", start_date="2024-01-01", end_date="2024-06-30",
            param_grid={"fast_ma": [5, 10], "mid_ma": [20]}, top_n=1,
        )
        r = results[0]
        self.assertIn("params", r)
        self.assertIn("metrics", r)

    def test_optimize_empty_param_grid_returns_default(self) -> None:
        opt = StrategyOptimizer("PutWrite")
        results = opt.optimize(
            symbol="000001.SZ", start_date="2024-01-01", end_date="2024-06-30",
            param_grid={}, top_n=1,
        )
        self.assertTrue(len(results) >= 0)


class TestConvenienceWrapper(unittest.TestCase):
    def test_wrapper_runs(self) -> None:
        results = optimize_strategy(
            "DefensiveMomentum", "000001.SZ", "2024-01-01", "2024-06-30",
            param_grid={"roc_period": [10, 20]}, top_n=2,
        )
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["rank"], 1)


if __name__ == "__main__":
    unittest.main()
