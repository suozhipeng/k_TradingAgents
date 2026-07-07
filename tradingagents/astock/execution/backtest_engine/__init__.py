from .models import BacktestDataAssumption, BacktestResult
from .engine import BacktestEngine
from .facade import run_backtest_via_facade

# Prefer this name for callers migrating away from ``modules.backtest_engine``.
run_backtest_pipeline = run_backtest_via_facade


def __getattr__(name: str):
    """Lazily expose legacy parameter helpers via the new package path."""
    if name in {"PipelineParams", "create_strategy", "BacktestMetrics"}:
        from modules.backtest_engine import BacktestMetrics, PipelineParams, create_strategy

        return {
            "BacktestMetrics": BacktestMetrics,
            "PipelineParams": PipelineParams,
            "create_strategy": create_strategy,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BacktestEngine",
    "BacktestDataAssumption",
    "BacktestMetrics",
    "BacktestResult",
    "PipelineParams",
    "create_strategy",
    "run_backtest_via_facade",
    "run_backtest_pipeline",
]
