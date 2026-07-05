"""Walk-Forward Analysis (滚动窗口验证) — anti-overfitting core tool."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..backtest_engine import BacktestEngine
from ..strategy_base import StrategyBase
from .config import _composite_score, _get_strategy_map

logger = logging.getLogger(__name__)


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
        重平衡频率（默认 ``"M"``）。
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
            ``"rolling"``（等宽滚动，默认）或 ``"expanding"``（扩展窗口）。
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
            from .optimizer import StrategyOptimizer

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

        avg_train = float(sum(train_scores) / len(train_scores))
        avg_val = float(sum(val_scores) / len(val_scores))

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
