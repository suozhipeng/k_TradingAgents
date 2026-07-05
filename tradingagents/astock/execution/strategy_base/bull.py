"""BullTrendStrategy — 趋势跟随 + 均线多头排列 — 牛市策略。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import StrategyBase


class BullTrendStrategy(StrategyBase):
    """趋势跟随 + 均线多头排列 — 牛市策略。

    当短期、中期、长期均线呈多头排列（MA20 > MA60 且 MA5 > MA20）
    且成交量放大确认时产生买入信号。

    Config keys (all optional):
        fast_ma : int    快线窗口 (default ``5``)
        mid_ma  : int    中线窗口 (default ``20``)
        slow_ma : int    慢线窗口 (default ``60``)
        volume_ratio : float  成交量放大倍数阈值 (default ``1.5``)
        price_col : str       价格列名 (default ``\"close\"``)
        volume_col : str      成交量列名 (default ``\"volume\"``)

    Signal logic
        - MA20 > MA60 **且** MA5 > MA20 **且** 成交量 > 均值×volume_ratio → ``+1`` (买入)
        - MA5 < MA20 或 MA20 < MA60 → ``-1`` (卖出)
        - 其他 → ``0`` (持有)
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.fast_ma: int = int(self.config.get("fast_ma", 5))
        self.mid_ma: int = int(self.config.get("mid_ma", 20))
        self.slow_ma: int = int(self.config.get("slow_ma", 60))
        self.volume_ratio: float = float(self.config.get("volume_ratio", 1.5))
        self.price_col: str = str(self.config.get("price_col", "close"))
        self.volume_col: str = str(self.config.get("volume_col", "volume"))

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

        # Volume confirmation (if volume column exists)
        vol_confirmed = pd.Series(True, index=data.index)
        if self.volume_col in data.columns:
            vol_ma = data[self.volume_col].rolling(window=self.mid_ma).mean()
            vol_confirmed = data[self.volume_col] > vol_ma * self.volume_ratio
            # Before volume MA stabilises, default to confirmed
            vol_confirmed = vol_confirmed.fillna(True)

        # Valid mask: all three MAs are non-NaN
        valid = ma5.notna() & ma20.notna() & ma60.notna()

        # Buy: 多头排列 (MA20 > MA60 and MA5 > MA20) + volume confirmation
        buy_mask = valid & (ma20 > ma60) & (ma5 > ma20) & vol_confirmed
        signals[buy_mask] = 1

        # Sell: 空头排列 (MA5 < MA20 or MA20 < MA60)
        sell_mask = valid & ((ma5 < ma20) | (ma20 < ma60))
        signals[sell_mask] = -1

        signals = signals.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)
        return signals
