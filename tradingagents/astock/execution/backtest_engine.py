"""Backtest engine for A-share strategies.

Uses ``AStockDataFacade`` for real data when available, falling back
to deterministic mock OHLCV data for testability.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

import pandas as pd
from pydantic import BaseModel, Field

from .fee_model import AStockFeeConfig, calculate_fees
from .metrics import summarize_metrics
from .strategy_base import StrategyBase

EXECUTION_SIGNAL: str = "ResearchOnly"

# ---------------------------------------------------------------------------
# Backtest data assumptions
# ---------------------------------------------------------------------------


class AdjustmentMethod(str, Enum):
    """复权方法"""
    NONE = "none"          # 未复权
    FORWARD = "forward"    # 前复权
    BACKWARD = "backward"  # 后复权


class CostModel(str, Enum):
    """成本模型"""
    DEFAULT = "default"       # 默认（千分之一印花税 + 万分之一佣金）
    CUSTOM = "custom"         # 自定义费率
    ZERO = "zero"             # 零成本（仅 mock/测试）


class SettlementConstraint(str, Enum):
    """成交约束"""
    T_PLUS_0 = "t+0"        # T+0
    T_PLUS_1 = "t+1"        # T+1（A 股默认）
    T_PLUS_0_TREASURY = "t+0_treasury"  # T+0 国债


class BacktestDataAssumption(BaseModel):
    """回测数据假设 — 说明回测使用的数据配置和约束。

    Attributes
    ----------
    adjustment : AdjustmentMethod
        复权方法（默认 forward）。
    cost_model : CostModel
        成本模型（默认 default）。
    settlement : SettlementConstraint
        成交约束（默认 t+1）。
    slippage_bps : float
        滑点（基点，默认 0 = 无滑点）。
    sample_out : bool
        是否使用样本外数据（默认 False）。
    data_source : str
        数据来源描述（如 ``"duckdb_live"``, ``"mock_deterministic"``）。
    data_quality : str
        数据质量标签（如 ``"normal"``, ``"mock"``, ``"partial"``）。
    survivorship_bias_risk : bool
        是否存在幸存者偏差风险（默认 False）。
    look_ahead_bias_risk : bool
        是否存在前视偏差风险（默认 False）。
    notes : list[str]
        额外的假设说明。
    """

    adjustment: AdjustmentMethod = AdjustmentMethod.FORWARD
    cost_model: CostModel = CostModel.DEFAULT
    settlement: SettlementConstraint = SettlementConstraint.T_PLUS_1
    slippage_bps: float = 0.0
    sample_out: bool = False
    data_source: str = ""
    data_quality: str = "normal"
    survivorship_bias_risk: bool = False
    look_ahead_bias_risk: bool = False
    notes: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "adjustment": self.adjustment.value,
            "cost_model": self.cost_model.value,
            "settlement": self.settlement.value,
            "slippage_bps": self.slippage_bps,
            "sample_out": self.sample_out,
            "data_source": self.data_source,
            "data_quality": self.data_quality,
            "survivorship_bias_risk": self.survivorship_bias_risk,
            "look_ahead_bias_risk": self.look_ahead_bias_risk,
            "notes": list(self.notes),
        }

    @classmethod
    def mock(cls) -> BacktestDataAssumption:
        """Pre-built mock/test assumption."""
        return cls(
            adjustment=AdjustmentMethod.FORWARD,
            cost_model=CostModel.ZERO,
            settlement=SettlementConstraint.T_PLUS_1,
            slippage_bps=0.0,
            sample_out=False,
            data_source="mock_deterministic",
            data_quality="mock",
            survivorship_bias_risk=True,
            look_ahead_bias_risk=False,
            notes=["Mock data — not suitable for live decisions"],
        )


# ---------------------------------------------------------------------------
# BacktestResult model
# ---------------------------------------------------------------------------


class BacktestResult(BaseModel):
    """Result of a completed backtest run.

    Attributes
    ----------
    symbol : str
    strategy_name : str
    start_date : str
    end_date : str
    total_return : float
    annualized_return : float
    sharpe_ratio : float
    max_drawdown : float
    win_rate : float
    total_trades : int
    periods : list[dict]
        Per-period account snapshots (beginning portfolio value, signal,
        trade, ending value, fees).
    fee_config_used : dict
        Snapshot of the fee config used.
    execution_signal : str
        Always ``"ResearchOnly"``.
    """

    symbol: str
    strategy_name: str = ""
    start_date: str
    end_date: str
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    trades: list[dict] = Field(default_factory=list)
    periods: list[dict] = Field(default_factory=list)
    fee_config_used: dict = Field(default_factory=dict)
    execution_signal: str = EXECUTION_SIGNAL
    decision_scope: str = "backtest_only"
    run_id: str = ""
    data_assumption: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Mock data helper (for environments where AStockDataFacade is unavailable)
# ---------------------------------------------------------------------------

_MOCK_OHLCV: dict[str, list[dict]] = {}

_SYMBOLS_MOCKED: set[str] = set()


def _generate_mock_bars(
    symbol: str,
    start_date: str,
    end_date: str,
    *,
    base_price: float = 100.0,
    volatility: float = 0.01,
) -> list[dict]:
    """Deterministic OHLCV sequence for testing."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    bars: list[dict] = []
    price = base_price
    current = start
    while current <= end:
        if current.weekday() < 5:  # trading day
            change = price * volatility * (hash(f"{symbol}:{current}") % 200 - 100) / 100.0
            open_p = round(price, 2)
            close_p = round(price + change, 2)
            high_p = round(max(open_p, close_p) * (1 + abs(change) / price / 2), 2)
            low_p = round(min(open_p, close_p) * (1 - abs(change) / price / 2), 2)
            bar = {
                "date": current.strftime("%Y-%m-%d"),
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": 1000000,
            }
            bars.append(bar)
            price = close_p
        current += timedelta(days=1)

    _MOCK_OHLCV[symbol] = bars
    _SYMBOLS_MOCKED.add(symbol)
    return bars


