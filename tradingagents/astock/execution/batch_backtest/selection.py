"""Best-performing selection utilities."""

from __future__ import annotations

import pandas as pd


def best_performing(results: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Return top N (symbol, strategy) combinations by total_return.

    Parameters
    ----------
    results : pd.DataFrame
        Output of :meth:`run_batch`.
    top_n : int
        Number of results to return (default ``10``).

    Returns
    -------
    pd.DataFrame
        Top ``top_n`` rows sorted by ``total_return`` descending.
    """
    if results.empty:
        return results
    return results.sort_values("total_return", ascending=False).head(top_n).reset_index(drop=True)
