"""StrategyOptimizer — grid search and genetic-algorithm parameter optimization."""

from __future__ import annotations

import copy
import itertools
import logging
import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..backtest_engine import BacktestEngine
from ..strategy_base import StrategyBase
from .config import _composite_score, _get_default_search_space, _get_strategy_map

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