# ---------------------------------------------------------------------------
# BacktestEngine
# ---------------------------------------------------------------------------


class BacktestEngine:
    """Period-based backtest engine for A-share strategies.

    Parameters
    ----------
    fee_config : AStockFeeConfig or None
        Custom fee configuration.  Falls back to defaults.
    """

    def __init__(self, fee_config: AStockFeeConfig | None = None, use_mock_data: bool = False) -> None:
        self.fee_config = fee_config or AStockFeeConfig()
        self._facade: Any = None  # lazy import
        self._use_mock_data = use_mock_data

    def _fetch_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch OHLCV data, falling back to mock data if facade unavailable."""
        # use_mock_data=True -> skip real data, go straight to mock
        if self._use_mock_data:
            return self._mock_fallback(symbol, start_date, end_date)

        # Try AStockDataFacade first (uses baostock as primary default)
        try:
            from tradingagents.astock.data_sources import AStockDataFacade

            if self._facade is None:
                self._facade = AStockDataFacade()
            response = self._facade.get_kline(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval="1d",
            )
            if response.status == "ok" and response.data and response.data.get("bars"):
                bars = response.data["bars"]
                df = pd.DataFrame(bars)
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date").sort_index()
                for col in ("open", "high", "low", "close", "volume"):
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                return df
        except Exception:
            pass

        # Fallback to mock data
        return self._mock_fallback(symbol, start_date, end_date)

    @staticmethod
    def _mock_fallback(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Generate mock OHLCV data for testing / fallback."""
        bars = _generate_mock_bars(symbol, start_date, end_date)
        df = pd.DataFrame(bars)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        for col in ("open", "high", "low", "close", "volume"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def run(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        strategy: StrategyBase,
        rebalance_freq: str = "M",
        *,
        initial_cash: float = 100000.0,
    ) -> BacktestResult:
        """Execute a single-symbol backtest.

        Parameters
        ----------
        symbol : str
            A-share symbol (e.g. ``"600519.SH"``).
        start_date : str
            Start date (``"YYYY-MM-DD"``).
        end_date : str
            End date (``"YYYY-MM-DD"``).
        strategy : StrategyBase
            Strategy instance.
        rebalance_freq : str
            Pandas offset alias for rebalance periods (default ``"M"`` =
            monthly).
        initial_cash : float
            Starting cash (default 100 000).

        Returns
        -------
        BacktestResult
        """
        df = self._fetch_data(symbol, start_date, end_date)
        if df.empty:
            return BacktestResult(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                fee_config_used={
                    "commission_rate": self.fee_config.commission_rate,
                    "stamp_tax_rate": self.fee_config.stamp_tax_rate,
                    "slippage_rate": self.fee_config.slippage_rate,
                    "min_commission": self.fee_config.min_commission,
                },
            )

        # ── Force date range slice ──
        df = df[(df.index >= pd.Timestamp(start_date)) & (df.index <= pd.Timestamp(end_date))]
        if df.empty:
            return BacktestResult(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                fee_config_used={
                    "commission_rate": self.fee_config.commission_rate,
                    "stamp_tax_rate": self.fee_config.stamp_tax_rate,
                    "slippage_rate": self.fee_config.slippage_rate,
                    "min_commission": self.fee_config.min_commission,
                },
            )

        # --- Group by rebalance periods ---
        periods = df.resample(rebalance_freq.replace("M", "ME"))
        cash = initial_cash
        shares = 0.0
        portfolio_values: list[float] = [initial_cash]
        dates: list[pd.Timestamp] = [df.index[0]]
        trades: list[dict] = []
        period_records: list[dict] = []

        for period_label, period_data in periods:
            if period_data.empty:
                continue
            # Get the last close of the period for signal generation
            close_at_end = float(period_data["close"].iloc[-1])

            # Generate signal from period data
            signal_series = strategy.generate_signals(period_data)
            # Take the last non-zero or most recent signal
            non_zero = signal_series[signal_series != 0]
            signal = int(non_zero.iloc[-1]) if not non_zero.empty else 0

            period_start_val = cash + shares * close_at_end

            if signal == 1 and cash > 0:
                # Buy: invest all cash minus fees
                max_shares = cash / close_at_end
                # Iteratively reduce shares until net_cost ≤ cash
                buy_shares = max_shares
                for _ in range(5):
                    fees = calculate_fees(close_at_end, buy_shares, is_buy=True, config=self.fee_config)
                    net_cost = buy_shares * close_at_end + fees["total"]
                    if net_cost <= cash:
                        break
                    buy_shares = (cash - fees.get("total", 0)) / close_at_end
                if buy_shares > 0.001:
                    fees = calculate_fees(close_at_end, buy_shares, is_buy=True, config=self.fee_config)
                    net_cost = buy_shares * close_at_end + fees["total"]
                    shares += buy_shares
                    cash -= net_cost
                    trades.append({
                        "date": str(period_data.index[-1].date()),
                        "type": "buy",
                        "price": close_at_end,
                        "shares": round(buy_shares, 4),
                        "fees": fees["total"],
                        "pnl": 0.0,
                    })
            elif signal == -1 and shares > 0:
                # Sell: liquidate all shares
                sell_value = shares * close_at_end
                fees = calculate_fees(close_at_end, shares, is_buy=False, config=self.fee_config)
                proceeds = sell_value - fees["total"]
                pnl = proceeds - (shares * close_at_end - sell_value)  # simplified P&L
                cash += proceeds
                trades.append({
                    "date": str(period_data.index[-1].date()),
                    "type": "sell",
                    "price": close_at_end,
                    "shares": round(shares, 4),
                    "fees": fees["total"],
                    "pnl": round(proceeds - (shares * close_at_end), 4),
                })
                shares = 0.0

            end_val = cash + shares * close_at_end
            portfolio_values.append(end_val)
            dates.append(period_data.index[-1])

            period_records.append({
                "period": str(period_label),
                "signal": signal,
                "start_value": round(period_start_val, 2),
                "end_value": round(end_val, 2),
                "close": close_at_end,
                "shares": round(shares, 4),
                "cash": round(cash, 2),
            })

        # Final valuation
        equity = pd.Series(portfolio_values, index=dates)

        # Compute metrics
        metrics = summarize_metrics(equity, trades)
        total_return = float(equity.iloc[-1] / equity.iloc[0] - 1)

        return BacktestResult(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            total_return=round(total_return, 6),
            annualized_return=metrics["annualized_return"],
            sharpe_ratio=metrics["sharpe_ratio"],
            max_drawdown=metrics["max_drawdown"],
            win_rate=metrics["win_rate"],
            total_trades=metrics["total_trades"],
            trades=trades,
            periods=period_records,
            fee_config_used={
                "commission_rate": self.fee_config.commission_rate,
                "stamp_tax_rate": self.fee_config.stamp_tax_rate,
                "slippage_rate": self.fee_config.slippage_rate,
                "min_commission": self.fee_config.min_commission,
            },
        )
