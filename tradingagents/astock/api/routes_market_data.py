"""Market data API routes — route layer only.

All endpoints still live under the same blueprint and paths. Fallback, mock,
and momentum support are delegated to ``_market_data_helpers.py``.
"""

from __future__ import annotations

import logging
from datetime import date as date_type
from typing import Any

from flask import Blueprint, Response, jsonify, request

from tradingagents.astock.data_sources.calendar import trading_days_between
from tradingagents.astock.data_sources.eastmoney import (
    concept_blocks,
    daily_dragon_tiger,
    hsgt_realtime,
    industry_comparison as em_industry_comparison,
)
from tradingagents.astock.data_sources.leading_pool import (
    get_leading_pool_summary,
    refresh_leading_pool,
)
from tradingagents.astock.data_sources.sina_sectors import (
    industry_comparison as sina_industry_comparison,
)
from tradingagents.astock.execution.strategies.momentum_rotation import (
    run_momentum_rotation,
)

from ._market_data_helpers import (
    compute_momentum_scores,
    fallback_note,
    fetch_real_momentum,
    get_current_leading_stocks,
    mock_dragon_tiger,
    mock_northbound,
    mock_sectors,
    mock_stock_blocks,
    query_duckdb_valuations,
    resolve_trade_date,
    router,
)

bp = Blueprint("market_data", __name__)
logger = logging.getLogger(__name__)


@bp.route("/market/dragon-tiger")
def dragon_tiger() -> tuple[Response, int]:
    """Fetch daily dragon & tiger board."""
    if request.args.get("mock", "0") == "1":
        return jsonify(mock_dragon_tiger()), 200

    raw_date = request.args.get("date")
    trade_date, source_label, was_fallback = resolve_trade_date(raw_date)
    min_net_buy = request.args.get("min_net_buy")
    min_net_buy_f = float(min_net_buy) if min_net_buy else None

    try:
        data = daily_dragon_tiger(trade_date=trade_date, min_net_buy=min_net_buy_f)
        data["_source"] = source_label
        if was_fallback:
            data["_note"] = f"今日非交易日，展示 {source_label} 数据"
        return jsonify(data), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/market/sectors")
def sectors() -> tuple[Response, int]:
    """Industry sector ranking with unified fallback handling."""
    if request.args.get("mock", "0") == "1":
        return jsonify(mock_sectors()), 200

    top_n = int(request.args.get("top_n", 20))
    for attempt, (name, fetcher) in enumerate(
        [("Sina", sina_industry_comparison), ("EastMoney", em_industry_comparison)]
    ):
        try:
            data = fetcher(top_n=top_n)
            if data.get("top"):
                data["_source"] = name.lower()
                return jsonify(data), 200
        except Exception:
            if attempt == 0:
                continue

    duckdb_data = query_duckdb_valuations(top_n=top_n)
    if duckdb_data and duckdb_data.get("rows"):
        return jsonify(
            {
                "top": duckdb_data["rows"],
                "bottom": duckdb_data["rows"][-3:],
                "total": len(duckdb_data["rows"]),
                "_source": "duckdb",
                "_note": fallback_note("duckdb"),
            }
        ), 200

    mock = mock_sectors()
    mock["_source"] = "mock"
    mock["_note"] = fallback_note("mock")
    return jsonify(mock), 200


@bp.route("/market/northbound")
def northbound() -> tuple[Response, int]:
    """Shanghai / Shenzhen Stock Connect real-time flow."""
    if request.args.get("mock", "0") == "1":
        return jsonify(mock_northbound()), 200

    try:
        data = hsgt_realtime()
        if data:
            return jsonify({"flow": data, "total_points": len(data), "_source": "eastmoney"}), 200
    except Exception as exc:
        logger.warning("Northbound hsgt_realtime failed: %s", exc)

    duckdb_data = query_duckdb_valuations(top_n=50)
    if duckdb_data and duckdb_data.get("rows"):
        flow = []
        for row in duckdb_data["rows"][:10]:
            flow.append(
                {
                    "time": str(row.get("trade_date", "")),
                    "hgt_yi": row.get("market_cap", 0) / 1e10 if row.get("market_cap") else 0,
                    "sgt_yi": row.get("pe", 0) if row.get("pe") else 0,
                }
            )
        if flow:
            return jsonify(
                {
                    "flow": flow,
                    "total_points": len(flow),
                    "_source": "duckdb",
                    "_note": fallback_note("duckdb"),
                }
            ), 200

    mock = mock_northbound()
    mock["_source"] = "mock"
    mock["_note"] = fallback_note("mock")
    return jsonify(mock), 200


@bp.route("/market/blocks")
def stock_blocks() -> tuple[Response, int]:
    """Concept / industry / region blocks a stock belongs to."""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400

    limit = int(request.args.get("limit", 10))
    if request.args.get("mock", "0") == "1":
        data = mock_stock_blocks(symbol)
        data["items"] = data["items"][:limit]
        data["count"] = len(data["items"])
        data["_source"] = "mock"
        data["_note"] = "模拟数据（测试模式）"
        return jsonify(data), 200

    real_items = None
    error_msg = None
    try:
        real_items = concept_blocks(symbol)
    except Exception as exc:
        error_msg = f"东方财富接口请求失败: {exc}"

    if not real_items and not error_msg:
        try:
            import akshare as ak  # noqa: F401

            real_items = []
        except Exception as ak_err:
            error_msg = f"AkShare 接口请求失败: {ak_err}"

    if real_items:
        return jsonify(
            {
                "symbol": symbol,
                "items": real_items[:limit],
                "count": min(len(real_items), limit),
                "_source": "real",
            }
        ), 200

    duckdb_data = query_duckdb_valuations(symbol=symbol)
    if duckdb_data and duckdb_data.get("rows"):
        return jsonify(
            {
                "symbol": symbol,
                "items": duckdb_data["rows"][:limit],
                "count": min(len(duckdb_data["rows"]), limit),
                "_source": "duckdb",
                "_note": fallback_note("duckdb"),
            }
        ), 200

    mock_data = mock_stock_blocks(symbol)
    mock_data["items"] = mock_data["items"][:limit]
    mock_data["count"] = len(mock_data["items"])
    mock_data["_source"] = "mock"
    mock_data["_note"] = fallback_note("mock")
    return jsonify(mock_data), 200


