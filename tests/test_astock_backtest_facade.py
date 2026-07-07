from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from rich.console import Console

from tests.astock_import_helpers import load_astock_submodule

_REPO = Path(__file__).resolve().parent.parent
_EXEC = _REPO / "tradingagents" / "astock" / "execution"
_PKG_PARENT = "tradingagents.astock.execution"


def _load_submodule(rel_name: str):
    return load_astock_submodule(rel_name, _PKG_PARENT, _EXEC)


_facade = _load_submodule("backtest_engine.facade")
_be = _load_submodule("backtest_engine")

ExecBacktestResult = _be.BacktestResult


class TestBacktestFacade(unittest.TestCase):
    def test_supported_strategy_uses_execution_engine(self) -> None:
        from modules.backtest_engine import PipelineParams

        fake_exec_result = ExecBacktestResult(
            symbol="MOCK.SH",
            strategy_name="MovingAverageTrend",
            start_date="2024-01-02",
            end_date="2024-02-29",
            total_return=0.12,
            annualized_return=0.34,
            sharpe_ratio=1.23,
            max_drawdown=0.08,
            win_rate=0.5,
            total_trades=2,
            trades=[{"type": "buy", "price": 10.0, "shares": 100.0, "fees": 5.0, "pnl": 0.0}],
            periods=[{"period": "2024-01-31", "signal": 1, "end_value": 112000.0, "cash": 0.0, "shares": 100.0}],
        )

        params = PipelineParams(
            symbol="MOCK.SH",
            strategy_name="MovingAverageTrend",
            start_date="2024-01-02",
            end_date="2024-02-29",
            strategy_config={"fast_period": 3, "slow_period": 7},
        )

        from modules.backtest_engine import BacktestMetrics as ModMetrics, BacktestResult as ModResult
        fake_persist = mock.MagicMock()

        with mock.patch.object(_facade, "_build_execution_strategy", return_value=object()) as build_strategy, \
             mock.patch("tradingagents.astock.execution.backtest_engine.engine.BacktestEngine.run", return_value=fake_exec_result) as run_mock, \
             mock.patch.object(_facade, "_legacy_backtest_exports", return_value=(ModMetrics, ModResult, fake_persist, None)) as exports_mock:
            result = _facade.run_backtest_via_facade(params)

        build_strategy.assert_called_once_with("MovingAverageTrend", {"fast_period": 3, "slow_period": 7})
        run_mock.assert_called_once()
        fake_persist.assert_called_once()
        self.assertEqual(result.strategy_name, "MovingAverageTrend")
        self.assertEqual(result.metrics.total_trades, 2)
        self.assertEqual(result.trades[0]["direction"], "buy")

    def test_modules_only_strategy_falls_back(self) -> None:
        from modules.backtest_engine import PipelineParams, BacktestResult, BacktestMetrics

        params = PipelineParams(
            symbol="MOCK.SH",
            strategy_name="AbsoluteLimitUpScore",
            start_date="2024-01-02",
            end_date="2024-02-29",
            strategy_config={},
        )
        fake_result = BacktestResult(
            run_id="demo",
            symbol="MOCK.SH",
            strategy_name="AbsoluteLimitUpScore",
            start_date="2024-01-02",
            end_date="2024-02-29",
            initial_cash=100000.0,
            final_value=101000.0,
            metrics=BacktestMetrics(total_return=0.01),
        )

        from modules.backtest_engine import BacktestMetrics as ModMetrics, BacktestResult as ModResult
        fake_legacy = mock.MagicMock(return_value=fake_result)

        with mock.patch.object(_facade, "_legacy_backtest_exports", return_value=(ModMetrics, ModResult, None, fake_legacy)) as exports_mock:
            result = _facade.run_backtest_via_facade(params)

        fake_legacy.assert_called_once_with(params)
        self.assertEqual(result.strategy_name, "AbsoluteLimitUpScore")


class TestCliBacktestCommand(unittest.TestCase):
    def test_cli_backtest_uses_facade(self) -> None:
        import cli.main as m
        from modules.backtest_engine import BacktestMetrics, BacktestResult

        fake_result = BacktestResult(
            run_id="demo",
            symbol="MOCK.SH",
            strategy_name="MovingAverageTrend",
            start_date="2024-01-02",
            end_date="2024-02-29",
            initial_cash=100000.0,
            final_value=101152.39,
            metrics=BacktestMetrics(
                total_return=0.011524,
                annualized_return=1.618165,
                sharpe_ratio=6.89243,
                max_drawdown=0.002245,
                win_rate=0.0,
                total_trades=1,
            ),
        )
        capture = Console(record=True, width=120)

        with mock.patch("tradingagents.astock.execution.backtest_engine.run_backtest_pipeline", return_value=fake_result) as facade_mock, \
             mock.patch.object(m, "console", capture):
            m.backtest("MOCK.SH", strategy="MovingAverageTrend", start="2024-01-02", end="2024-02-29", json_output=True)

        facade_mock.assert_called_once()
        text = capture.export_text()
        self.assertIn('"symbol": "MOCK.SH"', text)
        self.assertIn('"strategy": "MovingAverageTrend"', text)
        self.assertIn('"total_trades": 1', text)


class TestExecutionPackageCompatExports(unittest.TestCase):
    def test_execution_package_exposes_legacy_compat_symbols(self) -> None:
        import tradingagents.astock.execution.backtest_engine as pkg

        self.assertIsNotNone(pkg.PipelineParams)
        self.assertIsNotNone(pkg.create_strategy)
        self.assertIsNotNone(pkg.BacktestMetrics)


class TestLegacyModulesEntry(unittest.TestCase):
    def test_modules_public_entry_delegates_to_facade(self) -> None:
        import modules.backtest_engine as legacy
        from modules.backtest_engine import BacktestMetrics, BacktestResult, PipelineParams

        params = PipelineParams(
            symbol="MOCK.SH",
            strategy_name="MovingAverageTrend",
            start_date="2024-01-02",
            end_date="2024-02-29",
            strategy_config={"fast_period": 3, "slow_period": 7},
        )
        fake_result = BacktestResult(
            run_id="demo",
            symbol="MOCK.SH",
            strategy_name="MovingAverageTrend",
            start_date="2024-01-02",
            end_date="2024-02-29",
            initial_cash=100000.0,
            final_value=101152.39,
            metrics=BacktestMetrics(total_return=0.011524, total_trades=1),
        )

        with mock.patch("tradingagents.astock.execution.backtest_engine.facade.run_backtest_via_facade", return_value=fake_result) as facade_mock:
            result = legacy.run_backtest_pipeline(params)

        facade_mock.assert_called_once_with(params)
        self.assertEqual(result.final_value, 101152.39)


if __name__ == "__main__":
    unittest.main()
