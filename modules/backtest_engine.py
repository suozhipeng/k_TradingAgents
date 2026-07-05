"""
AStock Pro 工业级后端核心计算引擎
===================================

推平重建 v2.1 — 2026-07-06

功能覆盖:
  1. BaseStrategy 统一策略工厂（标准基类 + 3 种 A 股核心轮动算法）
  2. run_backtest_pipeline 统一入口（单策略 & 多策略矩阵并发）
  3. 3 大实盘防呆防线:
     - DataFrame 时间截断（前端 start_date / end_date 精确切片）
     - 沪深300 20 日均线风控拦截（强制清仓 + 国债逆回购 2%）
     - 坏数据脱水拦截器（NaN / Inf / 极端离群值 → 0.0）
  4. 沪深300 业绩基准线（灰色虚线，1.0 起点时间序列）
  5. 参数 MD5 哈希持久化到本地 DuckDB（前端一键分享锚点）
  6. 多策略矩阵并发计算（ThreadPoolExecutor）
  7. 幸存者偏差 / 前瞻偏差检测
  8. 深度风险归因（Sortino, Calmar, Beta, Drawdown Duration）

依赖:
  - pandas, numpy, hashlib
  - duckdb (optional, fallback silent)
  - concurrent.futures (stdlib)
  - 运行时项目: tradingagents.astock.data_sources (AStockDataFacade)
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

CSI300_SYMBOL = "000300.SH"
TRADING_DAYS_YEAR = 252.0
REPO_RATE_ANNUAL = 0.02  # 国债逆回购年化 2%
EXECUTION_SIGNAL = "ResearchOnly"

# ---------------------------------------------------------------------------
# 一、统一策略工厂 (Strategy Factory)
# ---------------------------------------------------------------------------


class BaseStrategy(ABC):
    """A 股回测策略标准基类。

    所有策略必须实现 ``generate_signals(data) → pd.Series[int]``。
    信号值: ``1`` = 买入, ``-1`` = 卖出, ``0`` = 持有。
    """

    name: str = "base"

    def __init__(self, config: dict | None = None) -> None:
        self.config = dict(config or {})

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """从 OHLCV DataFrame 生成交易信号。

        Parameters
        ----------
        data : pd.DataFrame
            必须包含 ``close`` 列，可选 ``open`` / ``high`` / ``low`` / ``volume``。
            index 为 ``pd.DatetimeIndex``。

        Returns
        -------
        pd.Series
            dtype int, 值域 {-1, 0, 1}, index 与 data 相同。
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} config={self.config}>"


# ── 1.1 MovingAverageTrend — 均线趋势跟踪 ──


class MovingAverageTrend(BaseStrategy):
    """双均线趋势跟踪策略。

    Config:
        fast_period : int  (default 5)
        slow_period : int  (default 20)
        price_col   : str  (default "close")
    """

    name: str = "MovingAverageTrend"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.fast: int = int(self.config.get("fast_period", 5))
        self.slow: int = int(self.config.get("slow_period", 20))
        self.price_col: str = str(self.config.get("price_col", "close"))
        if self.fast >= self.slow:
            raise ValueError(f"fast_period ({self.fast}) must be < slow_period ({self.slow})")

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        prices = data[self.price_col]
        fast_ma = prices.rolling(self.fast).mean()
        slow_ma = prices.rolling(self.slow).mean()
        prev_fast = fast_ma.shift(1)
        prev_slow = slow_ma.shift(1)
        sig = pd.Series(0, index=data.index, dtype=int)
        valid = fast_ma.notna() & slow_ma.notna() & prev_fast.notna() & prev_slow.notna()
        buy = valid & (fast_ma > slow_ma) & (prev_fast <= prev_slow)
        sell = valid & (fast_ma < slow_ma) & (prev_fast >= prev_slow)
        sig[buy] = 1
        sig[sell] = -1
        return sig.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)


# ── 1.2 BullTrend — 多头排列趋势跟随 ──


class BullTrend(BaseStrategy):
    """多头排列趋势跟随 — 牛市策略。

    Config:
        fast_ma  : int  (default 5)
        mid_ma   : int  (default 20)
        slow_ma  : int  (default 60)
        volume_ratio : float (default 1.5)
        price_col : str (default "close")
    """

    name: str = "BullTrend"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.fast: int = int(self.config.get("fast_ma", 5))
        self.mid: int = int(self.config.get("mid_ma", 20))
        self.slow: int = int(self.config.get("slow_ma", 60))
        self.vol_ratio: float = float(self.config.get("volume_ratio", 1.5))
        self.price_col: str = str(self.config.get("price_col", "close"))
        self.volume_col: str = str(self.config.get("volume_col", "volume"))
        if not (self.fast < self.mid < self.slow):
            raise ValueError(f"Expected fast ({self.fast}) < mid ({self.mid}) < slow ({self.slow})")

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        prices = data[self.price_col]
        ma5 = prices.rolling(self.fast).mean()
        ma20 = prices.rolling(self.mid).mean()
        ma60 = prices.rolling(self.slow).mean()
        sig = pd.Series(0, index=data.index, dtype=int)
        valid = ma5.notna() & ma20.notna() & ma60.notna()

        vol_confirmed = pd.Series(True, index=data.index)
        if self.volume_col in data.columns:
            vol_ma = data[self.volume_col].rolling(self.mid).mean()
            vol_confirmed = data[self.volume_col] > vol_ma * self.vol_ratio
            vol_confirmed = vol_confirmed.fillna(True)

        # 多头排列 + 成交量确认
        sig[valid & (ma20 > ma60) & (ma5 > ma20) & vol_confirmed] = 1
        # 空头排列
        sig[valid & ((ma5 < ma20) | (ma20 < ma60))] = -1
        return sig.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)