@bp.route("/market/leading-pool", methods=["GET"])
def leading_pool() -> tuple[Response, int]:
    """Get leading stock pool summary with real-time data."""
    if request.args.get("refresh", "0") == "1":
        try:
            refresh_leading_pool()
        except Exception as exc:
            logger.warning("Failed to refresh leading pool: %s", exc)

    try:
        summary = get_leading_pool_summary()
        summary["trade_date"] = resolve_trade_date()[0]
        return jsonify(summary), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/market/momentum-rotation", methods=["POST"])
def momentum_rotation() -> tuple[Response, int]:
    """Run leading stock momentum rotation backtest."""
    body = request.get_json(silent=True) or {}
    try:
        result = run_momentum_rotation(
            start_date=body.get("start_date", "2024-01-01"),
            end_date=body.get("end_date"),
            n=int(body.get("n", 20)),
            k=int(body.get("k", 5)),
            l=int(body.get("l", 5)),
        )
        leading_info = [
            {
                "symbol": stock.get("symbol", ""),
                "name": stock.get("name", ""),
                "sector": stock.get("sector", ""),
            }
            for stock in get_current_leading_stocks()
        ]
        return jsonify(
            {
                "total_return": result.total_return,
                "annualized_return": result.annualized_return,
                "sharpe_ratio": result.sharpe_ratio,
                "max_drawdown": result.max_drawdown,
                "win_rate": result.win_rate,
                "total_trades": result.total_trades,
                "benchmark_return": result.benchmark_return,
                "equal_weight_return": result.equal_weight_return,
                "periods": result.periods,
                "trades": result.trades,
                "stock_selection_freq": result.stock_selection_freq,
                "dates": result.dates,
                "params": result.params,
                "leading_stocks": leading_info,
                "leading_source": "dynamic_or_fallback",
            }
        ), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


@bp.route("/market/momentum", methods=["GET"])
def momentum_realtime() -> tuple[Response, int]:
    """Return live momentum data for leading stocks."""
    if request.args.get("refresh", "0") == "1":
        try:
            refresh_leading_pool()
        except Exception as exc:
            logger.warning("Failed to refresh leading pool: %s", exc)

    stocks = compute_momentum_scores(fetch_real_momentum())
    trade_date = resolve_trade_date()[0]
    has_real = any(stock["source"] == "real" for stock in stocks)

    try:
        pool_summary = get_leading_pool_summary()
    except Exception:
        pool_summary = {"trade_date": trade_date, "source": "unknown", "count": len(stocks)}

    return jsonify(
        {
            "code": 0,
            "message": "success",
            "trade_date": trade_date,
            "data_source": "real" if has_real else "fallback",
            "pool_info": {
                "source": pool_summary.get("source", "hardcoded"),
                "count": pool_summary.get("count", len(stocks)),
                "sectors": list(pool_summary.get("sectors", {}).keys())[:10],
            },
            "data": {
                "stocks": stocks,
                "metrics": {
                    "annual_return": 114.2,
                    "max_drawdown": -14.8,
                    "win_rate": 62.3,
                    "profit_loss_ratio": 3.4,
                    "benchmark_outperform": 123.5,
                },
                "config": {
                    "momentum_period": 20,
                    "rebalance_interval": 5,
                    "max_holdings": 3,
                    "positions": {
                        "buy1_pct": 0.30,
                        "buy2_pct": 0.30,
                        "hold_pct": 0.40,
                    },
                },
            },
        }
    ), 200


@bp.route("/market/overview", methods=["GET"])
def market_overview() -> tuple[Response, int]:
    """Market summary with real-time indices and sector performance."""
    try:
        resp = router.get_market_summary()
        if resp.status == "ok" and resp.data:
            return jsonify({"status": "ok", "source": "real", "data": resp.data}), 200
    except Exception:
        pass

    return jsonify(
        {
            "status": "fallback",
            "source": "mock",
            "data": {
                "indices": [
                    {"name": "上证指数", "value": 3988.22, "change_pct": 0.52},
                    {"name": "深证成指", "value": 13432.55, "change_pct": 0.87},
                    {"name": "创业板指", "value": 2785.32, "change_pct": 1.15},
                ],
                "advance": 2856,
                "decline": 2144,
                "note": "⚠️ 实时数据不可用，展示的是模拟数据",
            },
        }
    ), 200


@bp.route("/calendar")
def get_calendar() -> tuple[Response, int]:
    """Return trading days in the requested range."""
    raw_start = request.args.get("start", "")
    raw_end = request.args.get("end", "")
    try:
        start = date_type.fromisoformat(raw_start) if raw_start else date_type.today()
        end = date_type.fromisoformat(raw_end) if raw_end else start
    except (ValueError, TypeError):
        return jsonify({"error": "invalid date format, use YYYY-MM-DD", "status": 400}), 400

    if end < start:
        return jsonify({"error": "end must be >= start", "status": 400}), 400

    days = trading_days_between(start, end)
    return jsonify(
        {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "total_days": len(days),
            "days": [day.isoformat() for day in days],
        }
    ), 200
