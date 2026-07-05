"""MeanReversionStrategy — 均值回归策略 — 震荡策略。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import StrategyBase


class MeanReversionStrategy(StrategyBase):
    """均值回归策略 — 震荡策略。

    当价格偏离移动平均线超过 N 个标准差时产生反向信号。

    Config keys (all optional):
        std_multiplier : float  标准差倍数阈值 (default ``2.0``)
        ma_period      : int    移动平均窗口 (default ``20``)
        price_col      : str    价格列名 (default ``\"close\"``)

    Signal logic
        - 价格 < MA - N×σ → ``+1`` (买入，超卖反弹)
        - 价格 > MA + N×σ → ``-1`` (卖出，超买回调)
        - 其他 → ``0`` (持有)
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.std_multiplier: float = float(self.config.get("std_multiplier", 2.0))
        self.ma_period: int = int(self.config.get("ma_period", 20))
        self.price_col: str = str(self.config.get("price_col", "close"))

        if self.ma_period < 2:
            raise ValueError(f"ma_period must be >= 2, got {self.ma_period}")

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        if self.price_col not in data.columns:
            raise KeyError(
                f"Column '{self.price_col}' not found; available: {list(data.columns)}"
            )

        prices = data[self.price_col]
        ma = prices.rolling(window=self.ma_period).mean()
        std = prices.rolling(window=self.ma_period).std(ddof=0)

        signals = pd.Series(0, index=data.index, dtype=int)

        valid = ma.notna() & std.notna()

        # Oversold: price far below MA → buy signal
        buy_mask = valid & (prices < ma - self.std_multiplier * std)
        # Overbought: price far above MA → sell signal
        sell_mask = valid & (prices > ma + self.std_multiplier * std)

        signals[buy_mask] = 1
        signals[sell_mask] = -1

        signals = signals.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)
        return signals
