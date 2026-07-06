"""Shared helpers for the backtest API routes."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from typing import Any

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_STRATEGY_REGISTRY: dict[str, type] | None = None


def get_strategy_registry() -> dict[str, type]:
    """Lazy-build the strategy registry on first use."""
    global _STRATEGY_REGISTRY
    if _STRATEGY_REGISTRY is not None:
        return _STRATEGY_REGISTRY

    from tradingagents.astock.execution.strategy_base import (
        BollingerBandsReversionStrategy,
        BullTrendStrategy,
        DefensiveMomentumStrategy,
        GridTradingStrategy,
        MACDTrendStrategy,
        MeanReversionStrategy,
        MomentumRotationStrategy,
        MovingAverageTrendStrategy,
        PutWriteStrategy,
        RSIRangeStrategy,
        StockFlow,
        ValueAverageStrategy,
    )

    _STRATEGY_REGISTRY = {
        "MovingAverageTrend": MovingAverageTrendStrategy,
        "BullTrend": BullTrendStrategy,
        "ValueAverage": ValueAverageStrategy,
        "MeanReversion": MeanReversionStrategy,
        "RSIRange": RSIRangeStrategy,
        "DefensiveMomentum": DefensiveMomentumStrategy,
        "PutWrite": PutWriteStrategy,
        "MACDTrend": MACDTrendStrategy,
        "BollingerBands": BollingerBandsReversionStrategy,
        "GridTrading": GridTradingStrategy,
        "MomentumRotation": MomentumRotationStrategy,
        "StockFlow": StockFlow,
    }
    return _STRATEGY_REGISTRY


def get_optimizer_cls() -> Any:
    from tradingagents.astock.execution.optimizer import StrategyOptimizer

    return StrategyOptimizer


def create_backtest_engine(use_mock_data: bool = False) -> Any:
    from tradingagents.astock.execution.backtest_engine import BacktestEngine

    return BacktestEngine(use_mock_data=use_mock_data)


def sanitize_nan(records: list[dict[str, Any]]) -> None:
    """Replace NaN/Inf with None in-place for valid JSON."""
    for record in records:
        for key, value in record.items():
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                record[key] = None
            elif isinstance(value, datetime):
                record[key] = value.strftime("%Y-%m-%d")
            elif hasattr(value, "isoformat"):
                record[key] = value.isoformat()


def sanitize_metrics(record: dict[str, Any]) -> dict[str, Any]:
    """Deep-clean a single backtest result dict."""
    for key in (
        "total_return",
        "annualized_return",
        "sharpe_ratio",
        "max_drawdown",
        "win_rate",
        "total_trades",
    ):
        value = record.get(key)
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            record[key] = None
    return record


def validate_date(date_label: str, date_value: str) -> None:
    if not DATE_RE.match(date_value):
        raise ValueError(f"{date_label} date must be YYYY-MM-DD, got '{date_value}'")
    try:
        datetime.strptime(date_value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{date_label} date is invalid: '{date_value}'") from exc


def validate_date_range(
    start_label: str,
    start_date: str,
    end_label: str,
    end_date: str,
) -> None:
    validate_date(start_label, start_date)
    validate_date(end_label, end_date)
    if start_date >= end_date:
        raise ValueError(f"{start_label} must be before {end_label}")


def expand_params_json_rows(df: Any) -> list[dict[str, Any]]:
    rows = df.to_dict(orient="records") if df is not None and not df.empty else []
    sanitize_nan(rows)
    for row in rows:
        if isinstance(row.get("params_json"), str):
            try:
                row["params"] = json.loads(row["params_json"])
            except (json.JSONDecodeError, TypeError):
                row["params"] = {}
            del row["params_json"]
    return rows


def build_equity_curve(periods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"period": period["period"], "value": period["end_value"]} for period in periods]


def build_period_returns(periods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    returns = []
    prev_val = None
    for period in periods:
        value = period["end_value"]
        if prev_val is not None and prev_val > 0:
            ret = (value - prev_val) / prev_val
            returns.append({"period": period["period"], "return": round(ret, 6)})
        prev_val = value
    return returns


def extract_signal_trades(periods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trades = []
    for period in periods:
        if period.get("signal", 0) != 0:
            trades.append(
                {
                    "period": period["period"],
                    "signal": period["signal"],
                    "value": period["end_value"],
                }
            )
    return trades