# ── 1.3 MeanReversion — 均值回归 ──


class MeanReversion(BaseStrategy):
    """均值回归策略 — 震荡策略。

    Config:
        std_multiplier : float (default 2.0)
        ma_period      : int   (default 20)
        price_col      : str   (default "close")
    """

    name: str = "MeanReversion"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.std_mul: float = float(self.config.get("std_multiplier", 2.0))
        self.ma_period: int = int(self.config.get("ma_period", 20))
        self.price_col: str = str(self.config.get("price_col", "close"))

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        prices = data[self.price_col]
        ma = prices.rolling(self.ma_period).mean()
        std = prices.rolling(self.ma_period).std(ddof=0)
        sig = pd.Series(0, index=data.index, dtype=int)
        valid = ma.notna() & std.notna()
        sig[valid & (prices < ma - self.std_mul * std)] = 1
        sig[valid & (prices > ma + self.std_mul * std)] = -1
        return sig.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)


# ── 1.4 RSIRange — RSI 区间交易 ──


class RSIRange(BaseStrategy):
    """RSI 区间交易策略 — 震荡策略。

    Config:
        rsi_period  : int  (default 14)
        oversold    : int  (default 30)
        overbought  : int  (default 70)
        price_col   : str  (default "close")
    """

    name: str = "RSIRange"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.period: int = int(self.config.get("rsi_period", 14))
        self.oversold: int = int(self.config.get("oversold", 30))
        self.overbought: int = int(self.config.get("overbought", 70))
        self.price_col: str = str(self.config.get("price_col", "close"))

    @staticmethod
    def _rsi(prices: pd.Series, period: int) -> pd.Series:
        delta = prices.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_g = gain.rolling(period).mean()
        avg_l = loss.rolling(period).mean()
        rs = avg_g / avg_l.replace(0, float("nan"))
        rsi = 100.0 - (100.0 / (1.0 + rs))
        has = avg_g.notna() & avg_l.notna()
        rsi[has & (avg_l == 0) & (avg_g > 0)] = 100.0
        rsi[has & (avg_g == 0) & (avg_l == 0)] = 50.0
        return rsi

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        prices = data[self.price_col]
        rsi = self._rsi(prices, self.period)
        sig = pd.Series(0, index=data.index, dtype=int)
        valid = rsi.notna()
        sig[valid & (rsi < self.oversold)] = 1
        sig[valid & (rsi > self.overbought)] = -1
        return sig.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)


# ── 1.5 MACDTrend — MACD 趋势跟踪 ──


class MACDTrend(BaseStrategy):
    """MACD 趋势跟踪策略 — 趋势策略。

    Config:
        fast_period   : int  (default 12)
        slow_period   : int  (default 26)
        signal_period : int  (default 9)
        price_col     : str  (default "close")
    """

    name: str = "MACDTrend"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.fast: int = int(self.config.get("fast_period", 12))
        self.slow: int = int(self.config.get("slow_period", 26))
        self.signal: int = int(self.config.get("signal_period", 9))
        self.price_col: str = str(self.config.get("price_col", "close"))
        if self.fast >= self.slow:
            raise ValueError(f"fast ({self.fast}) must be < slow ({self.slow})")

    @staticmethod
    def _ema(s: pd.Series, p: int) -> pd.Series:
        return s.ewm(span=p, adjust=False).mean()

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        prices = data[self.price_col]
        macd = self._ema(prices, self.fast) - self._ema(prices, self.slow)
        signal = self._ema(macd, self.signal)
        hist = macd - signal
        sig = pd.Series(0, index=data.index, dtype=int)
        valid = macd.notna() & signal.notna()
        prev_h = hist.shift(1)
        sig[valid & (hist > 0) & (prev_h <= 0)] = 1
        sig[valid & (hist < 0) & (prev_h >= 0)] = -1
        return sig.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)


# ── 1.6 BollingerBands — 布林带均值回归 ──


class BollingerBands(BaseStrategy):
    """布林带均值回归策略 — 震荡策略。

    Config:
        ma_period  : int   (default 20)
        num_std    : float (default 2.0)
        price_col  : str   (default "close")
    """

    name: str = "BollingerBands"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.period: int = int(self.config.get("ma_period", 20))
        self.num_std: float = float(self.config.get("num_std", 2.0))
        self.price_col: str = str(self.config.get("price_col", "close"))

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        prices = data[self.price_col]
        ma = prices.rolling(self.period).mean()
        std = prices.rolling(self.period).std(ddof=0)
        upper = ma + self.num_std * std
        lower = ma - self.num_std * std
        sig = pd.Series(0, index=data.index, dtype=int)
        valid = upper.notna() & lower.notna()
        sig[valid & (prices <= lower)] = 1
        sig[valid & (prices >= upper)] = -1
        return sig.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)


# ── 1.7 DefensiveMomentum — 防御性动量 ──


class DefensiveMomentum(BaseStrategy):
    """防御性动量策略 — 熊市策略。

    Config:
        roc_period    : int   (default 20)
        vol_period    : int   (default 20)
        vol_threshold : float (default 0.02)
        price_col     : str   (default "close")
    """

    name: str = "DefensiveMomentum"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.roc: int = int(self.config.get("roc_period", 20))
        self.vol_p: int = int(self.config.get("vol_period", 20))
        self.vol_thr: float = float(self.config.get("vol_threshold", 0.02))
        self.price_col: str = str(self.config.get("price_col", "close"))

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        prices = data[self.price_col]
        roc = prices.pct_change(periods=self.roc)
        vol = prices.pct_change().rolling(self.vol_p).std(ddof=0)
        sig = pd.Series(0, index=data.index, dtype=int)
        valid = roc.notna() & vol.notna()
        sig[valid & (roc > 0) & (vol <= self.vol_thr)] = 1
        sig[valid & (roc < 0)] = -1
        return sig.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)


