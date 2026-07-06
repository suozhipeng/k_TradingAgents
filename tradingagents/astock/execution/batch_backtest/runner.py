"""Batch backtest runner for multi-symbol, multi-strategy evaluation.

Runs :class:`BacktestEngine` across every (symbol, strategy) pair and
aggregates results for ranking / best-performing selection.
"""

from __future__ import annotations

import uuid
from typing import Any

import pandas as pd

from ..backtest_engine import BacktestEngine, BacktestResult
from ..backtest.fee_model import AStockFeeConfig
from ..strategy_base import StrategyBase
from .ranking import rank_strategies as _rank_strategies
from .selection import best_performing as _best_performing

EXECUTION_SIGNAL: str = "ResearchOnly"


class BatchBacktestRunner:
    """Run backtests across multiple symbols and strategies.

    Parameters
    ----------
    store : AStockStore
        DuckDB-backed store used to persist results.
    fee_config : AStockFeeConfig or None
        Custom fee configuration.  Falls back to defaults.
    """

    def __init__(
        self,
        store: Any,
        fee_config: AStockFeeConfig | None = None,
        use_mock_data: bool = False,
    ) -> None:
        self._store = store
        self._fee_config = fee_config or AStockFeeConfig()
        self._use_mock_data = use_mock_data

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_batch(
        self,
        symbols: list[str],
        strategies: list[StrategyBase],
        start_date: str,
        end_date: str,
        rebalance_freq: str = "M",
        store_results: bool = True,
    ) -> pd.DataFrame:
        """Run backtest for each (symbol, strategy) pair.

        Parameters
        ----------
        symbols : list[str]
            List of A-share symbols (e.g. CSI 300 constituents).
        strategies : list[StrategyBase]
            Strategy instances to test.
        start_date : str
            Backtest start date (``"YYYY-MM-DD"``).
        end_date : str
            Backtest end date (``"YYYY-MM-DD"``).
        rebalance_freq : str
            Pandas offset alias for rebalance periods (default ``"M"``).
        store_results : bool
            Whether to persist batched results to DuckDB (default ``True``).

        Returns
        -------
        pd.DataFrame
            Columns: ``symbol``, ``strategy_name``, ``total_return``,
            ``sharpe``, ``max_drawdown``, ``win_rate``, ``total_trades``.
        """
        engine = BacktestEngine(
            fee_config=self._fee_config,
            use_mock_data=self._use_mock_data,
        )
        records: list[dict[str, Any]] = []

        for symbol in symbols:
            for strategy in strategies:
                result = engine.run(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    strategy=strategy,
                    rebalance_freq=rebalance_freq,
                )
                strategy_name = type(strategy).__name__
                row = {
                    "symbol": symbol,
                    "strategy_name": strategy_name,
                    "total_return": result.total_return,
                    "sharpe": result.sharpe_ratio,
                    "max_drawdown": result.max_drawdown,
                    "win_rate": result.win_rate,
                    "total_trades": result.total_trades,
                }
                records.append(row)

                if store_results:
                    self._store_backtest_result(result, strategy_name)

        df = pd.DataFrame(records)
        if df.empty:
            df = pd.DataFrame(
                columns=[
                    "symbol",
                    "strategy_name",
                    "total_return",
                    "sharpe",
                    "max_drawdown",
                    "win_rate",
                    "total_trades",
                ]
            )
        return df

    def rank_strategies(self, results: pd.DataFrame) -> pd.DataFrame:
        """Rank strategies by aggregate batch performance."""
        return _rank_strategies(results)

    def best_performing(
        self,
        results: pd.DataFrame,
        top_n: int = 10,
    ) -> pd.DataFrame:
        """Return the top symbol/strategy rows from a batch result."""
        return _best_performing(results, top_n=top_n)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _store_backtest_result(
        self, result: BacktestResult, strategy_name: str
    ) -> int:
        """Persist a single backtest result to DuckDB."""
        if not hasattr(self._store, "store_backtest_result"):
            return 0
        run_id = str(uuid.uuid4())[:8]
        data = {
            "run_id": run_id,
            "symbol": result.symbol,
            "strategy_name": strategy_name,
            "start_date": result.start_date,
            "end_date": result.end_date,
            "total_return": result.total_return,
            "annualized_return": result.annualized_return,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "win_rate": result.win_rate,
            "total_trades": result.total_trades,
            "periods": result.periods,
            "fee_config_used": result.fee_config_used,
            "execution_signal": result.execution_signal,
        }
        return self._store.store_backtest_result(data)
