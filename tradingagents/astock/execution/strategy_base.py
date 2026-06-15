"""Strategy base class and simple moving-average trend strategy."""

from __future__ import annotations

from abc import ABC, abstractmethod

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


class MovingAverageTrendStrategy(StrategyBase):
    """Simple dual-moving-average trend-following strategy.

    Config keys (all optional):
        fast_period : int
            Fast MA window (default ``5``).
        slow_period : int
            Slow MA window (default ``20``).
        price_col : str
            Column in *data* used for MA calculation (default ``"close"``).

    Signal logic
        - Fast MA crosses **above** slow MA  →  ``+1`` (buy)
        - Fast MA crosses **below** slow MA  →  ``-1`` (sell)
        - Otherwise                          →  ``0``  (hold)
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.fast_period: int = int(self.config.get("fast_period", 5))
        self.slow_period: int = int(self.config.get("slow_period", 20))
        self.price_col: str = str(self.config.get("price_col", "close"))

        if self.fast_period >= self.slow_period:
            raise ValueError(
                f"fast_period ({self.fast_period}) must be < slow_period ({self.slow_period})"
            )

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        if self.price_col not in data.columns:
            raise KeyError(
                f"Column '{self.price_col}' not found in data; "
                f"available columns: {list(data.columns)}"
            )

        prices = data[self.price_col]
        fast_ma = prices.rolling(window=self.fast_period).mean()
        slow_ma = prices.rolling(window=self.slow_period).mean()

        # Crossover detection: previous state vs current state
        prev_fast = fast_ma.shift(1)
        prev_slow = slow_ma.shift(1)

        signals = pd.Series(0, index=data.index, dtype=int)

        # Build valid-mask: both MAs have non-NaN current *and* previous values
        valid = fast_ma.notna() & slow_ma.notna() & prev_fast.notna() & prev_slow.notna()

        # Buy when fast crosses above slow (or first time fast > slow after both MAs are available)
        buy_condition = (fast_ma > slow_ma) & (prev_fast <= prev_slow)
        # Also trigger buy on the *first* period where fast_ma > slow_ma
        # (handles NaN boundary — prev_slow is NaN, so normal check misses it)
        first_buy = (fast_ma > slow_ma) & prev_fast.notna() & prev_slow.isna()
        buy_mask = valid & buy_condition
        signals[buy_mask] = 1
        # Apply first-buy as an independent condition (not NaN-gated)
        signals[first_buy] = 1

        # Sell when fast crosses below slow (or first time fast < slow after both MAs available)
        sell_condition = (fast_ma < slow_ma) & (prev_fast >= prev_slow)
        first_sell = (fast_ma < slow_ma) & prev_fast.notna() & prev_slow.isna()
        sell_mask = valid & sell_condition
        signals[sell_mask] = -1
        signals[first_sell] = -1

        # NaN regions (before both MAs are available) stay as 0
        signals = signals.fillna(0).astype(int)
        return signals


# ===================================================================
# 牛市策略 (2)
# ===================================================================


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

        signals = signals.fillna(0).astype(int)
        return signals


class ValueAverageStrategy(StrategyBase):
    """价值平均 / 成本平均策略 — 牛市策略。

    当价格低于估值区间下限时买入，高于上限时卖出。
    使用 PE/PB 历史分位数判断估值区间（模拟）。

    Config keys (all optional):
        pe_low_pct  : int  低估分位 (default ``30``)
        pe_high_pct : int  高估分位 (default ``70``)
        price_col   : str  价格列名 (default ``\"close\"``)

    Signal logic
        - 价格低于估值区间下限 → ``+1`` (买入)
        - 价格高于估值区间上限 → ``-1`` (卖出)
        - 区间内 → ``0`` (持有)

    Note
    ----
    由于 K-line 数据不含 PE/PB，这里用价格相对于历史价格的
    百分位来模拟估值区间。
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.pe_low_pct: int = int(self.config.get("pe_low_pct", 30))
        self.pe_high_pct: int = int(self.config.get("pe_high_pct", 70))
        self.price_col: str = str(self.config.get("price_col", "close"))

        if not (0 < self.pe_low_pct < self.pe_high_pct < 100):
            raise ValueError(
                f"Expected 0 < pe_low_pct ({self.pe_low_pct}) < "
                f"pe_high_pct ({self.pe_high_pct}) < 100"
            )

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        if self.price_col not in data.columns:
            raise KeyError(
                f"Column '{self.price_col}' not found; available: {list(data.columns)}"
            )

        prices = data[self.price_col]
        # Use expanding window to simulate historical percentile
        low_threshold = prices.expanding().quantile(self.pe_low_pct / 100.0)
        high_threshold = prices.expanding().quantile(self.pe_high_pct / 100.0)

        signals = pd.Series(0, index=data.index, dtype=int)

        # Need at least some data for percentiles to stabilise
        sufficient = prices.expanding().count() >= 20

        buy_mask = sufficient & (prices <= low_threshold)
        sell_mask = sufficient & (prices >= high_threshold)

        signals[buy_mask] = 1
        signals[sell_mask] = -1

        signals = signals.fillna(0).astype(int)
        return signals


# ===================================================================
# 震荡策略 (2)
# ===================================================================


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

        signals = signals.fillna(0).astype(int)
        return signals


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

        signals = signals.fillna(0).astype(int)
        return signals


# ===================================================================
# 熊市策略 (2)
# ===================================================================


class DefensiveMomentumStrategy(StrategyBase):
    """防御性动量策略 — 熊市策略。

    在市场下行时寻找相对强势的标的。
    使用价格动量（ROC）和低波动率筛选，信号偏保守。

    Config keys (all optional):
        roc_period    : int    ROC 计算窗口 (default ``20``)
        vol_period    : int    波动率计算窗口 (default ``20``)
        vol_threshold : float  日波动率上限 (default ``0.02``, 即 2%)
        price_col     : str    价格列名 (default ``\"close\"``)

    Signal logic
        - ROC > 0 **且** 波动率 ≤ vol_threshold → ``+1`` (买入 — 强势且低波动)
        - ROC < 0 → ``-1`` (卖出 — 动量转负)
        - 其他 → ``0`` (持有)
    """

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config or {})
        self.roc_period: int = int(self.config.get("roc_period", 20))
        self.vol_period: int = int(self.config.get("vol_period", 20))
        self.vol_threshold: float = float(self.config.get("vol_threshold", 0.02))
        self.price_col: str = str(self.config.get("price_col", "close"))

        if self.roc_period < 1:
            raise ValueError(f"roc_period must be >= 1, got {self.roc_period}")

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        if self.price_col not in data.columns:
            raise KeyError(
                f"Column '{self.price_col}' not found; available: {list(data.columns)}"
            )

        prices = data[self.price_col]

        # Rate of Change
        roc = prices.pct_change(periods=self.roc_period)

        # Daily returns for volatility
        daily_ret = prices.pct_change()
        volatility = daily_ret.rolling(window=self.vol_period).std(ddof=0)

        signals = pd.Series(0, index=data.index, dtype=int)

        valid = roc.notna() & volatility.notna()

        # Buy: positive momentum + low volatility
        buy_mask = valid & (roc > 0) & (volatility <= self.vol_threshold)
        # Sell: negative momentum
        sell_mask = valid & (roc < 0)

        signals[buy_mask] = 1
        signals[sell_mask] = -1

        signals = signals.fillna(0).astype(int)
        return signals


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

        signals = signals.fillna(0).astype(int)
        return signals


# ===================================================================
# 新策略：MACD 趋势跟踪
# ===================================================================


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

        signals = signals.fillna(0).astype(int)
        return signals


# ===================================================================
# 新策略：Bollinger Bands 均值回归
# ===================================================================


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

        signals = signals.fillna(0).astype(int)
        return signals


# ===================================================================
# 新策略：网格交易
# ===================================================================


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
        signals = signals.fillna(0).astype(int)
        return signals
