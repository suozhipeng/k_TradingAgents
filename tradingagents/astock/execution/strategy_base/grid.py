"""GridTradingStrategy — 网格交易策略 — 震荡策略。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import StrategyBase


class GridTradingStrategy(StrategyBase):
    """网格交易策略 — 震荡策略。

    在固定价格网格上低买高卖。网格层数、间距和初始基准价可配置。

    Config keys (all optional):
        grid_levels    : int    网格层数 (default ``5``)
        grid_spacing   : float  网格间距比例 (default ``0.02``, 即 2%)
        base_price     : float  基准价 (default ``None``, 使用首日收盘价)
        position_size  : float  每层仓位比例 (default ``0.2``, 即 20%)
        price_col      : str    价格列名 (default ``"close"``)

    Signal logic
        - 价格跌破某个网格下限 → ``+1`` (买入 — 吃掉一个网格)
        - 价格涨破某个网格上限 → ``-1`` (卖出 — 释放一个网格)
        - 价格在网格内或已超出全部网格 → ``0`` (持有)
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.grid_levels: int = int(self.config.get("grid_levels", 5))
        self.grid_spacing: float = float(self.config.get("grid_spacing", 0.02))
        self._base_price: float | None = self.config.get("base_price")
        self.position_size: float = float(self.config.get("position_size", 0.2))
        self.price_col: str = str(self.config.get("price_col", "close"))

        if self.grid_levels < 1:
            raise ValueError(f"grid_levels must be >= 1, got {self.grid_levels}")
        if self.grid_spacing <= 0:
            raise ValueError(f"grid_spacing must be > 0, got {self.grid_spacing}")
        if not (0 < self.position_size <= 1.0):
            raise ValueError(
                f"position_size must be in (0, 1], got {self.position_size}"
            )

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        if self.price_col not in data.columns:
            raise KeyError(
                f"Column '{self.price_col}' not found; available: {list(data.columns)}"
            )

        prices = data[self.price_col]

        # Determine base price from config or first close
        base = self._base_price if self._base_price is not None else prices.iloc[0]

        # Build grid levels: [base*(1-spacing)^k, ..., base, ..., base*(1+spacing)^k]
        grid_prices: list[float] = []
        for k in range(1, self.grid_levels + 1):
            grid_prices.append(base * (1 - self.grid_spacing * k))
        grid_prices.append(base)
        for k in range(1, self.grid_levels + 1):
            grid_prices.append(base * (1 + self.grid_spacing * k))
        grid_prices.sort()

        signals = pd.Series(0, index=data.index, dtype=int)

        # Track which grid levels have been "collected"
        # For simplicity: only generate signals on the *first* cross of each level
        prev_price = prices.shift(1)
        valid = prev_price.notna()

        for i, grid_level in enumerate(grid_prices):
            # Buy: price dropped to/through a grid level from above
            buy_cross = valid & (prices <= grid_level) & (prev_price > grid_level)
            signals[buy_cross] = 1

            # Sell: price rose to/through a grid level from below
            sell_cross = valid & (prices >= grid_level) & (prev_price < grid_level)
            signals[sell_cross] = -1

        # Reset to 0 for signals that might overlap (same period crosses multiple levels)
        # Simply keep the last assigned signal per period
        signals = signals.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)
        return signals
