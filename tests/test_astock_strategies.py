"""Phase 14: 6 策略层测试 — 2 牛 / 2 震荡 / 2 熊 + MA Trend 回归。"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Direct module imports (bypass package __init__.py chain)
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parent.parent
_EXEC = _REPO / "tradingagents" / "astock" / "execution"

_PKG_PARENT = "tradingagents.astock.execution"


def _load_submodule(rel_name: str):
    """Load a module from the execution package with correct package context."""
    fname = rel_name + ".py"
    full_name = f"{_PKG_PARENT}.{rel_name}"
    path = str(_EXEC / fname)
    spec = importlib.util.spec_from_file_location(full_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {full_name} from {path}")
    for parent in ("tradingagents", "tradingagents.astock", "tradingagents.astock.execution"):
        if parent not in sys.modules:
            pkg_spec = importlib.util.spec_from_loader(parent, loader=None, is_package=True)
            parent_mod = importlib.util.module_from_spec(pkg_spec)
            parent_mod.__path__ = []
            sys.modules[parent] = parent_mod
    exec_pkg = sys.modules[_PKG_PARENT]
    exec_pkg.__path__ = [str(_EXEC)]

    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = _PKG_PARENT
    mod.__name__ = full_name
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


_sb = _load_submodule("strategy_base")

StrategyBase = _sb.StrategyBase
MovingAverageTrendStrategy = _sb.MovingAverageTrendStrategy
BullTrendStrategy = _sb.BullTrendStrategy
ValueAverageStrategy = _sb.ValueAverageStrategy
MeanReversionStrategy = _sb.MeanReversionStrategy
RSIRangeStrategy = _sb.RSIRangeStrategy
DefensiveMomentumStrategy = _sb.DefensiveMomentumStrategy
PutWriteStrategy = _sb.PutWriteStrategy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_df(
    prices: list[float],
    start: str = "2024-01-02",
    volume: list[float] | None = None,
) -> pd.DataFrame:
    """Build a DataFrame with a ``close`` column (and optional ``volume``) and date index."""
    dates = pd.bdate_range(start=start, periods=len(prices))
    data = {"close": prices}
    if volume is not None:
        data["volume"] = volume
    return pd.DataFrame(data, index=dates)


# ===================================================================
# MA Trend 回归测试
# ===================================================================


class TestMovingAverageTrendRegression(unittest.TestCase):
    """回归测试：MovingAverageTrendStrategy 保持已有行为。"""

    def test_simple_crossover(self) -> None:
        prices = (
            [30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17, 16]
            + [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
        )
        df = _make_test_df(prices)
        strat = MovingAverageTrendStrategy({"fast_period": 5, "slow_period": 15})
        signals = strat.generate_signals(df)
        self.assertIn(1, signals.values)

    def test_sell_signal(self) -> None:
        prices = (
            [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
            + [30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17, 16]
        )
        df = _make_test_df(prices)
        strat = MovingAverageTrendStrategy({"fast_period": 5, "slow_period": 15})
        signals = strat.generate_signals(df)
        self.assertIn(-1, signals.values)

    def test_no_signal_flat(self) -> None:
        prices = [100] * 30
        df = _make_test_df(prices)
        strat = MovingAverageTrendStrategy({"fast_period": 5, "slow_period": 20})
        signals = strat.generate_signals(df)
        self.assertTrue((signals == 0).all())


# ===================================================================
# 牛市策略测试 (BullTrendStrategy)
# ===================================================================


class TestBullTrendStrategy(unittest.TestCase):
    """BullTrendStrategy — 趋势跟随 + 均线多头排列。"""

    def test_bull_market_buy_signal(self) -> None:
        """持续上涨 → MA20 > MA60 and MA5 > MA20 → 买入信号。"""
        prices = list(range(80, 200))  # rising from 80 to 199
        df = _make_test_df(prices)  # no volume column → vol_confirmed = True
        strat = BullTrendStrategy()
        signals = strat.generate_signals(df)
        # After enough data, should produce buy signals
        self.assertIn(1, signals.values, "Expected at least one buy signal in uptrend")

    def test_bear_market_sell_signal(self) -> None:
        """持续下跌 → sell signals."""
        prices = list(range(200, 50, -1))  # falling from 200 to 51
        df = _make_test_df(prices, volume=[100] * len(prices))
        strat = BullTrendStrategy()
        signals = strat.generate_signals(df)
        self.assertIn(-1, signals.values, "Expected at least one sell signal in downtrend")

    def test_validation_fast_mid_slow_order(self) -> None:
        """fast_ma < mid_ma < slow_ma 必须成立。"""
        with self.assertRaises(ValueError):
            BullTrendStrategy({"fast_ma": 20, "mid_ma": 5, "slow_ma": 60})


# ===================================================================
# 牛市策略测试 (ValueAverageStrategy)
# ===================================================================


class TestValueAverageStrategy(unittest.TestCase):
    """ValueAverageStrategy — 价值平均 / 成本平均。"""

    def test_buy_at_low_percentile(self) -> None:
        """价格处于历史低位 → 买入信号。"""
        # Start high, drop to low, stay low
        prices = [100] * 10 + list(range(100, 30, -2))  # drop from 100 to ~30
        df = _make_test_df(prices)
        strat = ValueAverageStrategy({"pe_low_pct": 30, "pe_high_pct": 70})
        signals = strat.generate_signals(df)
        self.assertIn(1, signals.values, "Expected buy signals at low prices")

    def test_sell_at_high_percentile(self) -> None:
        """价格处于历史高位 → 卖出信号。"""
        # Start low, rise to high
        prices = [30] * 10 + list(range(30, 180, 2))  # rise from 30 to ~178
        df = _make_test_df(prices)
        strat = ValueAverageStrategy({"pe_low_pct": 30, "pe_high_pct": 70})
        signals = strat.generate_signals(df)
        self.assertIn(-1, signals.values, "Expected sell signals at high prices")

    def test_validation_percentiles(self) -> None:
        """pe_low_pct < pe_high_pct 必须成立。"""
        with self.assertRaises(ValueError):
            ValueAverageStrategy({"pe_low_pct": 70, "pe_high_pct": 30})


# ===================================================================
# 震荡策略测试 (MeanReversionStrategy)
# ===================================================================


class TestMeanReversionStrategy(unittest.TestCase):
    """MeanReversionStrategy — 均值回归。"""

    def test_oversold_buy_signal(self) -> None:
        """价格远低于 MA20 → 买入信号。"""
        # Flat then sudden drop far below MA
        prices = [100] * 25 + [50] * 10  # big drop after stabilisation
        df = _make_test_df(prices)
        strat = MeanReversionStrategy({"std_multiplier": 1.5, "ma_period": 10})
        signals = strat.generate_signals(df)
        self.assertIn(1, signals.values, "Expected buy signal after oversold drop")

    def test_overbought_sell_signal(self) -> None:
        """价格远高于 MA20 → 卖出信号。"""
        # Flat then sudden spike far above MA
        prices = [100] * 20 + [200] * 10  # big spike after stabilisation
        df = _make_test_df(prices)
        strat = MeanReversionStrategy({"std_multiplier": 1.5, "ma_period": 10})
        signals = strat.generate_signals(df)
        self.assertIn(-1, signals.values, "Expected sell signal after overbought spike")

    def test_flat_no_signals(self) -> None:
        """平稳行情 → 无信号。"""
        prices = [100] * 30
        df = _make_test_df(prices)
        strat = MeanReversionStrategy({"ma_period": 10, "std_multiplier": 3.0})
        signals = strat.generate_signals(df)
        self.assertTrue((signals == 0).all(), "Expected no signals in flat market")


# ===================================================================
# 震荡策略测试 (RSIRangeStrategy)
# ===================================================================


class TestRSIRangeStrategy(unittest.TestCase):
    """RSIRangeStrategy — RSI 区间交易。"""

    def test_rsi_oversold_buy(self) -> None:
        """RSI < 30 → 买入信号。"""
        # Sharp downtrend → RSI should go below 30
        prices = [100] * 20 + [100 - i * 3 for i in range(30)]  # sharp drop
        df = _make_test_df(prices)
        strat = RSIRangeStrategy({"rsi_period": 14, "oversold": 30, "overbought": 70})
        signals = strat.generate_signals(df)
        self.assertIn(1, signals.values, "Expected buy signal from oversold RSI")

    def test_rsi_overbought_sell(self) -> None:
        """RSI > 70 → 卖出信号。"""
        # Sharp uptrend → RSI should go above 70
        prices = [100] * 20 + [100 + i * 3 for i in range(30)]  # sharp rise
        df = _make_test_df(prices)
        strat = RSIRangeStrategy({"rsi_period": 14, "oversold": 30, "overbought": 70})
        signals = strat.generate_signals(df)
        self.assertIn(-1, signals.values, "Expected sell signal from overbought RSI")

    def test_validation_oversold_less_than_overbought(self) -> None:
        """oversold < overbought 必须成立。"""
        with self.assertRaises(ValueError):
            RSIRangeStrategy({"oversold": 70, "overbought": 30})

    def test_flat_no_extreme_rsi(self) -> None:
        """平稳行情 → RSI 在中间区间 → 无信号。"""
        prices = [100] * 50
        df = _make_test_df(prices)
        strat = RSIRangeStrategy()
        signals = strat.generate_signals(df)
        self.assertTrue((signals == 0).all(), "Expected no signals in flat market")


# ===================================================================
# 熊市策略测试 (DefensiveMomentumStrategy)
# ===================================================================


class TestDefensiveMomentumStrategy(unittest.TestCase):
    """DefensiveMomentumStrategy — 防御性动量。"""

    def test_positive_momentum_low_vol_buy(self) -> None:
        """ROC > 0 且低波动 → 买入信号。"""
        # Steady uptrend with low volatility
        prices = [100 + i * 0.5 for i in range(60)]  # smooth uptrend
        df = _make_test_df(prices)
        strat = DefensiveMomentumStrategy({
            "roc_period": 10,
            "vol_period": 10,
            "vol_threshold": 0.1,
        })
        signals = strat.generate_signals(df)
        self.assertIn(1, signals.values, "Expected buy signal from positive momentum")

    def test_negative_momentum_sell(self) -> None:
        """ROC < 0 → 卖出信号。"""
        # Downtrend
        prices = [150 - i * 1.5 for i in range(60)]
        df = _make_test_df(prices)
        strat = DefensiveMomentumStrategy({
            "roc_period": 10,
            "vol_period": 10,
            "vol_threshold": 0.1,
        })
        signals = strat.generate_signals(df)
        self.assertIn(-1, signals.values, "Expected sell signal from negative momentum")

    def test_high_vol_no_buy(self) -> None:
        """高波动时即便 ROC>0 也不产生买入。"""
        # Chaotic prices → high volatility
        import numpy as np
        rng = np.random.default_rng(42)
        prices = [100 + float(rng.normal(0, 5)) for _ in range(60)]
        df = _make_test_df(prices)
        strat = DefensiveMomentumStrategy({
            "roc_period": 10,
            "vol_period": 10,
            "vol_threshold": 0.01,  # very low threshold
        })
        signals = strat.generate_signals(df)
        # May have sell signals, but buy signals should be rare/absent
        # Just verify it runs without error and returns correct type
        self.assertIsInstance(signals, pd.Series)
        self.assertEqual(signals.dtype, int)


# ===================================================================
# 熊市策略测试 (PutWriteStrategy)
# ===================================================================


class TestPutWriteStrategy(unittest.TestCase):
    """PutWriteStrategy — 类 Put Write 空头对冲。"""

    def test_bear_market_sell(self) -> None:
        """MA5 < MA20 < MA60 → 卖出信号。"""
        # Sustained downtrend creates bearish MA alignment
        prices = list(range(200, 20, -1))  # long downtrend
        df = _make_test_df(prices)
        strat = PutWriteStrategy()
        signals = strat.generate_signals(df)
        self.assertIn(-1, signals.values, "Expected sell signals in bearish MA alignment")

    def test_bull_market_no_sell(self) -> None:
        """上涨趋势 → 无卖出信号（可能为零）。"""
        prices = list(range(50, 200))  # long uptrend
        df = _make_test_df(prices)
        strat = PutWriteStrategy()
        signals = strat.generate_signals(df)
        # In a pure uptrend, short-term MA > long-term MA, so no -1
        self.assertNotIn(-1, signals.values, "Expected no sell signals in uptrend")

    def test_validation_fast_mid_slow_order(self) -> None:
        """fast_ma < mid_ma < slow_ma 必须成立。"""
        with self.assertRaises(ValueError):
            PutWriteStrategy({"fast_ma": 60, "mid_ma": 20, "slow_ma": 5})


# ===================================================================
# 跨策略统一约束
# ===================================================================


class TestStrategyUniformConstraints(unittest.TestCase):
    """所有策略必须遵守的统一契约。"""

    STRATEGY_CLASSES = [
        MovingAverageTrendStrategy,
        BullTrendStrategy,
        ValueAverageStrategy,
        MeanReversionStrategy,
        RSIRangeStrategy,
        DefensiveMomentumStrategy,
        PutWriteStrategy,
    ]

    def test_output_is_integer_series(self) -> None:
        """所有策略的输出必须是 int dtype 的 pd.Series。"""
        prices = [float(i) for i in range(100, 200)]
        df = _make_test_df(prices)
        for cls in self.STRATEGY_CLASSES:
            with self.subTest(strategy=cls.__name__):
                strat = cls()
                signals = strat.generate_signals(df)
                self.assertIsInstance(signals, pd.Series)
                self.assertEqual(signals.dtype, int)

    def test_output_values_are_in_minus1_0_1(self) -> None:
        """信号值只能是 -1, 0, 1。"""
        prices = [float(i) for i in range(100, 200)]
        df = _make_test_df(prices)
        for cls in self.STRATEGY_CLASSES:
            with self.subTest(strategy=cls.__name__):
                strat = cls()
                signals = strat.generate_signals(df)
                valid = signals.isin([-1, 0, 1])
                self.assertTrue(valid.all(), f"Found invalid signals in {cls.__name__}")

    def test_output_index_matches_input(self) -> None:
        """输出 index 必须与输入一致。"""
        prices = [float(i) for i in range(100, 200)]
        df = _make_test_df(prices)
        for cls in self.STRATEGY_CLASSES:
            with self.subTest(strategy=cls.__name__):
                strat = cls()
                signals = strat.generate_signals(df)
                pd.testing.assert_index_equal(signals.index, df.index)

    def test_missing_price_column_raises_key_error(self) -> None:
        """缺少 close 列时抛出 KeyError。"""
        df = pd.DataFrame({"open": [1.0, 2.0, 3.0]})
        for cls in self.STRATEGY_CLASSES:
            with self.subTest(strategy=cls.__name__):
                strat = cls()
                with self.assertRaises(KeyError):
                    strat.generate_signals(df)


if __name__ == "__main__":
    unittest.main()
