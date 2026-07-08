"""Backtest API routes — run and query backtests.

All routes return JSON.  Error responses follow ``{"error": ..., "status": N}``.

Uses lazy imports for ``tradingagents.astock.execution.*`` to avoid the full
dependency chain at module load time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

from ._backtest_helpers import (
    build_equity_curve,
    build_period_returns,
    create_backtest_engine,
    expand_params_json_rows,
    extract_signal_trades,
    get_optimizer_cls,
    get_strategy_registry,
    sanitize_metrics,
    sanitize_nan,
    validate_date_range,
)

bp = Blueprint("backtest", __name__)


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

    registry = get_strategy_registry()
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
        validate_date_range("start date", start_date, "end date", end_date)
    except ValueError as exc:
        return jsonify({"error": str(exc), "status": 400}), 400

    try:
        strategy_cls = registry[strategy_name]
        strategy = strategy_cls()
        engine = create_backtest_engine(use_mock_data=use_mock)
        result = engine.run(symbol, start_date, end_date, strategy, rebalance_freq)
        result.strategy_name = strategy_name

        # Generate clean timestamp ID before persisting
        run_id = datetime.now().strftime("%Y%m%d%H%M%S")
        result.run_id = run_id

        # Persist to store
        _store().store_backtest_result(result)

        payload = {
            "run_id": run_id,
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
            "data_assumption": result.data_assumption,
            "benchmark_symbol": result.benchmark_symbol,
            "benchmark_return": result.benchmark_return,
            "benchmark_max_drawdown": result.benchmark_max_drawdown,
            "alpha": result.alpha,
            "beta": result.beta,
            "cost_breakdown": result.cost_breakdown,
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
            return jsonify({"results": expand_params_json_rows(df)}), 200
        rows = df.to_dict(orient="records") if df is not None and not df.empty else []
        sanitize_nan(rows)
        return jsonify({"results": rows}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# Alias: GET /api/v1/backtest/history → same handler as /backtest/results
bp.add_url_rule("/backtest/history", "get_backtest_history", get_backtest_results)


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

    try:
        validate_date_range("start date", start_date, "end date", end_date)
    except ValueError as exc:
        return jsonify({"error": str(exc), "status": 400}), 400

    registry = get_strategy_registry()
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
        engine = create_backtest_engine(use_mock_data=use_mock)
        results = []
        for name in names:
            strategy = registry[name]()
            result = engine.run(symbol, start_date, end_date, strategy)

            periods = result.periods or []
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
                    "equity_curve": build_equity_curve(periods),
                    "returns": build_period_returns(periods),
                    "benchmark_symbol": result.benchmark_symbol,
                    "benchmark_return": result.benchmark_return,
                    "benchmark_max_drawdown": result.benchmark_max_drawdown,
                    "alpha": result.alpha,
                    "beta": result.beta,
                    "cost_breakdown": result.cost_breakdown,
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

        # Sanitize all metrics before emitting
        for r in results:
            sanitize_metrics(r)

        return jsonify({"comparison": results}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Walk-Forward Analysis endpoint
# ---------------------------------------------------------------------------


@bp.route("/backtest/walkforward", methods=["POST"])
def walkforward():
    """Run Walk-Forward Analysis and return results + summary."""
    try:
        body = request.get_json(force=True) or {}
        symbol = str(body.get("symbol", "")).strip()
        start_date = str(body.get("start_date", "")).strip()
        end_date = str(body.get("end_date", "")).strip()
        strategy_name = str(body.get("strategy", "MovingAverageTrend"))
        train_years = float(body.get("train_years", 2))
        val_months = int(body.get("val_months", 6))
        top_n = int(body.get("top_n", 1))

        if not symbol or not start_date or not end_date:
            return jsonify({"error": "symbol, start_date, end_date required", "status": 400}), 400

        try:
            validate_date_range("start_date", start_date, "end_date", end_date)
        except ValueError as exc:
            return jsonify({"error": str(exc), "status": 400}), 400

        registry = get_strategy_registry()
        strategy_cls = registry.get(strategy_name)
        if strategy_cls is None:
            return jsonify({"error": f"Unknown strategy: {strategy_name}", "status": 400}), 400

        engine = create_backtest_engine(use_mock_data=True)
        from tradingagents.astock.execution.optimizer import WalkForwardAnalyzer

        wfa = WalkForwardAnalyzer(strategy_cls, engine=engine)
        results = wfa.run(
            symbol, start_date, end_date,
            param_grid=None,
            train_years=train_years,
            val_months=val_months,
            window_mode="rolling",
            top_n=top_n,
        )

        windows = []
        for r in results:
            windows.append({
                "window_idx": r.window_idx,
                "train_period": f"{r.train_start} → {r.train_end}",
                "val_period": f"{r.val_start} → {r.val_end}",
                "best_params": r.best_params,
                "train_score": round(r.train_score, 4),
                "val_score": round(r.val_score, 4),
                "val_sharpe": round(r.val_metrics.get("sharpe_ratio", 0), 4),
                "val_return": round(r.val_metrics.get("total_return", 0), 4),
                "val_max_dd": round(r.val_metrics.get("max_drawdown", 0), 4),
            })

        summary = wfa.summarize(results)
        return jsonify({
            "windows": windows,
            "summary": summary,
        }), 200
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

    try:
        validate_date_range("start_date", start_date, "end_date", end_date)
    except ValueError as exc:
        return jsonify({"error": str(exc), "status": 400}), 400

    registry = get_strategy_registry()
    if strategy_name not in registry:
        return jsonify({
            "error": f"Unknown strategy {strategy_name!r}. Available: {list(registry)}",
            "status": 400,
        }), 400

    try:
        strategy = registry[strategy_name]()
        engine = create_backtest_engine(use_mock_data=bool(body.get("mock_data", False)))
        result = engine.run(symbol, start_date, end_date, strategy)

        periods = result.periods or []
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
            "equity_curve": build_equity_curve(periods),
            "returns": build_period_returns(periods),
            "trades": extract_signal_trades(periods),
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

    Returns an ``OptimizeResult`` JSON body (see
    ``tradingagents.astock.schemas.optimization.OptimizeResult``).
    """
    body = request.get_json(force=True, silent=True) or {}
    strategy_name = body.get("strategy", "")
    if not strategy_name:
        return jsonify({"error": "strategy is required", "status": 400}), 400
    symbol = body.get("symbol", "600519.SH")
    start_date = body.get("start_date", "")
    end_date = body.get("end_date", "")
    use_mock = bool(body.get("mock_data", False))
    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date are required", "status": 400}), 400
    param_grid = body.get("param_grid")
    top_n = int(body.get("top_n", 5))

    registry = get_strategy_registry()
    if strategy_name not in registry:
        return jsonify({
            "error": f"Unknown strategy {strategy_name!r}. Available: {list(registry)}",
            "status": 400,
        }), 400

    try:
        OptimizerCls = get_optimizer_cls()
        optimizer = OptimizerCls(
            strategy_name,
            engine=create_backtest_engine(use_mock_data=use_mock),
        )
        raw_results = optimizer.optimize(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            param_grid=param_grid,
            top_n=top_n,
        )
        from tradingagents.astock.schemas.optimization import OptimizeResult
        best = raw_results[0] if raw_results else {}
        best_score = best.get("score", 0.0)
        result = OptimizeResult(
            strategy_name=strategy_name,
            symbol=symbol,
            score=best_score,
            top_n=raw_results,
            parameter_count=len(raw_results),
            notes=[
                "in_sample/out_sample/walk_forward/benchmark/alpha: "
                "not yet split — requires sample-partition aware optimizer."
            ],
        )
        return jsonify(result.model_dump()), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500
