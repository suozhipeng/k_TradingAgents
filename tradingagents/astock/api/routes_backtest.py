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
        BollingerBandsReversionStrategy,
        BullTrendStrategy,
        DefensiveMomentumStrategy,
        GridTradingStrategy,
        MACDTrendStrategy,
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
        "MACDTrend": MACDTrendStrategy,
        "BollingerBands": BollingerBandsReversionStrategy,
        "GridTrading": GridTradingStrategy,
    }
    return _STRATEGY_REGISTRY


def _get_optimizer() -> Any:
    """Lazy import + instantiate StrategyOptimizer."""
    from tradingagents.astock.execution.optimizer import StrategyOptimizer

    return StrategyOptimizer


def _get_backtest_engine(use_mock_data: bool = False) -> Any:
    """Lazy import + instantiate BacktestEngine."""
    from tradingagents.astock.execution.backtest_engine import BacktestEngine

    return BacktestEngine(use_mock_data=use_mock_data)


def _sanitize_nan(records: list[dict]) -> None:
    """Replace NaN/Inf with None in-place for valid JSON."""
    import math
    from datetime import datetime

    for record in records:
        for k, v in record.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                record[k] = None
            elif isinstance(v, datetime):
                record[k] = v.strftime("%Y-%m-%d")
            elif hasattr(v, "isoformat"):
                record[k] = v.isoformat()


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
        mock_data (bool) — optional, force mock data (for testing)
    """
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "")
    strategy_name = data.get("strategy", "")
    start_date = data.get("start", "")
    end_date = data.get("end", "")
    rebalance_freq = data.get("rebalance_freq", "M")
    use_mock = bool(data.get("mock_data", False))

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
        engine = _get_backtest_engine(use_mock_data=use_mock)
        result = engine.run(symbol, start_date, end_date, strategy, rebalance_freq)
        result.strategy_name = strategy_name

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
            "trades": result.trades,
            "periods": result.periods,
            "fee_config_used": result.fee_config_used,
            "execution_signal": result.execution_signal,
        }
        return jsonify(payload), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# DELETE /api/v1/backtest/results — clear all backtest history
# ---------------------------------------------------------------------------


@bp.route("/backtest/results", methods=["DELETE"])
def clear_backtest_results() -> tuple[Response, int]:
    """Delete all stored backtest results."""
    try:
        deleted = _store().clear_backtest_results()
        return jsonify({"status": "ok", "deleted": deleted}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# DELETE /api/v1/backtest/results/<run_id> — delete single record
# ---------------------------------------------------------------------------


@bp.route("/backtest/results/<run_id>", methods=["DELETE"])
def delete_backtest_result(run_id: str) -> tuple[Response, int]:
    """Delete a single backtest result by run_id."""
    try:
        deleted = _store().delete_backtest_result(run_id)
        return jsonify({"status": "ok", "deleted": deleted}), 200
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
            _sanitize_nan(results)
            for r in results:
                if isinstance(r.get("params_json"), str):
                    try:
                        r["params"] = json.loads(r["params_json"])
                    except (json.JSONDecodeError, TypeError):
                        r["params"] = {}
                    del r["params_json"]
            return jsonify({"results": results}), 200
        rows = df.to_dict(orient="records") if df is not None and not df.empty else []
        _sanitize_nan(rows)
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
    use_mock = bool(request.args.get("mock_data", "0"))

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
        engine = _get_backtest_engine(use_mock_data=use_mock)
        results = []
        for name in names:
            strategy = registry[name]()
            result = engine.run(symbol, start_date, end_date, strategy)

            # Extract equity curve and returns from periods (same as analyze)
            periods = result.periods or []
            equity_curve = [
                {"period": p["period"], "value": p["end_value"]}
                for p in periods
            ]
            returns = []
            prev_val = None
            for p in periods:
                val = p["end_value"]
                if prev_val is not None and prev_val > 0:
                    ret = (val - prev_val) / prev_val
                    returns.append({"period": p["period"], "return": round(ret, 6)})
                prev_val = val

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
                    "equity_curve": equity_curve,
                    "returns": returns,
                }
            )

        # Sort by composite score (50% Sharpe + 30% return - 20% drawdown)
        def _composite(r: dict) -> float:
            s = r.get("sharpe_ratio", 0) or 0
            tr = r.get("total_return", 0) or 0
            dd = r.get("max_drawdown", 0) or 0
            return 0.5 * s + 0.3 * tr - 0.2 * dd

        results.sort(key=_composite, reverse=True)
        for i, r in enumerate(results, start=1):
            r["rank"] = i

        return jsonify({"comparison": results}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# POST /api/v1/backtest/analyze — detailed performance analysis
# ---------------------------------------------------------------------------


@bp.route("/backtest/analyze", methods=["POST"])
def analyze_backtest() -> tuple[Response, int]:
    """POST /api/v1/backtest/analyze
    JSON: {
      "strategy": "MACDTrend",
      "symbol": "600519.SH",
      "start_date": "2024-01-01",
      "end_date": "2025-12-31",
    }
    Returns detailed performance data for charting.
    """
    body = request.get_json(force=True, silent=True) or {}
    strategy_name = body.get("strategy", "")
    if not strategy_name:
        return jsonify({"error": "strategy is required", "status": 400}), 400
    symbol = body.get("symbol", "600519.SH")
    start_date = body.get("start_date", "")
    end_date = body.get("end_date", "")
    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date are required", "status": 400}), 400

    registry = _get_strategy_registry()
    if strategy_name not in registry:
        return jsonify({
            "error": f"Unknown strategy {strategy_name!r}. Available: {list(registry)}",
            "status": 400,
        }), 400

    try:
        strategy = registry[strategy_name]()
        engine = _get_backtest_engine(use_mock_data=bool(body.get("mock_data", False)))
        result = engine.run(symbol, start_date, end_date, strategy)

        # Extract equity curve from periods
        periods = result.periods or []
        equity_curve = [
            {"period": p["period"], "value": p["end_value"]}
            for p in periods
        ]
        # Compute returns for each period
        returns = []
        prev_val = None
        for p in periods:
            val = p["end_value"]
            if prev_val is not None and prev_val > 0:
                ret = (val - prev_val) / prev_val
                returns.append({"period": p["period"], "return": round(ret, 6)})
            prev_val = val

        # Trade P&L extraction
        trades = []
        for p in periods:
            if p.get("signal", 0) != 0:
                trades.append({
                    "period": p["period"],
                    "signal": p["signal"],
                    "value": p["end_value"],
                })

        payload = {
            "strategy": strategy_name,
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "metrics": {
                "total_return": result.total_return,
                "annualized_return": result.annualized_return,
                "sharpe_ratio": result.sharpe_ratio,
                "max_drawdown": result.max_drawdown,
                "win_rate": result.win_rate,
                "total_trades": result.total_trades,
            },
            "equity_curve": equity_curve,
            "returns": returns,
            "trades": trades,
        }
        return jsonify(payload), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# POST /api/v1/backtest/optimize — parameter grid search
# ---------------------------------------------------------------------------


@bp.route("/backtest/optimize", methods=["POST"])
def optimize_strategy_api() -> tuple[Response, int]:
    """POST /api/v1/backtest/optimize
    JSON: {
      "strategy": "MACDTrend",
      "symbol": "600519.SH",
      "start_date": "2024-01-01",
      "end_date": "2025-12-31",
      "param_grid": {"fast_period": [8,12,16], "slow_period": [20,26,32]},
      "top_n": 5
    }
    """
    body = request.get_json(force=True, silent=True) or {}
    strategy_name = body.get("strategy", "")
    if not strategy_name:
        return jsonify({"error": "strategy is required", "status": 400}), 400
    symbol = body.get("symbol", "600519.SH")
    start_date = body.get("start_date", "")
    end_date = body.get("end_date", "")
    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date are required", "status": 400}), 400
    param_grid = body.get("param_grid")
    top_n = int(body.get("top_n", 5))

    registry = _get_strategy_registry()
    if strategy_name not in registry:
        return jsonify({
            "error": f"Unknown strategy {strategy_name!r}. Available: {list(registry)}",
            "status": 400,
        }), 400

    try:
        OptimizerCls = _get_optimizer()
        optimizer = OptimizerCls(strategy_name)
        results = optimizer.optimize(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            param_grid=param_grid,
            top_n=top_n,
        )
        return jsonify({
            "strategy": strategy_name,
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "total_trials": len(results),
            "results": results,
        }), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500
