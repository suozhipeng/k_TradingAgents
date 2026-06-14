"""Backtest API routes — run and query backtests.

All routes return JSON.  Error responses follow ``{"error": ..., "status": N}``.

Uses lazy imports for ``tradingagents.astock.execution.*`` to avoid the full
dependency chain at module load time.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

bp = Blueprint("backtest", __name__)

# Strategy registry: built lazily inside route functions to avoid triggering
# the full tradingagents.astock import chain at module load time.
_STRATEGY_REGISTRY: dict[str, type] | None = None


def _get_strategy_registry() -> dict[str, type]:
    """Lazy-build strategy registry on first call."""
    global _STRATEGY_REGISTRY
    if _STRATEGY_REGISTRY is not None:
        return _STRATEGY_REGISTRY

    # Lazy import — only triggered when a backtest endpoint is actually called
    from tradingagents.astock.execution.strategy_base import (
        BullTrendStrategy,
        DefensiveMomentumStrategy,
        MeanReversionStrategy,
        MovingAverageTrendStrategy,
        PutWriteStrategy,
        RSIRangeStrategy,
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
    }
    return _STRATEGY_REGISTRY


def _get_backtest_engine() -> Any:
    """Lazy import + instantiate BacktestEngine."""
    from tradingagents.astock.execution.backtest_engine import BacktestEngine

    return BacktestEngine()


def _store() -> Any:
    return current_app.config["STORE"]


# ---------------------------------------------------------------------------
# POST /api/v1/backtest/run
# ---------------------------------------------------------------------------


@bp.route("/backtest/run", methods=["POST"])
def run_backtest() -> tuple[Response, int]:
    """Run a single backtest.

    JSON body:
        symbol (str) — required
        strategy (str) — required, one of the registered strategy names
        start (str) — required, YYYY-MM-DD
        end (str) — required, YYYY-MM-DD
        rebalance_freq (str) — optional, default "M"
    """
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "")
    strategy_name = data.get("strategy", "")
    start_date = data.get("start", "")
    end_date = data.get("end", "")
    rebalance_freq = data.get("rebalance_freq", "M")

    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    if not strategy_name:
        return jsonify({"error": "strategy is required", "status": 400}), 400

    registry = _get_strategy_registry()
    if strategy_name not in registry:
        return jsonify(
            {
                "error": f"Unknown strategy '{strategy_name}'. Available: {list(registry)}",
                "status": 400,
            }
        ), 400
    if not start_date or not end_date:
        return jsonify({"error": "start and end dates are required", "status": 400}), 400

    try:
        strategy_cls = registry[strategy_name]
        strategy = strategy_cls()
        engine = _get_backtest_engine()
        result = engine.run(symbol, start_date, end_date, strategy, rebalance_freq)

        # Persist to store
        _store().store_backtest_result(result)

        payload = {
            "run_id": result.symbol + "_" + strategy_name + "_" + datetime.utcnow().isoformat(),
            "symbol": result.symbol,
            "strategy_name": strategy_name,
            "start_date": result.start_date,
            "end_date": result.end_date,
            "total_return": result.total_return,
            "annualized_return": result.annualized_return,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "win_rate": result.win_rate,
            "total_trades": result.total_trades,
            "periods": result.periods,
            "fee_config_used": result.fee_config_used,
            "execution_signal": result.execution_signal,
        }
        return jsonify(payload), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/backtest/results
# ---------------------------------------------------------------------------


@bp.route("/backtest/results")
def get_backtest_results() -> tuple[Response, int]:
    """Query historical backtest results.

    Query params:
        strategy (str) — optional filter by strategy name.
    """
    strategy_name = request.args.get("strategy")
    try:
        df = _store().get_backtest_results(strategy_name=strategy_name)
        if df is not None and not df.empty and "params_json" in df.columns:
            results = df.to_dict(orient="records")
            for r in results:
                if isinstance(r.get("params_json"), str):
                    try:
                        r["params"] = json.loads(r["params_json"])
                    except (json.JSONDecodeError, TypeError):
                        r["params"] = {}
                    del r["params_json"]
            return jsonify({"results": results}), 200
        rows = df.to_dict(orient="records") if df is not None and not df.empty else []
        return jsonify({"results": rows}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/backtest/compare
# ---------------------------------------------------------------------------


@bp.route("/backtest/compare")
def compare_backtests() -> tuple[Response, int]:
    """Multi-strategy comparison.

    Query params:
        strategies (str) — comma-separated strategy names
        symbol (str) — stock symbol
        start (str) — YYYY-MM-DD
        end (str) — YYYY-MM-DD
    """
    strategies_param = request.args.get("strategies", "")
    symbol = request.args.get("symbol", "")
    start_date = request.args.get("start", "")
    end_date = request.args.get("end", "")

    if not strategies_param:
        return jsonify({"error": "strategies is required (comma-separated)", "status": 400}), 400
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400
    if not start_date or not end_date:
        return jsonify({"error": "start and end dates are required", "status": 400}), 400

    registry = _get_strategy_registry()
    names = [s.strip() for s in strategies_param.split(",") if s.strip()]
    if not names:
        return jsonify({"error": "No valid strategy names provided", "status": 400}), 400

    unknown = [n for n in names if n not in registry]
    if unknown:
        return jsonify(
            {
                "error": f"Unknown strategies: {unknown}. Available: {list(registry)}",
                "status": 400,
            }
        ), 400

    try:
        engine = _get_backtest_engine()
        results = []
        for name in names:
            strategy = registry[name]()
            result = engine.run(symbol, start_date, end_date, strategy)
            results.append(
                {
                    "strategy_name": name,
                    "total_return": result.total_return,
                    "annualized_return": result.annualized_return,
                    "sharpe_ratio": result.sharpe_ratio,
                    "max_drawdown": result.max_drawdown,
                    "win_rate": result.win_rate,
                    "total_trades": result.total_trades,
                    "periods": result.periods,
                }
            )
        return jsonify({"comparison": results}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500