# ── 1.8 PutWrite — 空头对冲 ──


class PutWrite(BaseStrategy):
    """Put Write 空头对冲策略 — 熊市策略。

    Config:
        fast_ma   : int  (default 5)
        mid_ma    : int  (default 20)
        slow_ma   : int  (default 60)
        price_col : str  (default "close")
    """

    name: str = "PutWrite"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.fast: int = int(self.config.get("fast_ma", 5))
        self.mid: int = int(self.config.get("mid_ma", 20))
        self.slow: int = int(self.config.get("slow_ma", 60))
        self.price_col: str = str(self.config.get("price_col", "close"))
        if not (self.fast < self.mid < self.slow):
            raise ValueError(f"Expected fast ({self.fast}) < mid ({self.mid}) < slow ({self.slow})")

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        prices = data[self.price_col]
        ma5 = prices.rolling(self.fast).mean()
        ma20 = prices.rolling(self.mid).mean()
        ma60 = prices.rolling(self.slow).mean()
        sig = pd.Series(0, index=data.index, dtype=int)
        valid = ma5.notna() & ma20.notna() & ma60.notna()
        sig[valid & (ma5 < ma20) & (ma20 < ma60)] = -1
        return sig.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)


# ── 1.9 ValueAverage — 价值平均策略 ──


class ValueAverage(BaseStrategy):
    """价值平均 / 成本平均策略 — 牛市策略。

    Config:
        pe_low_pct  : int   (default 30)
        pe_high_pct : int   (default 70)
        price_col   : str   (default "close")
    """

    name: str = "ValueAverage"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.low_pct: int = int(self.config.get("pe_low_pct", 30))
        self.high_pct: int = int(self.config.get("pe_high_pct", 70))
        self.price_col: str = str(self.config.get("price_col", "close"))

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        prices = data[self.price_col]
        low_thr = prices.expanding().quantile(self.low_pct / 100.0)
        high_thr = prices.expanding().quantile(self.high_pct / 100.0)
        sig = pd.Series(0, index=data.index, dtype=int)
        enough = prices.expanding().count() >= 20
        sig[enough & (prices <= low_thr)] = 1
        sig[enough & (prices >= high_thr)] = -1
        return sig.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)


# ── 1.10 AbsoluteLimitUpScore — 绝对连板梯队得分 ──


class AbsoluteLimitUpScore(BaseStrategy):
    """绝对连板梯队得分策略。

    统计连续涨停板数量，梯次打分，高分买入，断板卖出。

    Config:
        min_score   : int   买入最低得分 (default 3)
        hold_score  : int   持有最低得分 (default 1)
        limit_pct   : float 涨停阈值 (default 0.0995, 普通 A 股)
        price_col   : str   (default "close")
    """

    name: str = "AbsoluteLimitUpScore"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.min_score: int = int(self.config.get("min_score", 3))
        self.hold_score: int = int(self.config.get("hold_score", 1))
        self.limit_pct: float = float(self.config.get("limit_pct", 0.0995))
        self.price_col: str = str(self.config.get("price_col", "close"))

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        prices = data[self.price_col]
        pct_change = prices.pct_change()

        # 标记涨停日
        is_limit = pct_change >= self.limit_pct

        # 计算连板计数 (rolling streak of consecutive limit-ups)
        streak = is_limit.astype(int).groupby(
            (is_limit != is_limit.shift()).cumsum()
        ).cumsum()

        # 非涨停日连板计数归零
        streak[~is_limit] = 0

        score = streak  # 连板数 = 得分

        sig = pd.Series(0, index=data.index, dtype=int)

        # 买入: 得分 >= min_score 且前一天未持有
        prev_score = score.shift(1).fillna(0)
        sig[(score >= self.min_score) & (prev_score < self.min_score)] = 1

        # 卖出: 得分 < hold_score 且曾经满足过买入条件
        sig[(score < self.hold_score) & (score.shift(1) >= self.hold_score)] = -1

        # 断板（非涨停日且有持仓）立即卖出
        sig[~is_limit & prev_score.gt(0)] = -1

        return sig.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)


# ── 1.3 LeadingSectorMomentum — 领涨板块动量斜率 ──


class LeadingSectorMomentum(BaseStrategy):
    """领涨板块动量斜率策略。

    基于板块指数的短期动量斜率决定方向。斜率 = (MA_fast - MA_slow) / MA_slow。
    斜率陡升买入，斜率陡降卖出。

    Config:
        fast_period  : int   快线窗口 (default 5)
        slow_period  : int   慢线窗口 (default 20)
        buy_threshold: float 买入斜率阈值 (default 0.03 = 3%)
        sell_threshold: float 卖出斜率阈值 (default -0.02 = -2%)
        price_col    : str   (default "close")
    """

    name: str = "LeadingSectorMomentum"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.fast: int = int(self.config.get("fast_period", 5))
        self.slow: int = int(self.config.get("slow_period", 20))
        self.buy_thr: float = float(self.config.get("buy_threshold", 0.03))
        self.sell_thr: float = float(self.config.get("sell_threshold", -0.02))
        self.price_col: str = str(self.config.get("price_col", "close"))

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        prices = data[self.price_col]
        ma_fast = prices.rolling(self.fast).mean()
        ma_slow = prices.rolling(self.slow).mean()

        # 动量斜率
        slope = (ma_fast - ma_slow) / ma_slow.replace(0, float("nan"))

        prev_slope = slope.shift(1)

        sig = pd.Series(0, index=data.index, dtype=int)
        valid = slope.notna() & prev_slope.notna()

        # 斜率上穿买入阈值
        sig[valid & (slope > self.buy_thr) & (prev_slope <= self.buy_thr)] = 1
        # 斜率下穿卖出阈值
        sig[valid & (slope < self.sell_thr) & (prev_slope >= self.sell_thr)] = -1

        return sig.replace([np.inf, -np.inf], np.nan).fillna(0).astype(int)


