"""ValueAverageStrategy — 价值平均 / 成本平均策略 — 牛市策略。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import StrategyBase


class ValueAverageStrategy(StrategyBase):
    """价值平均 / 成本平均策略 — 牛市策略。

    当价格低于估值区间下限时买入，高于上限时卖出。
    使用 PE/PB 历史分位数判断估值区间（模拟）。

    Config keys (all optional):
        pe_low_pct  : int  低估分位 (default ``30``)
        pe_high_pct : int  高估分位 (default ``70``)
        price_col   : str  价格列名 (default ``\"close\"``)

    Signal logic
        - 价格低于估值区间下限 → ``+1`` (买入)
        - 价格高于估值区间上限 → ``-1`` (卖出)
        - 区间内 → ``0`` (持有)

    Note
    ----
    由于 K-line 数据不含 PE/PB，这里用价格相对于历史价格的
    百分位来模拟估值区间。
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.pe_low_pct: int = int(self.config.get("pe_low_pct", 30))
        self.pe_high_pct: int = int(self.config.get("pe_high_pct", 70))
        self.price_col: str = str(self.config.get("price_col", "close"))

        if not (0 < self.pe_low_pct < self.pe_high_pct < 100):
            raise ValueError(
                f"Expected 0 < pe_low_pct ({self.pe_low_pct}) < "
                f"pe_high_pct ({self.pe_high_pct}) < 100"
            )

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        if self.price_col not in data.columns:
            raise KeyError(
                f"Column '{self.price_col}' not found; available: {list(data.columns)}"
            )

        prices = data[self.price_col]
        # Use expanding window to simulate historical percentile
        low_threshold = prices.expanding().quantile(self.pe_low_pct / 100.0)
        high_threshold = prices.expanding().quantile(self.pe_high_pct / 100.0)

        signals = pd.Series(0, index=data.index, dtype=int)

        # Need at least some data for percentiles to stabilise
        sufficient = prices.expanding().count() >= 20

        buy_mask = sufficient & (prices <= low_threshold)
        sell_mask = sufficient & (prices >= high_threshold)

        signals[buy_mask] = 1
        signals[sell_mask] = -1

        signals = signals.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)
        return signals
