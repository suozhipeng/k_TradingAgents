"""Strategy base classes: StrategyBase and PortfolioStrategyBase."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class StrategyBase(ABC):
    """Abstract base class for backtest strategies.

    Subclasses must implement :meth:`generate_signals`.
    """

    def __init__(self, config: dict) -> None:
        self.config = dict(config)

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate trading signals from price/volume data.

        Parameters
        ----------
        data : pd.DataFrame
            Must contain at least ``close`` (and optionally ``open``, ``high``,
            ``low``, ``volume``) indexed by date.

        Returns
        -------
        pd.Series
            Integer signal series with the same index as *data*:
            ``1`` = buy, ``-1`` = sell, ``0`` = hold.
        """
        ...


class PortfolioStrategyBase(StrategyBase):
    """组合策略抽象基类 — 管理多标的投资组合。

    不适用单标的 ``generate_signals``。子类必须实现
    ``generate_portfolio_weights()``。

    Config keys (all optional):
        k : int     调仓间隔（交易日），默认 ``5``
        warmup : int  预热天数，默认 ``20``
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.k: int = int(self.config.get("k", 5))
        self.warmup: int = int(self.config.get("warmup", 20))

        if self.k < 1:
            raise ValueError(f"k must be >= 1, got {self.k}")

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """单标的信号生成 — 不支持，请用 ``generate_portfolio_weights``。"""
        raise NotImplementedError(
            f"{type(self).__name__} is a portfolio-level strategy; "
            "use generate_portfolio_weights(prices_df) or BacktestEngine.run_portfolio()."
        )

    @abstractmethod
    def generate_portfolio_weights(
        self, prices: pd.DataFrame, existing_weights: dict[str, float] | None = None
    ) -> dict[str, float]:
        """生成下一调仓周期的持仓权重。

        Parameters
        ----------
        prices : pd.DataFrame
            列名为股票代码，每列对应一只股票的收盘价。
        existing_weights : dict or None
            当前持仓权重（用于未选中时的保留逻辑，默认 None = 全部清仓）。

        Returns
        -------
        dict[str, float]
            股票代码 → 权重。总和归一化为 1.0。空 dict = 空仓。
        """
        ...

    def get_rebalance_dates(self, dates: pd.DatetimeIndex, start_idx: int | None = None) -> list[pd.Timestamp]:
        """计算调仓日列表。

        从 warmup 期后开始，每 k 个交易日调仓一次。
        子类可重写以实现自定义调仓日历。

        Parameters
        ----------
        dates : pd.DatetimeIndex
            全部交易日序列。
        start_idx : int or None
            起始索引（默认 warmup 参数值）。

        Returns
        -------
        list of Timestamp
        """
        if start_idx is None:
            start_idx = self.warmup
        return list(dates[start_idx::self.k])
