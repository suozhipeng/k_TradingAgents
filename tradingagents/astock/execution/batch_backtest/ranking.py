"""Strategy ranking utilities."""

from __future__ import annotations

import pandas as pd


def rank_strategies(results: pd.DataFrame) -> pd.DataFrame:
    """Rank strategies by average return across all symbols.

    Parameters
    ----------
    results : pd.DataFrame
        Output of :meth:`run_batch`.

    Returns
    -------
    pd.DataFrame
        Sorted by ``avg_return`` descending, with columns
        ``strategy_name``, ``avg_return``, ``avg_sharpe``,
        ``avg_max_drawdown``, ``count``.
    """
    if results.empty:
        return pd.DataFrame(
            columns=[
                "strategy_name",
                "avg_return",
                "avg_sharpe",
                "avg_max_drawdown",
                "count",
            ]
        )
    grouped = results.groupby("strategy_name", as_index=False).agg(
        avg_return=("total_return", "mean"),
        avg_sharpe=("sharpe", "mean"),
        avg_max_drawdown=("max_drawdown", "mean"),
        count=("symbol", "count"),
    )
    return grouped.sort_values("avg_return", ascending=False).reset_index(drop=True)
