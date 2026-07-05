"""DefensiveMomentumStrategy — 防御性动量策略 — 熊市策略。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import StrategyBase


class DefensiveMomentumStrategy(StrategyBase):
    """防御性动量策略 — 熊市策略。

    在市场下行时寻找相对强势的标的。
    使用价格动量（ROC）和低波动率筛选，信号偏保守。

    Config keys (all optional):
        roc_period    : int    ROC 计算窗口 (default ``20``)
        vol_period    : int    波动率计算窗口 (default ``20``)
        vol_threshold : float  日波动率上限 (default ``0.02``, 即 2%)
        price_col     : str    价格列名 (default ``\"close\"``)

    Signal logic
        - ROC > 0 **且** 波动率 ≤ vol_threshold → ``+1`` (买入 — 强势且低波动)
        - ROC < 0 → ``-1`` (卖出 — 动量转负)
        - 其他 → ``0`` (持有)
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.roc_period: int = int(self.config.get("roc_period", 20))
        self.vol_period: int = int(self.config.get("vol_period", 20))
        self.vol_threshold: float = float(self.config.get("vol_threshold", 0.02))
        self.price_col: str = str(self.config.get("price_col", "close"))

        if self.roc_period < 1:
            raise ValueError(f"roc_period must be >= 1, got {self.roc_period}")

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        if self.price_col not in data.columns:
            raise KeyError(
                f"Column '{self.price_col}' not found; available: {list(data.columns)}"
            )

        prices = data[self.price_col]

        # Rate of Change
        roc = prices.pct_change(periods=self.roc_period)

        # Daily returns for volatility
        daily_ret = prices.pct_change()
        volatility = daily_ret.rolling(window=self.vol_period).std(ddof=0)

        signals = pd.Series(0, index=data.index, dtype=int)

        valid = roc.notna() & volatility.notna()

        # Buy: positive momentum + low volatility
        buy_mask = valid & (roc > 0) & (volatility <= self.vol_threshold)
        # Sell: negative momentum
        sell_mask = valid & (roc < 0)

        signals[buy_mask] = 1
        signals[sell_mask] = -1

        signals = signals.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)
        return signals
