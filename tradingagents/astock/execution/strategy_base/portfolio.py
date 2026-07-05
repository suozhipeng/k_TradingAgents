"""Portfolio-level MomentumRotationStrategy."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import PortfolioStrategyBase


class MomentumRotationStrategy(PortfolioStrategyBase):
    """龙头股动量轮动策略 — 组合级策略。

    多标的池中按风险调整动量选取 Top-L 只。
    不适用于单标的 ``generate_signals``，用 ``generate_portfolio_weights``。

    Config keys (all optional):
        n : int    动量计算周期（交易日），默认 ``20``
        k : int    调仓间隔（交易日），默认 ``5``
        l : int    持仓标的数量，默认 ``5``
        warmup : int  动量预热天数，默认 ``n``
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.n: int = int(self.config.get("n", 20))
        self.l: int = int(self.config.get("l", 5))
        # warmup defaults to n (overrides PortfolioStrategyBase default)
        self.warmup: int = int(self.config.get("warmup", self.n))
        self.k: int = int(self.config.get("k", 5))

        if self.n < 2:
            raise ValueError(f"n must be >= 2, got {self.n}")
        if self.k < 1:
            raise ValueError(f"k must be >= 1, got {self.k}")
        if self.l < 1:
            raise ValueError(f"l must be >= 1, got {self.l}")

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
        prices = prices.copy()
        # ── 1. 日收益率 ──
        daily_ret = prices.pct_change().replace([np.inf, -np.inf], np.nan)

        # ── 2. 风险调整动量 ──
        raw_momentum = daily_ret.rolling(window=self.n).mean()
        variance = daily_ret.rolling(window=self.n).var(ddof=0)
        adj_momentum = raw_momentum / np.sqrt(variance).replace(0, np.nan)

        # ── 3. 取最新值 ──
        latest_raw = raw_momentum.iloc[-1]
        latest_adj = adj_momentum.iloc[-1]

        # 第一重: 正原始动量
        pos_mask = latest_raw > 0
        candidates = latest_adj[pos_mask].dropna().sort_values(ascending=False)

        # 第二重: 选前 L
        selected = candidates.head(self.l)

        if selected.empty:
            return {}

        total = float(selected.sum())
        if total <= 0:
            return {}

        weights: dict[str, float] = {}
        for sym, w in selected.items():
            weights[str(sym)] = round(float(w) / total, 6)

        return weights
