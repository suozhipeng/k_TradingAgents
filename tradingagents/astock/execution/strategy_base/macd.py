"""MACDTrendStrategy — MACD 趋势跟踪策略 — 趋势策略。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import StrategyBase


class MACDTrendStrategy(StrategyBase):
    """MACD 趋势跟踪策略 — 趋势策略。

    使用 MACD（指数平滑移动平均线）的金叉/死叉判断趋势方向。

    Config keys (all optional):
        fast_period   : int  快线EMA窗口 (default ``12``)
        slow_period   : int  慢线EMA窗口 (default ``26``)
        signal_period : int  信号线窗口 (default ``9``)
        price_col     : str  价格列名 (default ``"close"``)

    Signal logic
        - MACD 金叉（MACD 上穿信号线） → ``+1`` (买入)
        - MACD 死叉（MACD 下穿信号线） → ``-1`` (卖出)
        - 其他 → ``0`` (持有)
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.fast_period: int = int(self.config.get("fast_period", 12))
        self.slow_period: int = int(self.config.get("slow_period", 26))
        self.signal_period: int = int(self.config.get("signal_period", 9))
        self.price_col: str = str(self.config.get("price_col", "close"))

        if self.fast_period >= self.slow_period:
            raise ValueError(
                f"fast_period ({self.fast_period}) must be < slow_period ({self.slow_period})"
            )
        if self.signal_period < 1:
            raise ValueError(f"signal_period must be >= 1, got {self.signal_period}")

    @staticmethod
    def _ema(series: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average."""
        return series.ewm(span=period, adjust=False).mean()

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        if self.price_col not in data.columns:
            raise KeyError(
                f"Column '{self.price_col}' not found; available: {list(data.columns)}"
            )

        prices = data[self.price_col]
        ema_fast = self._ema(prices, self.fast_period)
        ema_slow = self._ema(prices, self.slow_period)
        macd_line = ema_fast - ema_slow
        signal_line = self._ema(macd_line, self.signal_period)
        histogram = macd_line - signal_line

        signals = pd.Series(0, index=data.index, dtype=int)

        valid = macd_line.notna() & signal_line.notna()
        prev_hist = histogram.shift(1)

        # Golden cross: histogram from negative/zero → positive
        buy_mask = valid & (histogram > 0) & (prev_hist <= 0)
        # Death cross: histogram from positive/zero → negative
        sell_mask = valid & (histogram < 0) & (prev_hist >= 0)

        signals[buy_mask] = 1
        signals[sell_mask] = -1

        signals = signals.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)
        return signals
