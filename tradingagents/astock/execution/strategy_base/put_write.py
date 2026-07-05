"""PutWriteStrategy — Put Write（类空头对冲）策略 — 熊市策略。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import StrategyBase


class PutWriteStrategy(StrategyBase):
    """Put Write（类空头对冲）策略 — 熊市策略。

    当短中长期均线呈空头排列时，严格退出仓位。
    仅在 MA5 < MA20 且 MA20 < MA60 时卖出（不持有多头仓位）。

    Config keys (all optional):
        fast_ma   : int  快线窗口 (default ``5``)
        mid_ma    : int  中线窗口 (default ``20``)
        slow_ma   : int  慢线窗口 (default ``60``)
        price_col : str  价格列名 (default ``\"close\"``)

    Signal logic
        - MA5 < MA20 **且** MA20 < MA60 → ``-1`` (卖出/不持仓)
        - 其他 → ``0`` (持有)
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.fast_ma: int = int(self.config.get("fast_ma", 5))
        self.mid_ma: int = int(self.config.get("mid_ma", 20))
        self.slow_ma: int = int(self.config.get("slow_ma", 60))
        self.price_col: str = str(self.config.get("price_col", "close"))

        if not (self.fast_ma < self.mid_ma < self.slow_ma):
            raise ValueError(
                f"Expected fast_ma ({self.fast_ma}) < mid_ma ({self.mid_ma}) "
                f"< slow_ma ({self.slow_ma})"
            )

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        if self.price_col not in data.columns:
            raise KeyError(
                f"Column '{self.price_col}' not found; available: {list(data.columns)}"
            )

        prices = data[self.price_col]
        ma5 = prices.rolling(window=self.fast_ma).mean()
        ma20 = prices.rolling(window=self.mid_ma).mean()
        ma60 = prices.rolling(window=self.slow_ma).mean()

        signals = pd.Series(0, index=data.index, dtype=int)

        valid = ma5.notna() & ma20.notna() & ma60.notna()

        # Sell/defensive: 空头排列 (MA5 < MA20 < MA60)
        sell_mask = valid & (ma5 < ma20) & (ma20 < ma60)
        signals[sell_mask] = -1

        signals = signals.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)
        return signals
