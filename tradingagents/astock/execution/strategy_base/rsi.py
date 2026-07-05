"""RSIRangeStrategy — RSI 区间交易策略 — 震荡策略。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import StrategyBase


class RSIRangeStrategy(StrategyBase):
    """RSI 区间交易策略 — 震荡策略。

    使用 RSI 指标判断超买超卖区间。

    Config keys (all optional):
        rsi_period  : int  RSI 计算窗口 (default ``14``)
        oversold    : int  超卖阈值 (default ``30``)
        overbought  : int  超买阈值 (default ``70``)
        price_col   : str  价格列名 (default ``\"close\"``)

    Signal logic
        - RSI < oversold → ``+1`` (买入)
        - RSI > overbought → ``-1`` (卖出)
        - 其他 → ``0`` (持有)
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.rsi_period: int = int(self.config.get("rsi_period", 14))
        self.oversold: int = int(self.config.get("oversold", 30))
        self.overbought: int = int(self.config.get("overbought", 70))
        self.price_col: str = str(self.config.get("price_col", "close"))

        if self.rsi_period < 1:
            raise ValueError(f"rsi_period must be >= 1, got {self.rsi_period}")
        if not (0 < self.oversold < self.overbought < 100):
            raise ValueError(
                f"Expected 0 < oversold ({self.oversold}) < "
                f"overbought ({self.overbought}) < 100"
            )

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        if self.price_col not in data.columns:
            raise KeyError(
                f"Column '{self.price_col}' not found; available: {list(data.columns)}"
            )

        prices = data[self.price_col]

        # RSI calculation
        delta = prices.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)

        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()

        # Handle extreme cases: infinite RS when no losses, zero RS when no gains
        rs = avg_gain / avg_loss.replace(0, float("nan"))
        rsi = 100.0 - (100.0 / (1.0 + rs))

        # Only override computed RSI where we have data (not during warmup)
        has_data = avg_gain.notna() & avg_loss.notna()
        # When avg_loss is 0 and avg_gain > 0 → RSI = 100 (overbought)
        rsi[has_data & (avg_loss == 0) & (avg_gain > 0)] = 100.0
        # When both are 0 (flat prices) → RSI = 50 (neutral)
        rsi[has_data & (avg_gain == 0) & (avg_loss == 0)] = 50.0

        signals = pd.Series(0, index=data.index, dtype=int)

        valid = rsi.notna()
        buy_mask = valid & (rsi < self.oversold)
        sell_mask = valid & (rsi > self.overbought)

        signals[buy_mask] = 1
        signals[sell_mask] = -1

        signals = signals.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)
        return signals