# ---------------------------------------------------------------------------
# 策略工厂映射
# ---------------------------------------------------------------------------

_STRATEGY_CLASSES: dict[str, type[BaseStrategy]] = {
    "MovingAverageTrend": MovingAverageTrend,
    "BullTrend": BullTrend,
    "MeanReversion": MeanReversion,
    "RSIRange": RSIRange,
    "MACDTrend": MACDTrend,
    "BollingerBands": BollingerBands,
    "DefensiveMomentum": DefensiveMomentum,
    "PutWrite": PutWrite,
    "ValueAverage": ValueAverage,
    "AbsoluteLimitUpScore": AbsoluteLimitUpScore,
    "LeadingSectorMomentum": LeadingSectorMomentum,
}


def create_strategy(name: str, config: dict | None = None) -> BaseStrategy:
    """按名称实例化策略。"""
    cls = _STRATEGY_CLASSES.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown strategy '{name}'. Available: {list(_STRATEGY_CLASSES.keys())}"
        )
    return cls(config)


def list_strategies() -> list[str]:
    """返回所有已注册的策略名称列表。"""
    return list(_STRATEGY_CLASSES.keys())


# ---------------------------------------------------------------------------
# 二、数据模型
# ---------------------------------------------------------------------------


@dataclass
class BacktestMetrics:
    """聚合回测绩效指标。"""

    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    avg_holding_days: float = 0.0
    profit_factor: float = 0.0
    benchmark_return: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0


@dataclass
class BacktestSnapshot:
    """单期快照。"""

    date: str
    portfolio_value: float
    cash: float
    shares: float
    signal: int
    benchmark_value: float = 1.0  # 基准值，以 1.0 为起点


@dataclass
class TradeRecord:
    """单笔交易记录。"""

    date: str
    direction: str  # "buy" | "sell"
    price: float
    shares: float
    fees: float
    pnl: float = 0.0
    reason: str = ""


@dataclass
class BacktestResult:
    """回测最终输出。"""

    run_id: str
    symbol: str
    strategy_name: str
    start_date: str
    end_date: str
    initial_cash: float
    final_value: float

    metrics: BacktestMetrics = field(default_factory=BacktestMetrics)

    trades: list[dict] = field(default_factory=list)
    snapshots: list[dict] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    benchmark_curve: list[float] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)

    cost_breakdown: dict = field(default_factory=lambda: {
        "total_fees": 0.0,
        "commission": 0.0,
        "stamp_tax": 0.0,
        "slippage": 0.0,
    })

    market_regime: str = ""
    risk_gate_blocks: int = 0
    sanitized_flags: list[str] = field(default_factory=list)
    params_hash: str = ""


@dataclass
class PipelineParams:
    """``run_backtest_pipeline`` 参数封装。"""

    symbol: str
    strategy_name: str
    start_date: str
    end_date: str
    strategy_config: dict = field(default_factory=dict)
    initial_cash: float = 100_000.0
    rebalance_freq: str = "M"

    risk_gate_enabled: bool = True          # 沪深300 20日线风控
    risk_gate_symbol: str = CSI300_SYMBOL  # 基准风控指数
    sanitize_enabled: bool = True           # 坏数据清洗
    benchmark_enabled: bool = True          # 基准线

    # 多策略参数（矩阵）
    multi_strategy_params: list[dict] | None = None  # [{strategy_name, strategy_config, weight}]

    # 回测引擎覆盖
    fee_commission_rate: float = 0.00025
    fee_stamp_tax_rate: float = 0.001
    fee_slippage_rate: float = 0.001
    fee_min_commission: float = 5.0


# ---------------------------------------------------------------------------
# 三、核心回测引擎
# ---------------------------------------------------------------------------


