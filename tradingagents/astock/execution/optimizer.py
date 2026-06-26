"""Strategy parameter optimizer — grid search over config space.

Usage
-----
>>> from tradingagents.astock.execution.optimizer import StrategyOptimizer
>>> from tradingagents.astock.execution.strategy_base import MACDTrendStrategy
>>> optimizer = StrategyOptimizer(strategy_cls=MACDTrendStrategy)
>>> params = {"fast_period": [8, 12, 16], "slow_period": [20, 26, 32]}
>>> results = optimizer.optimize("600519.SH", "2024-01-01", "2025-12-31", params)
>>> results[0]["params"]  # best parameter set
"""

from __future__ import annotations

import copy
import itertools
import logging
import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .backtest_engine import BacktestEngine
from .strategy_base import StrategyBase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GA constants
# ---------------------------------------------------------------------------

_DEFAULT_GA_CONFIG = {
    "pop_size": 20,
    "generations": 10,
    "tournament_size": 3,
    "crossover_rate": 0.8,
    "mutation_rate": 0.15,
    "elite_count": 2,
}

# ---------------------------------------------------------------------------
# Parameter type detection
# ---------------------------------------------------------------------------


@dataclass
class _ParamSpec:
    """Describes a single tunable parameter's type and bounds."""

    name: str
    dtype: type  # int or float
    min_val: float
    max_val: float
    discrete_values: list[Any] | None = None  # None = continuous range


def _infer_param_spec(name: str, candidates: list[Any]) -> _ParamSpec:
    """Infer whether *candidates* represent a discrete choice list or a range.

    - All values are the same → degenerate (min==max still works)
    - All values are int → integer parameter
    - Any value is float → float parameter
    """
    vals = [float(v) for v in candidates]
    is_int = all(isinstance(v, int) and not isinstance(v, bool) for v in candidates)
    return _ParamSpec(
        name=name,
        dtype=int if is_int else float,
        min_val=min(vals),
        max_val=max(vals),
        discrete_values=list(candidates) if len(candidates) <= 5 else None,
    )


def _random_value(spec: _ParamSpec) -> Any:
    """Sample a random valid value for *spec*."""
    if spec.discrete_values and len(spec.discrete_values) <= 5:
        return random.choice(spec.discrete_values)
    if spec.dtype == int:
        return random.randint(int(spec.min_val), int(spec.max_val))
    return round(random.uniform(spec.min_val, spec.max_val), 6)


# ---------------------------------------------------------------------------
# GA operators
# ---------------------------------------------------------------------------


