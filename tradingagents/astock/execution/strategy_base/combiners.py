"""StockFlow — multi-strategy signal cascade combiner."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import StrategyBase


_SIGNAL_MODES = frozenset({"and", "or", "majority", "cascade"})


class StockFlow(StrategyBase):
    """图执行链 — 多策略信号级联组合。

    按 *order* 依次执行多个子策略，用 *mode* 组合最终信号。
    子策略可以是 10 个已注册策略中的任意组合。

    Config keys:
        flows : list[dict]
            策略流定义。每个元素::

                {
                    "name": "MovingAverageTrend",     # 策略名
                    "config": {"fast_period": 5},      # 参数（可选）
                    "order": 0,                        # 执行顺序（必填）
                    "weight": 1.0,                     # 信号权重（可选，默认 1.0）
                }

        mode : str
            组合模式:
            - ``"and"`` — 全票一致（全部为1→1, 全部为-1→-1, 否则→0）
            - ``"or"`` — 任一触发（有1→1, 有-1→-1, 冲突时-1优先）
            - ``"majority"`` — 多数投票（比权重累加）
            - ``"cascade"`` — 级联（按 order 执行，第一个非零者胜出）

    Example::

        StockFlow({
            "flows": [
                {"name": "MovingAverageTrend", "order": 0, "weight": 2.0},
                {"name": "RSIRange", "order": 1, "weight": 1.0},
            ],
            "mode": "majority",
        })
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        raw_flows: list[dict] = list(self.config.get("flows", []))
        if not raw_flows:
            raise ValueError("StockFlow requires at least one flow in 'flows'")

        self.mode: str = str(self.config.get("mode", "and")).lower()
        if self.mode not in _SIGNAL_MODES:
            raise ValueError(
                f"Unknown mode {self.mode!r}. Choose from: {sorted(_SIGNAL_MODES)}"
            )

        # Build sub-strategies
        self.flows: list[dict] = sorted(raw_flows, key=lambda f: f.get("order", 0))
        self._strategies: list[tuple[str, StrategyBase, float]] = []

        for f in self.flows:
            name = str(f["name"])
            sub_config = dict(f.get("config", {}))
            weight = float(f.get("weight", 1.0))
            cls = self._resolve_strategy(name)
            strat = cls(sub_config)
            self._strategies.append((name, strat, weight))

    @staticmethod
    def _resolve_strategy(name: str) -> type[StrategyBase]:
        """Lazy-resolve a strategy name to its class."""
        from tradingagents.astock.execution.strategy_base import (
            BollingerBandsReversionStrategy,
            BullTrendStrategy,
            DefensiveMomentumStrategy,
            GridTradingStrategy,
            MACDTrendStrategy,
            MeanReversionStrategy,
            MovingAverageTrendStrategy,
            PutWriteStrategy,
            RSIRangeStrategy,
            ValueAverageStrategy,
        )

        _STRATEGY_CLASSES: dict[str, type[StrategyBase]] = {
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
        }
        cls = _STRATEGY_CLASSES.get(name)
        if cls is None:
            raise ValueError(
                f"Unknown strategy {name!r}. Available: {list(_STRATEGY_CLASSES)}"
            )
        return cls

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Run all sub-strategies and combine signals via *mode*."""
        signals: dict[str, pd.Series] = {}
        for name, strat, weight in self._strategies:
            try:
                sig = strat.generate_signals(data)
                signals[name] = sig * weight  # weighted signal ∈ [-w, 0, w]
            except Exception:
                signals[name] = pd.Series(0, index=data.index, dtype=float)

        if not signals:
            return pd.Series(0, index=data.index, dtype=int)

        # Build signal matrix
        sig_df = pd.DataFrame(signals).replace([np.inf, -np.inf], np.nan).fillna(0.0)

        if self.mode == "and":
            # All positive → 1, all negative → -1, mixed → 0
            all_pos = (sig_df > 0).all(axis=1)
            all_neg = (sig_df < 0).all(axis=1)
            combined = pd.Series(0, index=data.index, dtype=int)
            combined[all_pos] = 1
            combined[all_neg] = -1

        elif self.mode == "or":
            # Any positive with no negative → 1, any negative with no positive → -1
            has_pos = (sig_df > 0).any(axis=1)
            has_neg = (sig_df < 0).any(axis=1)
            combined = pd.Series(0, index=data.index, dtype=int)
            combined[has_neg & ~has_pos] = -1
            combined[has_pos & ~has_neg] = 1
            # Conflict → -1 (defensive)

        elif self.mode == "majority":
            # Weighted sum, threshold at 0 (greater weight sum carries)
            total = sig_df.sum(axis=1)
            combined = pd.Series(0, index=data.index, dtype=int)
            combined[total > 0] = 1
            combined[total < 0] = -1

        else:  # cascade
            # First non-zero signal wins (per date)
            combined = pd.Series(0, index=data.index, dtype=int)
            for name, _, _ in self._strategies:
                sig = signals[name]
                mask = (combined == 0) & (sig != 0)
                combined[mask] = np.sign(sig[mask]).astype(int)

        return combined
