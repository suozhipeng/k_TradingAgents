"""BollingerBandsReversionStrategy — 布林带均值回归策略 — 震荡策略。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import StrategyBase


class BollingerBandsReversionStrategy(StrategyBase):
    """布林带均值回归策略 — 震荡策略。

    当价格触及下轨（超卖）时买入，触及上轨（超买）时卖出。

    Config keys (all optional):
        ma_period      : int  中轨MA窗口 (default ``20``)
        num_std        : float  标准差倍数 (default ``2.0``)
        price_col      : str  价格列名 (default ``"close"``)

    Signal logic
        - 收盘价 ≤ 下轨（MA - N×σ）→ ``+1`` (买入)
        - 收盘价 ≥ 上轨（MA + N×σ）→ ``-1`` (卖出)
        - 其他 → ``0`` (持有)
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.ma_period: int = int(self.config.get("ma_period", 20))
        self.num_std: float = float(self.config.get("num_std", 2.0))
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
        upper = ma + self.num_std * std
        lower = ma - self.num_std * std

        signals = pd.Series(0, index=data.index, dtype=int)
        valid = upper.notna() & lower.notna()

        # Oversold: price touches or breaks below lower band → buy
        buy_mask = valid & (prices <= lower)
        # Overbought: price touches or breaks above upper band → sell
        sell_mask = valid & (prices >= upper)

        signals[buy_mask] = 1
        signals[sell_mask] = -1

        signals = signals.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)
        return signals
