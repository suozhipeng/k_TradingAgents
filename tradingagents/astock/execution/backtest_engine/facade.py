"""Backtest facade bridging modules-style params to the execution engine.

Returns legacy ``modules.backtest_engine.BacktestResult`` objects so existing
CLI / callers keep their output shape unchanged.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from modules.backtest_engine import BacktestResult as ModulesBacktestResultDC
    from modules.backtest_engine import PipelineParams

logger = logging.getLogger(__name__)

# ── 策略名映射：modules 名 → execution 类名 ─────────────────────────

_MODULES_TO_EXEC_STRATEGY_MAP: dict[str, str | None] = {
    "MovingAverageTrend": "MovingAverageTrendStrategy",
    "BullTrend": "BullTrendStrategy",
    "MeanReversion": "MeanReversionStrategy",
    "RSIRange": "RSIRangeStrategy",
    "MACDTrend": "MACDTrendStrategy",
    "BollingerBands": "BollingerBandsReversionStrategy",
    "DefensiveMomentum": "DefensiveMomentumStrategy",
    "PutWrite": "PutWriteStrategy",
    "ValueAverage": "ValueAverageStrategy",
    # modules 独有（无 execution 等价物）
    "AbsoluteLimitUpScore": None,
    "LeadingSectorMomentum": None,
}


def _build_execution_strategy(strategy_name: str, config: dict | None):
    """构建 execution 版策略实例。"""
    from tradingagents.astock.execution import strategy_base as sb

    class_name = _MODULES_TO_EXEC_STRATEGY_MAP.get(strategy_name)
    if class_name is None:
        raise ValueError(f"No execution engine equivalent for {strategy_name}")

    cls = getattr(sb, class_name, None)
    if cls is None:
        raise ValueError(f"Execution strategy class not found: {class_name}")

    return cls(config or {})


def _legacy_backtest_exports():
    """Load legacy modules.backtest_engine symbols lazily."""
    from modules.backtest_engine import (
        BacktestMetrics,
        BacktestResult as ModulesBacktestResultDC,
        _persist_to_duckdb,
        _run_backtest_pipeline_legacy,
    )

    return (
        BacktestMetrics,
        ModulesBacktestResultDC,
        _persist_to_duckdb,
        _run_backtest_pipeline_legacy,
    )


def _use_modules_fallback(params: PipelineParams) -> bool:
    """判断是否应 fallback 到 modules 版引擎。"""
    return _MODULES_TO_EXEC_STRATEGY_MAP.get(params.strategy_name) is None


def _convert_result_to_modules(
    exec_result: Any,
    strategy_name: str,
    symbol: str,
    start_date: str,
    end_date: str,
    initial_cash: float,
    run_id: str,
) -> ModulesBacktestResultDC:
    """将 execution 版 BacktestResult 转换为 modules 版 BacktestResult 格式。"""
    BacktestMetrics, ModulesBacktestResultDC, _, _ = _legacy_backtest_exports()
    from tradingagents.astock.execution.backtest_engine.models import BacktestResult as ExecBacktestResult

    assert isinstance(exec_result, ExecBacktestResult)

    # 提取指标
    metrics = BacktestMetrics(
        total_return=getattr(exec_result, "total_return", 0.0),
        annualized_return=getattr(exec_result, "annualized_return", 0.0),
        sharpe_ratio=getattr(exec_result, "sharpe_ratio", 0.0),
        sortino_ratio=0.0,  # execution 版无此指标
        max_drawdown=getattr(exec_result, "max_drawdown", 0.0),
        calmar_ratio=0.0,  # execution 版无此指标
        win_rate=getattr(exec_result, "win_rate", 0.0),
        total_trades=getattr(exec_result, "total_trades", 0),
        avg_holding_days=0.0,  # execution 版无此指标
        profit_factor=0.0,  # execution 版无此指标
        benchmark_return=getattr(exec_result, "benchmark_return", 0.0),
        alpha=getattr(exec_result, "alpha", 0.0),
        beta=getattr(exec_result, "beta", 0.0),
    )

    # 转换 trades 格式：execution 版用 "type"，modules 版用 "direction"
    trades = []
    for t in exec_result.trades:
        trade = dict(t)
        if "type" in trade and trade["type"] in ("buy", "sell"):
            trade["direction"] = trade["type"]
        if "fees" in trade:
            trade.setdefault("pnl", 0.0)
        trades.append(trade)

    # 转换 periods → snapshots
    snapshots = []
    for p in getattr(exec_result, "periods", []):
        snapshots.append({
            "date": p.get("period", ""),
            "portfolio_value": p.get("end_value", 0.0),
            "cash": p.get("cash", 0.0),
            "shares": p.get("shares", 0.0),
            "signal": p.get("signal", 0),
        })

    # 构建净值曲线
    equity_curve = [s["portfolio_value"] for s in snapshots]
    if not equity_curve:
        equity_curve = [initial_cash]
    dates = [s["date"] for s in snapshots]
    if not dates:
        dates = [start_date]

    # 计算 MD5 参数哈希
    payload = {
        "symbol": symbol,
        "strategy": strategy_name,
        "start": start_date,
        "end": end_date,
        "metrics": {
            "total_return": metrics.total_return,
            "sharpe": metrics.sharpe_ratio,
            "max_dd": metrics.max_drawdown,
            "trades": metrics.total_trades,
        },
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    params_hash = hashlib.md5(raw.encode("utf-8")).hexdigest()

    # 费用汇总
    cost_bd = {"total_fees": 0.0, "commission": 0.0, "stamp_tax": 0.0, "slippage": 0.0}
    for t in trades:
        cost_bd["total_fees"] += t.get("fees", 0)
        for k in ("commission", "stamp_tax", "slippage"):
            v = t.get(k)
            if isinstance(v, (int, float)):
                cost_bd[k] += v

    return ModulesBacktestResultDC(
        run_id=run_id,
        symbol=symbol,
        strategy_name=strategy_name,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
        final_value=float(equity_curve[-1]) if equity_curve else initial_cash,
        metrics=metrics,
        trades=trades,
        snapshots=snapshots,
        equity_curve=[round(v, 2) for v in equity_curve],
        benchmark_curve=[],
        dates=dates,
        cost_breakdown=cost_bd,
        risk_gate_blocks=0,
        sanitized_flags=[],
        params_hash=params_hash,
    )


def run_backtest_via_facade(params: PipelineParams) -> ModulesBacktestResultDC:
    """统一回测执行入口 — 优先走 execution 引擎，fallback 到 modules 版。

    Parameters
    ----------
    params : PipelineParams
        完整的回测参数封装。

    Returns
    -------
    ModulesBacktestResultDC
        modules 格式的 BacktestResult（保持 CLI 输出不变）。
    """
    run_id = datetime.now().strftime("%Y%m%d%H%M%S")

    # ── 路径 1: execution 引擎 ──────────────────────────────────
    if not _use_modules_fallback(params):
        from tradingagents.astock.execution.backtest_engine.engine import (
            BacktestEngine,
        )
        from tradingagents.astock.execution.backtest_engine.models import (
            BacktestResult as ExecBacktestResult,
        )

        strategy = _build_execution_strategy(
            params.strategy_name,
            params.strategy_config,
        )

        engine = BacktestEngine(use_mock_data=False)
        exec_result: ExecBacktestResult = engine.run(
            symbol=params.symbol,
            start_date=params.start_date,
            end_date=params.end_date,
            strategy=strategy,
            rebalance_freq=params.rebalance_freq,
            initial_cash=params.initial_cash,
        )

        result = _convert_result_to_modules(
            exec_result,
            strategy_name=params.strategy_name,
            symbol=params.symbol,
            start_date=params.start_date,
            end_date=params.end_date,
            initial_cash=params.initial_cash,
            run_id=run_id,
        )

        _, _, _persist_to_duckdb, _ = _legacy_backtest_exports()
        _persist_to_duckdb(result)
        return result

    # ── 路径 2: modules 版引擎（fallback） ──────────────────────
    logger.info("Using modules backtest engine for %s", params.strategy_name)
    _, _, _, _run_backtest_pipeline_legacy = _legacy_backtest_exports()
    return _run_backtest_pipeline_legacy(params)