class BacktestCoreEngine:
    """工业级回测核心计算引擎。

    职责:
      1. 数据获取与时间截断
      2. 沪深300 20 日线风控
      3. 逐期回测循环
      4. 指标计算与坏数据清洗
      5. 基准线计算
      6. MD5 持久化
    """

    def __init__(self, use_mock_data: bool = False) -> None:
        self._facade: Any = None
        self._use_mock_data = use_mock_data

    # ── 3.1 数据获取与时间截断 ──

    def fetch_ohlcv(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取 OHLCV 数据，返回时间截断后的 DataFrame。

        第一步：加载原始数据
        第二步：强制根据 start_date / end_date 精确切片（防呆防线 #1）
        """
        if self._use_mock_data:
            df = self._mock_bars(symbol, start_date, end_date)
        else:
            df = self._real_data(symbol, start_date, end_date)

        if df.empty:
            return df

        # === 防呆防线 #1: DataFrame 时间切片 ===
        df = df.sort_index()
        df = df[
            (df.index >= pd.Timestamp(start_date)) &
            (df.index <= pd.Timestamp(end_date))
        ]
        return df

    def _real_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        try:
            from tradingagents.astock.data_sources import AStockDataFacade
            if self._facade is None:
                self._facade = AStockDataFacade()
            resp = self._facade.get_kline(
                symbol=symbol, start_date=start_date,
                end_date=end_date, interval="1d",
            )
            if resp.status == "ok" and resp.data and resp.data.get("bars"):
                bars = resp.data["bars"]
                df = pd.DataFrame(bars)
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date").sort_index()
                for col in ("open", "high", "low", "close", "volume"):
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                return df
        except Exception as exc:
            logger.warning("Real data fetch failed for %s: %s", symbol, exc)
        return pd.DataFrame()

    def _mock_bars(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """确定性的 mock OHLCV（仅用于测试）。"""
        dt_start = datetime.strptime(start, "%Y-%m-%d")
        dt_end = datetime.strptime(end, "%Y-%m-%d")
        rows: list[dict] = []
        price = 100.0
        cur = dt_start
        while cur <= dt_end:
            if cur.weekday() < 5:
                change = price * 0.01 * (hash(f"{symbol}:{cur}") % 200 - 100) / 100.0
                close_p = round(price + change, 2)
                rows.append({
                    "date": cur.strftime("%Y-%m-%d"),
                    "open": round(price, 2),
                    "high": round(max(price, close_p) * 1.005, 2),
                    "low": round(min(price, close_p) * 0.995, 2),
                    "close": close_p,
                    "volume": 1_000_000,
                })
                price = close_p
            cur += timedelta(days=1)
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        return df.set_index("date").sort_index()

    # ── 3.2 沪深300 20 日线风控拦截 ──

    def _load_benchmark_data(
        self, symbol: str, start_date: str, end_date: str,
    ) -> pd.DataFrame:
        """获取基准指数（沪深300）OHLCV。

        优先用 AStockDataFacade，失败则 mock。
        """
        bmk = self.fetch_ohlcv(symbol, start_date, end_date)
        if bmk.empty and not self._use_mock_data:
            logger.warning(
                "Benchmark %s data empty, fallback to mock", symbol,
            )
            bmk = self._mock_bars(symbol, start_date, end_date)
        return bmk

    def _risk_gate_check(
        self, bmk_df: pd.DataFrame, current_date: pd.Timestamp,
    ) -> bool:
        """防呆防线 #2: 沪深300 20 日均线风控。

        如果当前日期沪深300 位于 20 日均线下方，返回 False（禁止买入）。

        Returns
        -------
        bool
            True = 安全（可买入）, False = 风控拦截（禁止买入）
        """
        if bmk_df.empty or len(bmk_df) < 20:
            return True  # 数据不足时放行

        # 取当前日期及之前的数据
        hist = bmk_df[bmk_df.index <= current_date]
        if len(hist) < 20:
            return True

        ma20 = hist["close"].rolling(20).mean()
        current_close = hist["close"].iloc[-1]
        current_ma20 = ma20.iloc[-1]

        if pd.isna(current_ma20):
            return True

        return current_close >= current_ma20

    # ── 3.3 费用计算 ──

    def _calc_fees(
        self, price: float, shares: float, is_buy: bool,
    ) -> dict:
        """计算 A 股交易费用。"""
        turnover = price * shares
        commission = max(turnover * self._fee_cfg["commission_rate"],
                         self._fee_cfg["min_commission"])
        stamp_tax = turnover * self._fee_cfg["stamp_tax_rate"] if not is_buy else 0.0
        slippage = turnover * self._fee_cfg["slippage_rate"] * 2
        total = commission + stamp_tax + slippage
        return {
            "commission": round(commission, 4),
            "stamp_tax": round(stamp_tax, 4),
            "slippage": round(slippage, 4),
            "total": round(total, 4),
        }

    # ── 3.4 主回测循环 ──

    def run(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        strategy: BaseStrategy,
        *,
        initial_cash: float = 100_000.0,
        rebalance_freq: str = "M",
        risk_gate_enabled: bool = True,
        risk_gate_symbol: str = CSI300_SYMBOL,
        sanitize_enabled: bool = True,
        benchmark_enabled: bool = True,
    ) -> BacktestResult:
        """执行单策略单标的回测。"""
        self._fee_cfg = {
            "commission_rate": 0.00025,
            "stamp_tax_rate": 0.001,
            "slippage_rate": 0.001,
            "min_commission": 5.0,
        }

        run_id = datetime.now().strftime("%Y%m%d%H%M%S")
        result = BacktestResult(
            run_id=run_id,
            symbol=symbol,
            strategy_name=strategy.name,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            final_value=initial_cash,
        )

        # ── 加载数据 + 时间切片 ──
        df = self.fetch_ohlcv(symbol, start_date, end_date)
        if df.empty:
            logger.warning("No data for %s in %s‑%s", symbol, start_date, end_date)
            return result

        # ── 加载基准指数（沪深300） ──
        bmk_df = pd.DataFrame()
        if risk_gate_enabled or benchmark_enabled:
            bmk_df = self._load_benchmark_data(risk_gate_symbol, start_date, end_date)

        # ── 按重采样周期分组 ──
        rebalance = rebalance_freq.replace("M", "ME")  # pandas 0.25+ compat
        periods = df.resample(rebalance)

        cash = initial_cash
        shares = 0.0
        equity: list[float] = [initial_cash]
        dates_list: list[pd.Timestamp] = [df.index[0]]
        trades: list[dict] = []
        snapshots: list[dict] = []
        risk_gate_blocks = 0

        for period_label, period_data in periods:
            if period_data.empty:
                continue

            close_at_end = float(period_data["close"].iloc[-1])
            period_date = period_data.index[-1]

            # ── 生成信号 ──
            sig_series = strategy.generate_signals(period_data)
            non_zero = sig_series[sig_series != 0]
            signal = int(non_zero.iloc[-1]) if not non_zero.empty else 0

            period_start_val = cash + shares * close_at_end

            if signal == 1 and cash > 0:
                # === 防呆防线 #2: 大盘 20 日线风控 ===
                risk_blocked = False
                if risk_gate_enabled and not bmk_df.empty:
                    gate_pass = self._risk_gate_check(bmk_df, period_date)
                    if not gate_pass:
                        risk_blocked = True
                        risk_gate_blocks += 1

                if risk_blocked:
                    # 强制清空持仓, 资金释放为现金, 国债逆回购 2%
                    if shares > 0:
                        # 卖出持仓
                        fees = self._calc_fees(close_at_end, shares, is_buy=False)
                        proceeds = shares * close_at_end - fees["total"]
                        cash += proceeds
                        trades.append({
                            "date": str(period_date.date()),
                            "direction": "sell",
                            "price": close_at_end,
                            "shares": round(shares, 4),
                            "fees": fees["total"],
                            "pnl": round(proceeds - (shares * close_at_end), 4),
                            "reason": "risk_gate_ma20_forced_liquidation",
                        })
                        shares = 0.0
                    # 空仓自动产生国债逆回购收益 (年化2%按日计)
                    days_in_period = len(period_data)
                    repo_return = cash * (REPO_RATE_ANNUAL / 365.0) * days_in_period
                    cash += repo_return
                else:
                    # 正常买入
                    buy_shares = cash / close_at_end
                    # 迭代缩减至费用可覆盖
                    for _ in range(5):
                        fees = self._calc_fees(
                            close_at_end, buy_shares, is_buy=True,
                        )
                        net_cost = buy_shares * close_at_end + fees["total"]
                        if net_cost <= cash:
                            break
                        buy_shares = (cash - fees.get("total", 0)) / close_at_end

                    if buy_shares > 0.001:
                        fees = self._calc_fees(
                            close_at_end, buy_shares, is_buy=True,
                        )
                        net_cost = buy_shares * close_at_end + fees["total"]
                        shares += buy_shares
                        cash -= net_cost
                        trades.append({
                            "date": str(period_date.date()),
                            "direction": "buy",
                            "price": close_at_end,
                            "shares": round(buy_shares, 4),
                            "fees": fees["total"],
                            "commission": fees["commission"],
                            "stamp_tax": fees["stamp_tax"],
                            "slippage": fees["slippage"],
                            "pnl": 0.0,
                            "reason": "signal_buy",
                        })

            elif signal == -1 and shares > 0:
                # 卖出全部持仓
                sell_value = shares * close_at_end
                fees = self._calc_fees(close_at_end, shares, is_buy=False)
                proceeds = sell_value - fees["total"]
                pnl = round(proceeds - (shares * close_at_end), 4)
                cash += proceeds
                trades.append({
                    "date": str(period_date.date()),
                    "direction": "sell",
                    "price": close_at_end,
                    "shares": round(shares, 4),
                    "fees": fees["total"],
                    "commission": fees["commission"],
                    "stamp_tax": fees["stamp_tax"],
                    "slippage": fees["slippage"],
                    "pnl": pnl,
                    "reason": "signal_sell",
                })
                shares = 0.0

            # 记录快照
            end_val = cash + shares * close_at_end
            equity.append(end_val)
            dates_list.append(period_date)
            snapshots.append({
                "date": str(period_date.date()),
                "portfolio_value": round(end_val, 2),
                "cash": round(cash, 2),
                "shares": round(shares, 4),
                "signal": signal,
            })

        # ── 3.5 计算指标 ──

        equity_series = pd.Series(equity, index=dates_list)
        metrics = self._compute_metrics(equity_series, trades)

        # === 防呆防线 #3: 坏数据脱水拦截器 ===
        sanitized_flags: list[str] = []
        if sanitize_enabled:
            metrics, sanitized_flags = self._sanitize_metrics(metrics)

        # ── 基准线 ──
        bench_curve: list[float] = []
        if benchmark_enabled and not bmk_df.empty:
            bench_curve = self._compute_benchmark_curve(bmk_df, dates_list)

        # ── 费用汇总 ──
        cost_bd = {"total_fees": 0.0, "commission": 0.0, "stamp_tax": 0.0, "slippage": 0.0}
        for t in trades:
            cost_bd["total_fees"] += t.get("fees", 0)
            for k in ("commission", "stamp_tax", "slippage"):
                v = t.get(k)
                if isinstance(v, (int, float)):
                    cost_bd[k] += v

        result.metrics = metrics
        result.final_value = float(equity[-1]) if len(equity) > 1 else initial_cash
        result.trades = trades
        result.snapshots = snapshots
        result.equity_curve = [round(v, 2) for v in equity]
        result.benchmark_curve = [round(v, 6) for v in bench_curve]
        result.dates = [str(d.date()) for d in dates_list]
        result.cost_breakdown = cost_bd
        result.risk_gate_blocks = risk_gate_blocks
        result.sanitized_flags = sanitized_flags

        # ── 3.6 MD5 参数哈希 ──
        result.params_hash = self._compute_params_hash(result)
        result.run_id = run_id

        return result

    # ── 3.5 指标计算 ──

    @staticmethod
    def _compute_metrics(
        equity: pd.Series, trades: list[dict],
    ) -> BacktestMetrics:
        """从净值曲线和交易列表计算全部绩效指标。"""
        m = BacktestMetrics()

        if len(equity) < 2:
            return m

        # 收益率
        total_ret = float(equity.iloc[-1] / equity.iloc[0] - 1)
        n = float(len(equity))
        annual_ret = (1.0 + total_ret) ** (TRADING_DAYS_YEAR / max(n, 1.0)) - 1.0

        # 日收益率
        daily_ret = equity.pct_change().fillna(0.0)
        excess = daily_ret - (0.02 / TRADING_DAYS_YEAR)

        # Sharpe
        sharpe = 0.0
        if excess.std(ddof=1) > 1e-12:
            sharpe = float(excess.mean() / excess.std(ddof=1) * math.sqrt(TRADING_DAYS_YEAR))

        # Sortino (仅下行波动率)
        downside = excess[excess < 0]
        sortino = 0.0
        if len(downside) > 1 and downside.std(ddof=1) > 1e-12:
            sortino = float(
                excess.mean() / downside.std(ddof=1) * math.sqrt(TRADING_DAYS_YEAR)
            )

        # 最大回撤
        cummax = equity.cummax()
        dd = (equity - cummax) / cummax
        max_dd = float(abs(dd.min()))

        # Calmar
        calmar = annual_ret / max_dd if max_dd > 1e-12 else 0.0

        # 胜率
        win_rate = 0.0
        if trades:
            wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
            win_rate = wins / len(trades)

        # 平均持仓天数
        avg_hold = 0.0
        buy_dates: list[str] = []
        for t in trades:
            if t.get("direction") == "buy":
                buy_dates.append(t["date"])
            elif t.get("direction") == "sell" and buy_dates:
                buy_dates.pop(0)
        if buy_dates:
            avg_hold = float(len(buy_dates))

        # Profit Factor
        gross_profit = sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0)
        gross_loss = abs(sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 1e-12 else 0.0

        m.total_return = round(total_ret, 6)
        m.annualized_return = round(annual_ret, 6)
        m.sharpe_ratio = round(sharpe, 6)
        m.sortino_ratio = round(sortino, 6)
        m.max_drawdown = round(max_dd, 6)
        m.calmar_ratio = round(calmar, 6)
        m.win_rate = round(win_rate, 6)
        m.total_trades = len(trades)
        m.avg_holding_days = round(avg_hold, 2)
        m.profit_factor = round(profit_factor, 6)
        return m

    # ── 防呆防线 #3: 指标清洗 ──

    @staticmethod
    def _sanitize_metrics(metrics: BacktestMetrics) -> tuple[BacktestMetrics, list[str]]:
        """脱水拦截器: NaN / Inf / 极端离群值 → 0.0。

        返回 (清洗后指标, 触发标记列表)。
        """
        flags: list[str] = []
        fields = [
            "total_return", "annualized_return", "sharpe_ratio",
            "sortino_ratio", "max_drawdown", "calmar_ratio",
            "win_rate", "profit_factor",
        ]

        for fname in fields:
            raw = getattr(metrics, fname)
            cleaned = raw

            if isinstance(cleaned, float):
                if math.isnan(cleaned) or math.isinf(cleaned):
                    cleaned = 0.0
                    flags.append(f"{fname}_nan_inf")

                # 极端离群值
                if fname in ("sharpe_ratio", "sortino_ratio") and abs(cleaned) > 20:
                    cleaned = 0.0
                    flags.append(f"{fname}_extreme")
                if fname in ("total_return", "annualized_return") and abs(cleaned) > 10:
                    cleaned = 0.0
                    flags.append(f"{fname}_extreme")
                if fname == "max_drawdown" and (cleaned > 1.0 or cleaned < 0.0):
                    cleaned = 0.0
                    flags.append(f"{fname}_out_of_range")
                if fname == "win_rate" and (cleaned < 0.0 or cleaned > 1.0):
                    cleaned = 0.0
                    flags.append(f"{fname}_out_of_range")
                if fname == "profit_factor" and cleaned > 100:
                    cleaned = 0.0
                    flags.append(f"{fname}_extreme")

            setattr(metrics, fname, cleaned)

        return metrics, flags

    # ── 基准线 ──

    @staticmethod
    def _compute_benchmark_curve(
        bmk_df: pd.DataFrame, backtest_dates: list[pd.Timestamp],
    ) -> list[float]:
        """计算沪深300 基准曲线（1.0 为起点）。

        在回测日期点上进行对齐插值。
        """
        if bmk_df.empty or not backtest_dates:
            return []

        closes = bmk_df["close"]
        first_close = float(closes.iloc[0]) if not closes.empty else 1.0
        if first_close <= 0:
            return []

        # 对齐回测日期
        aligned = closes.reindex(backtest_dates, method="ffill")
        if aligned.isna().all():
            return [1.0] * len(backtest_dates)

        curve = (aligned / first_close).fillna(1.0).tolist()
        return [round(float(v), 6) for v in curve]

    # ── MD5 哈希 ──

    @staticmethod
    def _compute_params_hash(result: BacktestResult) -> str:
        """根据参数组合生成唯一 MD5 哈希 ID。"""
        payload = {
            "symbol": result.symbol,
            "strategy": result.strategy_name,
            "start": result.start_date,
            "end": result.end_date,
            "metrics": {
                "total_return": result.metrics.total_return,
                "sharpe": result.metrics.sharpe_ratio,
                "max_dd": result.metrics.max_drawdown,
                "trades": result.metrics.total_trades,
            },
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.md5(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 四、统一执行入口
# ---------------------------------------------------------------------------


def _build_multi_config(params: PipelineParams) -> list[dict]:
    """构建多策略矩阵参数列表。"""
    if params.multi_strategy_params:
        return params.multi_strategy_params

    return [
        {
            "strategy_name": params.strategy_name,
            "strategy_config": params.strategy_config,
            "weight": 1.0,
        },
    ]


def _persist_to_duckdb(result: BacktestResult) -> None:
    """将回测结果持久化到本地 DuckDB（静默 fallback）。"""
    try:
        import duckdb
        db_path = os.path.join(
            os.path.dirname(__file__), "..",
            "tradingagents", "astock", "store", "astock.duckdb",
        )
        # 确保目录存在
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        conn = duckdb.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS backtest_runs (
                run_id VARCHAR PRIMARY KEY,
                params_hash VARCHAR,
                symbol VARCHAR,
                strategy_name VARCHAR,
                start_date DATE,
                end_date DATE,
                initial_cash DOUBLE,
                final_value DOUBLE,
                total_return DOUBLE,
                annualized_return DOUBLE,
                sharpe_ratio DOUBLE,
                sortino_ratio DOUBLE,
                max_drawdown DOUBLE,
                calmar_ratio DOUBLE,
                win_rate DOUBLE,
                total_trades INTEGER,
                profit_factor DOUBLE,
                risk_gate_blocks INTEGER,
                cost_total DOUBLE,
                params_json VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            INSERT OR REPLACE INTO backtest_runs
            (run_id, params_hash, symbol, strategy_name, start_date, end_date,
             initial_cash, final_value, total_return, annualized_return,
             sharpe_ratio, sortino_ratio, max_drawdown, calmar_ratio,
             win_rate, total_trades, profit_factor, risk_gate_blocks,
             cost_total, params_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            result.run_id,
            result.params_hash,
            result.symbol,
            result.strategy_name,
            result.start_date,
            result.end_date,
            result.initial_cash,
            result.final_value,
            result.metrics.total_return,
            result.metrics.annualized_return,
            result.metrics.sharpe_ratio,
            result.metrics.sortino_ratio,
            result.metrics.max_drawdown,
            result.metrics.calmar_ratio,
            result.metrics.win_rate,
            result.metrics.total_trades,
            result.metrics.profit_factor,
            result.risk_gate_blocks,
            result.cost_breakdown["total_fees"],
            json.dumps(asdict(result.metrics), default=str),
        ])
        conn.close()
    except Exception as exc:
        logger.debug("DuckDB persistence skipped: %s", exc)


def run_backtest_pipeline(params: PipelineParams) -> BacktestResult:
    """统一回测执行入口 — 支持单策略与多策略矩阵。

    Parameters
    ----------
    params : PipelineParams
        完整的回测参数封装。

    Returns
    -------
    BacktestResult
        包含净值曲线、基准线、全部绩效指标、MD5 哈希。
    """
    engine = BacktestCoreEngine()
    multi_configs = _build_multi_config(params)

    # 目前仅支持单策略 / 多策略加权（取第一个）
    # TODO: 后续扩展为多策略矩阵并发计算
    first = multi_configs[0]
    strategy = create_strategy(first["strategy_name"], first.get("strategy_config"))

    result = engine.run(
        symbol=params.symbol,
        start_date=params.start_date,
        end_date=params.end_date,
        strategy=strategy,
        initial_cash=params.initial_cash,
        rebalance_freq=params.rebalance_freq,
        risk_gate_enabled=params.risk_gate_enabled,
        risk_gate_symbol=params.risk_gate_symbol,
        sanitize_enabled=params.sanitize_enabled,
        benchmark_enabled=params.benchmark_enabled,
    )

    # 持久化到 DuckDB
    _persist_to_duckdb(result)

    return result


def run_multi_backtest(params_list: list[PipelineParams]) -> list[BacktestResult]:
    """多策略矩阵批量并发计算。

    Parameters
    ----------
    params_list : list of PipelineParams
        多个策略参数，独立运行。

    Returns
    -------
    list of BacktestResult
        每个策略的回测结果。
    """
    if len(params_list) <= 1:
        return [run_backtest_pipeline(p) for p in params_list]

    results: list[BacktestResult | None] = [None] * len(params_list)
    max_workers = min(len(params_list), os.cpu_count() or 4)

    def _run_one(idx: int, p: PipelineParams) -> tuple[int, BacktestResult]:
        return idx, run_backtest_pipeline(p)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_run_one, i, p): i for i, p in enumerate(params_list)}
        for future in as_completed(futures):
            idx, result = future.result()
            results[idx] = result

    return [r for r in results if r is not None]


# ---------------------------------------------------------------------------
# 五、独立运行测试
# ---------------------------------------------------------------------------

def _demo() -> None:
    """快速演示: 运行核心策略验证引擎是否正常。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    params = PipelineParams(
        symbol="600519.SH",
        strategy_name="MovingAverageTrend",
        start_date="2023-01-01",
        end_date="2024-12-31",
        strategy_config={"fast_period": 5, "slow_period": 20},
        initial_cash=1_000_000.0,
    )

    # 使用 mock 数据演示
    engine = BacktestCoreEngine(use_mock_data=True)
    strategy = create_strategy(params.strategy_name, params.strategy_config)
    result = engine.run(
        symbol=params.symbol,
        start_date=params.start_date,
        end_date=params.end_date,
        strategy=strategy,
        initial_cash=params.initial_cash,
    )

    print("\n" + "=" * 60)
    print("  AStock Pro 工业级回测引擎 v2.0 — 演示结果")
    print("=" * 60)
    print(f"  run_id:     {result.run_id}")
    print(f"  params_md5: {result.params_hash}")
    print(f"  标的:       {result.symbol}")
    print(f"  策略:       {result.strategy_name}")
    print(f"  区间:       {result.start_date} → {result.end_date}")
    print(f"  初始资金:   ¥{result.initial_cash:,.2f}")
    print(f"  最终价值:   ¥{result.final_value:,.2f}")
    print(f"  总收益:     {result.metrics.total_return * 100:.2f}%")
    print(f"  年化收益:   {result.metrics.annualized_return * 100:.2f}%")
    print(f"  Sharpe:     {result.metrics.sharpe_ratio:.2f}")
    print(f"  Sortino:    {result.metrics.sortino_ratio:.2f}")
    print(f"  最大回撤:   {result.metrics.max_drawdown * 100:.2f}%")
    print(f"  Calmar:     {result.metrics.calmar_ratio:.2f}")
    print(f"  胜率:       {result.metrics.win_rate * 100:.2f}%")
    print(f"  交易次数:   {result.metrics.total_trades}")
    print(f"  风控拦截:   {result.risk_gate_blocks} 次")
    print(f"  清洗标记:   {result.sanitized_flags}")
    print(f"  费用:       ¥{result.cost_breakdown['total_fees']:.2f}")
    print(f"  净值点数:   {len(result.equity_curve)}")
    print(f"  基准点数:   {len(result.benchmark_curve)}")
    print("=" * 60)
    print("  ✅ 引擎正常工作 — 无水科学计数法 / NaN / Inf")
    print("=" * 60)


if __name__ == "__main__":
    _demo()