def _sbx_crossover(
    p1: dict[str, Any], p2: dict[str, Any], specs: list[_ParamSpec], eta: float = 15.0
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Simulated Binary Crossover for real/integer parameters."""
    c1, c2 = {}, {}
    for spec in specs:
        v1, v2 = float(p1[spec.name]), float(p2[spec.name])
        if random.random() < 0.5 or spec.discrete_values:
            c1[spec.name] = p1[spec.name]
            c2[spec.name] = p2[spec.name]
            continue
        if abs(v1 - v2) < 1e-10:
            c1[spec.name], c2[spec.name] = p1[spec.name], p2[spec.name]
            continue
        u = random.random()
        beta = (
            (2.0 * u) ** (1.0 / (eta + 1.0))
            if u <= 0.5
            else (1.0 / (2.0 * (1.0 - u))) ** (1.0 / (eta + 1.0))
        )
        c1v = 0.5 * ((1.0 + beta) * v1 + (1.0 - beta) * v2)
        c2v = 0.5 * ((1.0 - beta) * v1 + (1.0 + beta) * v2)
        c1v = max(spec.min_val, min(spec.max_val, c1v))
        c2v = max(spec.min_val, min(spec.max_val, c2v))
        c1[spec.name] = int(c1v) if spec.dtype == int else round(c1v, 6)
        c2[spec.name] = int(c2v) if spec.dtype == int else round(c2v, 6)
    return c1, c2


def _polynomial_mutate(
    ind: dict[str, Any], specs: list[_ParamSpec], rate: float, eta: float = 20.0
) -> dict[str, Any]:
    """Polynomial mutation — respects integer/choice constraints."""
    child = dict(ind)
    for spec in specs:
        if random.random() > rate:
            continue
        # Choice param → reset to another random choice
        if spec.discrete_values and len(spec.discrete_values) <= 5:
            choices = [v for v in spec.discrete_values if v != ind[spec.name]]
            if choices:
                child[spec.name] = random.choice(choices)
            continue
        v = float(ind[spec.name])
        delta = min(v - spec.min_val, spec.max_val - v) / max(spec.max_val - spec.min_val, 1e-10)
        u = random.random()
        if u <= 0.5:
            delta_q = (2.0 * u + (1.0 - 2.0 * u) * (1.0 - delta) ** (eta + 1.0)) ** (
                1.0 / (eta + 1.0)
            ) - 1.0
        else:
            delta_q = 1.0 - (2.0 * (1.0 - u) + 2.0 * (u - 0.5) * (1.0 - delta) ** (eta + 1.0)) ** (
                1.0 / (eta + 1.0)
            )
        new_v = v + delta_q * (spec.max_val - spec.min_val)
        new_v = max(spec.min_val, min(spec.max_val, new_v))
        child[spec.name] = int(new_v) if spec.dtype == int else round(new_v, 6)
    return child

# ---------------------------------------------------------------------------
# Default search spaces for each strategy
# Int / float ranges: define which parameter values to try.
# Keys that are not listed keep their default from the strategy __init__.
# ---------------------------------------------------------------------------

DEFAULT_SEARCH_SPACES: dict[str, dict[str, list[Any]]] = {
    "MovingAverageTrend": {
        "fast_period": [5, 10, 15, 20],
        "slow_period": [20, 30, 50, 60],
    },
    "BullTrend": {
        "fast_ma": [5, 10],
        "mid_ma": [20, 30],
        "slow_ma": [60, 80],
        "volume_ratio": [1.0, 1.5, 2.0],
    },
    "ValueAverage": {
        "pe_low_pct": [20, 30, 40],
        "pe_high_pct": [60, 70, 80],
    },
    "MeanReversion": {
        "std_multiplier": [1.5, 2.0, 2.5, 3.0],
        "ma_period": [10, 20, 30],
    },
    "RSIRange": {
        "rsi_period": [7, 14, 21],
        "oversold": [20, 25, 30],
        "overbought": [70, 75, 80],
    },
    "DefensiveMomentum": {
        "roc_period": [10, 20, 30],
        "vol_threshold": [0.015, 0.02, 0.03],
    },
    "PutWrite": {
        "fast_ma": [5, 10],
        "mid_ma": [20, 30],
        "slow_ma": [60, 80],
    },
    "MACDTrend": {
        "fast_period": [8, 12, 16],
        "slow_period": [20, 26, 32],
        "signal_period": [5, 9, 14],
    },
    "BollingerBands": {
        "ma_period": [10, 20, 30],
        "num_std": [1.5, 2.0, 2.5, 3.0],
    },
    "GridTrading": {
        "grid_levels": [3, 5, 8],
        "grid_spacing": [0.02, 0.03, 0.05],
    },
    "MomentumRotation": {
        "n": [10, 20, 30],
        "k": [5, 10, 20],
        "l": [3, 5, 8],
    },
}

DEFAULT_STRATEGY_NAME_TO_CLASS: dict[str, type[StrategyBase]] = {}

# Lazy registry populated on first access


def _get_strategy_map() -> dict[str, type[StrategyBase]]:
    if DEFAULT_STRATEGY_NAME_TO_CLASS:
        return DEFAULT_STRATEGY_NAME_TO_CLASS
    from .strategy_base import (  # noqa: F401
        BollingerBandsReversionStrategy,
        BullTrendStrategy,
        DefensiveMomentumStrategy,
        GridTradingStrategy,
        MACDTrendStrategy,
        MeanReversionStrategy,
        MomentumRotationStrategy,
        MovingAverageTrendStrategy,
        PutWriteStrategy,
        RSIRangeStrategy,
        ValueAverageStrategy,
    )

    mapping = {
        "MovingAverageTrend": MovingAverageTrendStrategy,
        "BullTrend": BullTrendStrategy,
        "ValueAverage": ValueAverageStrategy,
        "MeanReversion": MeanReversionStrategy,
        "RSIRange": RSIRangeStrategy,
        "DefensiveMomentum": DefensiveMomentumStrategy,
        "PutWrite": PutWriteStrategy,
        "MACDTrend": MACDTrendStrategy,
        "BollingerBands": BollingerBandsReversionStrategy,
        "GridTrading": GridTradingStrategy,
        "MomentumRotation": MomentumRotationStrategy,
    }
    DEFAULT_STRATEGY_NAME_TO_CLASS.update(mapping)
    return DEFAULT_STRATEGY_NAME_TO_CLASS


def _get_default_search_space(name: str) -> dict[str, list[Any]]:
    """Return the default search space for *name*, or empty dict if unknown."""
    return dict(DEFAULT_SEARCH_SPACES.get(name, {}))


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _composite_score(metrics: dict[str, Any]) -> float:
    """Composite score in [-1, 1] for ranking parameter sets.

    Higher is better.  Combines Sharpe, return, drawdown penalty, and
    trade count bonus using a simple weighted formula.
    Treats None/NaN metrics as 0.
    """
    sharpe = metrics.get("sharpe_ratio", 0.0) or 0.0
    total_return = metrics.get("total_return", 0.0) or 0.0
    max_dd = metrics.get("max_drawdown", 0.0) or 0.0
    total_trades = metrics.get("total_trades", 0) or 0

    # Sharpe contribution (bounded)
    sharpe_score = max(min(sharpe / 3.0, 1.0), -1.0)

    # Return contribution (bounded)
    return_score = max(min(total_return * 2.0, 1.0), -1.0) if total_return > 0 else max(total_return, -1.0)

    # Drawdown penalty (0 → no penalty, 0.5+ → heavy penalty)
    dd_penalty = min(max_dd * 2.0, 1.0)

    # Trade count bonus (avoid zero-trade scenarios)
    trade_bonus = min(total_trades / 50.0, 0.2)

    score = (
        0.35 * sharpe_score
        + 0.30 * return_score
        - 0.25 * dd_penalty
        + 0.10 * trade_bonus
    )
    return round(score, 4)


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------


class StrategyOptimizer:
    """Grid-search parameter optimizer for backtest strategies.

    Parameters
    ----------
    strategy_cls : type[StrategyBase] or str
        Strategy class or registered name (e.g. ``"MACDTrend"``).
    engine : BacktestEngine or None
        Backtest engine instance.  Created fresh if omitted.
    rebalance_freq : str
        Rebalance frequency passed to ``BacktestEngine.run``.
    initial_cash : float
        Starting capital passed to ``BacktestEngine.run``.
    """

    def __init__(
        self,
        strategy_cls: type[StrategyBase] | str,
        engine: BacktestEngine | None = None,
        rebalance_freq: str = "M",
        initial_cash: float = 100000.0,
    ) -> None:
        if isinstance(strategy_cls, str):
            mapping = _get_strategy_map()
            resolved = mapping.get(strategy_cls)
            if resolved is None:
                raise ValueError(
                    f"Unknown strategy name {strategy_cls!r}. "
                    f"Available: {list(mapping)}"
                )
            strategy_cls = resolved
        self.strategy_cls: type[StrategyBase] = strategy_cls
        self.engine = engine or BacktestEngine()
        self.rebalance_freq = rebalance_freq
        self.initial_cash = initial_cash

    def optimize(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        param_grid: dict[str, list[Any]] | None = None,
        *,
        top_n: int = 5,
        metric: str = "composite",
        method: str = "grid",
        ga_config: dict[str, Any] | None = None,
        progress_callback: Any = None,
    ) -> list[dict[str, Any]]:
        """Run parameter search over *param_grid* and return top-N results.

        Parameters
        ----------
        symbol : str
            A-share symbol.
        start_date, end_date : str
            Backtest date range.
        param_grid : dict or None
            Parameter search space: ``{param_name: [values]``}.
            Uses ``DEFAULT_SEARCH_SPACES`` when ``None``.
        top_n : int
            Number of top results to return (default 5).
        metric : str
            Scoring metric.  ``"composite"`` (default) uses ``_composite_score``.
            ``"sharpe"``, ``"total_return"`` also accepted.
        method : str
            ``"grid"`` (default) — exhaustive Cartesian product.
            ``"genetic"`` — evolutionary search (GA) over continuous/discrete space.
        ga_config : dict or None
            GA hyper-parameters when ``method="genetic"``:
            ``pop_size`` (20), ``generations`` (10), ``tournament_size`` (3),
            ``crossover_rate`` (0.8), ``mutation_rate`` (0.15), ``elite_count`` (2).
        progress_callback : callable or None
            ``fn(current, total, params)`` called after each trial.

        Returns
        -------
        list[dict]
            Each entry: ``{"rank", "params", "metrics", "score"}``,
            sorted best-first.
        """
        if param_grid is None:
            name = self.strategy_cls.__name__.replace("Strategy", "")
            param_grid = _get_default_search_space(name)

        if not param_grid:
            result = self._run_trial(symbol, start_date, end_date, {})
            if result is None:
                return []
            return [{"rank": 1, "params": {}, **result}]

        if method == "genetic":
            cfg = dict(_DEFAULT_GA_CONFIG)
            if ga_config:
                cfg.update(ga_config)
            return self._genetic_optimize(
                symbol, start_date, end_date, param_grid,
                top_n=top_n, metric=metric, ga_config=cfg,
                progress_callback=progress_callback,
            )

        # -- Grid search (default) --
        keys = list(param_grid.keys())
        value_lists = [param_grid[k] for k in keys]
        combinations = list(itertools.product(*value_lists))
        total = len(combinations)

        results: list[dict[str, Any]] = []
        for idx, combo in enumerate(combinations):
            params = dict(zip(keys, combo))
            trial_result = self._run_trial(symbol, start_date, end_date, params)
            if progress_callback:
                progress_callback(idx + 1, total, params)
            if trial_result is None:
                continue
            trial_result["params"] = params
            trial_result["score"] = _composite_score(trial_result["metrics"])
            results.append(trial_result)

        if not results:
            return []

        # Sort by score descending
        results.sort(key=lambda r: r["score"], reverse=True)

        # Rank and return top-N
        for i, r in enumerate(results[:top_n]):
            r["rank"] = i + 1

        return results[:top_n]

    def _genetic_optimize(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        param_grid: dict[str, list[Any]],
        *,
        top_n: int,
        metric: str,
        ga_config: dict[str, Any],
        progress_callback: Any,
    ) -> list[dict[str, Any]]:
        """Genetic algorithm search over continuous/discrete parameter space.

        Uses tournament selection, SBX crossover, polynomial mutation,
        and elitism.  Evaluates ``pop_size * generations`` trials
        (compared to potentially exponential grid combinations).
        """
        specs = [_infer_param_spec(k, v) for k, v in param_grid.items()]
        pop_size = int(ga_config.get("pop_size", 20))
        generations = int(ga_config.get("generations", 10))
        tournament_size = int(ga_config.get("tournament_size", 3))
        crossover_rate = float(ga_config.get("crossover_rate", 0.8))
        mutation_rate = float(ga_config.get("mutation_rate", 0.15))
        elite_count = int(ga_config.get("elite_count", 2))

        # Population: list of (params, result_or_None)
        population: list[tuple[dict[str, Any], dict[str, Any] | None]] = []

        # Seed with default params first (ensures baseline exists)
        default_trial = self._run_trial(symbol, start_date, end_date, {})
        if default_trial is not None:
            default_trial["params"] = {}
            default_trial["score"] = _composite_score(default_trial["metrics"])
            population.append(({}, default_trial))

        def _evaluate(
            params: dict[str, Any], idx: int, total: int,
        ) -> dict[str, Any] | None:
            trial = self._run_trial(symbol, start_date, end_date, params)
            if progress_callback:
                progress_callback(idx + 1, total, params)
            if trial is None:
                return None
            trial["params"] = params
            trial["score"] = _composite_score(trial["metrics"])
            return trial

        def _random_ind() -> dict[str, Any]:
            return {s.name: _random_value(s) for s in specs}

        def _tournament(
            pop: list[tuple[dict[str, Any], dict[str, Any]]],
            k: int,
        ) -> dict[str, Any]:
            candidates = random.sample(pop, min(k, len(pop)))
            best = max(candidates, key=lambda x: x[1]["score"])
            return best[0]

        # Fill population with random individuals
        total_evals = elite_count + pop_size + generations * pop_size
        eval_counter = [0]

        while len(population) < pop_size:
            params = _random_ind()
            trial = _evaluate(params, eval_counter[0], total_evals)
            eval_counter[0] += 1
            if trial is not None:
                population.append((params, trial))

        if not population:
            return []

        # Evolution loop
        best_overall: dict[str, Any] | None = None
        for gen in range(generations):
            # Filter to evaluated individuals only
            valid = [(p, r) for p, r in population if r is not None]
            if not valid:
                break

            # Track best
            current_best = max(valid, key=lambda x: x[1]["score"])
            if best_overall is None or current_best[1]["score"] > best_overall["score"]:
                best_overall = dict(current_best[1])

            # Elitism
            valid.sort(key=lambda x: x[1]["score"], reverse=True)
            next_pop: list[tuple[dict[str, Any], dict[str, Any] | None]] = valid[:elite_count]

            # Generate offspring
            while len(next_pop) < pop_size:
                p1_params = _tournament(valid, tournament_size)
                p2_params = _tournament(valid, tournament_size)

                if random.random() < crossover_rate:
                    c1, c2 = _sbx_crossover(p1_params, p2_params, specs)
                else:
                    c1, c2 = dict(p1_params), dict(p2_params)

                c1 = _polynomial_mutate(c1, specs, mutation_rate)
                c2 = _polynomial_mutate(c2, specs, mutation_rate)

                for child_params in (c1, c2):
                    if len(next_pop) >= pop_size:
                        break
                    trial = _evaluate(child_params, eval_counter[0], total_evals)
                    eval_counter[0] += 1
                    if trial is not None:
                        next_pop.append((child_params, trial))

            population = next_pop
            logger.debug(
                "GA gen %d/%d — pop=%d best_score=%.4f",
                gen + 1, generations, len(population),
                best_overall["score"] if best_overall else float("-inf"),
            )

        # Collect all evaluated individuals
        all_results = [r for _, r in population if r is not None]
        if best_overall:
            all_results.append(best_overall)

        if not all_results:
            return []

        all_results.sort(key=lambda r: r["score"], reverse=True)
        for i, r in enumerate(all_results[:top_n]):
            r["rank"] = i + 1
        return all_results[:top_n]

    def _run_trial(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        params: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Run a single backtest trial with *params*."""
        try:
            strategy = self.strategy_cls(params)
            result = self.engine.run(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                strategy=strategy,
                rebalance_freq=self.rebalance_freq,
                initial_cash=self.initial_cash,
            )
            return {
                "metrics": {
                    "total_return": result.total_return,
                    "annualized_return": result.annualized_return,
                    "sharpe_ratio": result.sharpe_ratio,
                    "max_drawdown": result.max_drawdown,
                    "win_rate": result.win_rate,
                    "total_trades": result.total_trades,
                },
            }
        except Exception as exc:
            logger.debug("Trial failed for params %s: %s", params, exc)
            return None


def optimize_strategy(
    strategy_name: str,
    symbol: str,
    start_date: str,
    end_date: str,
    param_grid: dict[str, list[Any]] | None = None,
    *,
    top_n: int = 5,
    engine: BacktestEngine | None = None,
) -> list[dict[str, Any]]:
    """Convenience wrapper — create an optimizer and run it in one call."""
    optimizer = StrategyOptimizer(strategy_name, engine=engine)
    return optimizer.optimize(symbol, start_date, end_date, param_grid, top_n=top_n)


# ---------------------------------------------------------------------------
# Walk-Forward Analysis
# ---------------------------------------------------------------------------


@dataclass
class WFWindow:
    """单次滚动窗口结果."""

    window_idx: int
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    best_params: dict[str, Any]
    train_score: float
    val_score: float
    val_metrics: dict[str, Any] = field(default_factory=dict)


class WalkForwardAnalyzer:
    """Walk-Forward Analysis（滚动窗口验证）— 防过拟合核心工具。

    .. code-block:: python

        wfa = WalkForwardAnalyzer("MACDTrend")
        results = wfa.run("600519.SH", "2020-01-01", "2025-12-31",
            param_grid={"fast_period": [8, 12, 16], "slow_period": [20, 26, 32]},
            train_years=2, val_months=6)

    Parameters
    ----------
    strategy_cls : type[StrategyBase] or str
        策略类或注册名。
    engine : BacktestEngine or None
        回测引擎。默认新建（mock 数据）。
    rebalance_freq : str
        重平衡频率（默认 ``\"M\"``）。
    initial_cash : float
        初始资金（默认 100000）。
    """

    def __init__(
        self,
        strategy_cls: type[StrategyBase] | str,
        engine: BacktestEngine | None = None,
        rebalance_freq: str = "M",
        initial_cash: float = 100000.0,
    ) -> None:
        if isinstance(strategy_cls, str):
            mapping = _get_strategy_map()
            resolved = mapping.get(strategy_cls)
            if resolved is None:
                raise ValueError(
                    f"Unknown strategy name {strategy_cls!r}. "
                    f"Available: {list(mapping)}"
                )
            strategy_cls = resolved
        self.strategy_cls: type[StrategyBase] = strategy_cls
        self.engine = engine or BacktestEngine()
        self.rebalance_freq = rebalance_freq
        self.initial_cash = initial_cash

    def run(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        param_grid: dict[str, list[Any]] | None = None,
        *,
        train_years: float = 2.0,
        val_months: int = 6,
        window_mode: str = "rolling",
        top_n: int = 1,
        progress_callback: Any = None,
    ) -> list[WFWindow]:
        """执行 Walk-Forward Analysis。

        Parameters
        ----------
        symbol, start_date, end_date, param_grid :
            同 ``StrategyOptimizer.optimize``。
        train_years : float
            训练窗口长度（年，默认 2）。
        val_months : int
            验证窗口长度（月，默认 6）。
        window_mode : str
            ``\"rolling\"``（等宽滚动，默认）或 ``\"expanding\"``（扩展窗口）。
        top_n : int
            每窗口保留的最优参数数（默认 1）。
        progress_callback : callable or None
            ``fn(current, total, window_info)``。

        Returns
        -------
        list of WFWindow
            每窗口的 train/val 结果，按时间排序。
        """
        # ── 1. 获取交易日历 ──
        df = self.engine._fetch_data(symbol, start_date, end_date)
        if df.empty:
            return []

        trading_dates = df.index.sort_values()
        total_days = len(trading_dates)

        # ── 2. 计算窗口 ──
        train_days = int(train_years * 252)
        val_days = int(val_months * 21)

        if train_days + val_days > total_days:
            logger.warning(
                "train=%dd + val=%dd > total=%dd — reducing train window",
                train_days, val_days, total_days,
            )
            train_days = max(total_days - val_days, val_days)

        windows: list[tuple[int, int, int, int]] = []
        step = val_days
        offset = 0
        while offset + train_days + val_days <= total_days:
            t_start = offset
            t_end = offset + train_days - 1
            v_start = t_end + 1
            v_end = v_start + val_days - 1
            windows.append((t_start, t_end, v_start, v_end))
            if window_mode == "expanding":
                offset = 0
                train_days += val_days  # expand training window
            else:
                offset += step

        if not windows:
            return []

        # ── 3. 逐窗口执行 ──
        results: list[WFWindow] = []
        for idx, (ts, te, vs, ve) in enumerate(windows):
            train_start = str(trading_dates[ts].date())
            train_end = str(trading_dates[min(te, total_days - 1)].date())
            val_start = str(trading_dates[min(vs, total_days - 1)].date())
            val_end = str(trading_dates[min(ve, total_days - 1)].date())

            # Optimize on training window
            optimizer = StrategyOptimizer(
                self.strategy_cls, engine=self.engine,
                rebalance_freq=self.rebalance_freq,
                initial_cash=self.initial_cash,
            )
            opt_results = optimizer.optimize(
                symbol, train_start, train_end,
                param_grid=param_grid, top_n=top_n,
                progress_callback=progress_callback,
            )

            if not opt_results:
                continue

            best_params = dict(opt_results[0]["params"])
            train_score = float(opt_results[0]["score"])

            # Validate on out-of-sample window
            strategy = self.strategy_cls(best_params)
            val_result = self.engine.run(
                symbol, val_start, val_end, strategy,
                rebalance_freq=self.rebalance_freq,
                initial_cash=self.initial_cash,
            )

            val_metrics = {
                "total_return": val_result.total_return,
                "annualized_return": val_result.annualized_return,
                "sharpe_ratio": val_result.sharpe_ratio,
                "max_drawdown": val_result.max_drawdown,
                "win_rate": val_result.win_rate,
                "total_trades": val_result.total_trades,
            }
            val_score = _composite_score(val_metrics)

            results.append(WFWindow(
                window_idx=idx,
                train_start=train_start,
                train_end=train_end,
                val_start=val_start,
                val_end=val_end,
                best_params=best_params,
                train_score=train_score,
                val_score=val_score,
                val_metrics=val_metrics,
            ))

            if progress_callback:
                progress_callback(idx + 1, len(windows), {
                    "window": idx,
                    "train_score": train_score,
                    "val_score": val_score,
                })

        return results

    def summarize(self, results: list[WFWindow]) -> dict[str, Any]:
        """汇总 Walk-Forward 结果。

        Returns
        -------
        dict
            ``num_windows``, ``avg_train_score``, ``avg_val_score``,
            ``overfit_gap``（train - val，越大越过拟合）,
            ``param_stability``（各参数的标准差，越小越稳定）.
        """
        if not results:
            return {
                "num_windows": 0,
                "avg_train_score": 0.0,
                "avg_val_score": 0.0,
                "overfit_gap": 0.0,
                "param_stability": {},
            }

        train_scores = [r.train_score for r in results]
        val_scores = [r.val_score for r in results]

        avg_train = float(np.mean(train_scores))
        avg_val = float(np.mean(val_scores))

        # Param stability: std across windows for each param
        param_stability: dict[str, float] = {}
        if results:
            all_params = results[0].best_params.keys()
            for key in all_params:
                values = []
                for r in results:
                    v = r.best_params.get(key)
                    if isinstance(v, (int, float)):
                        values.append(float(v))
                if values:
                    param_stability[key] = round(float(np.std(values)), 4)

        return {
            "num_windows": len(results),
            "avg_train_score": round(avg_train, 4),
            "avg_val_score": round(avg_val, 4),
            "overfit_gap": round(avg_train - avg_val, 4),
            "param_stability": param_stability,
        }
