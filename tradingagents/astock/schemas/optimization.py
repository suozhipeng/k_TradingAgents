"""OptimizeResult schema — structured output for strategy optimization runs.

The optimizer tests multiple parameter combinations and returns the best
configuration along with in-sample / out-sample / walk-forward performance.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OptimizeResult(BaseModel):
    """Result of a strategy parameter optimization.

    Attributes
    ----------
    strategy_name : str
    symbol : str
    score : float
        Optimization score (higher = better).
    top_n : list[dict[str, Any]]
        Top-N parameter combinations with their scores.
    in_sample_return : float
        In-sample (training) total return.
    out_sample_return : float
        Out-sample (validation) total return, if available.
    walk_forward_return : float
        Walk-forward total return, if available.
    parameter_count : int
        Total parameter combinations evaluated.
    benchmark_return : float
        Benchmark return for the same period.
    alpha : float
        Excess return vs benchmark.
    """

    strategy_name: str = ""
    symbol: str = ""
    score: float = 0.0
    top_n: list[dict[str, Any]] = Field(default_factory=list)
    in_sample_return: float = 0.0
    out_sample_return: float = 0.0
    walk_forward_return: float = 0.0
    parameter_count: int = 0
    benchmark_return: float = 0.0
    alpha: float = 0.0
    notes: list[str] = Field(default_factory=list)


__all__ = ["OptimizeResult"]
