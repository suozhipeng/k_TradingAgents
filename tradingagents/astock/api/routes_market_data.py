"""Market data API routes — route layer only.

All endpoints still live under the same blueprint and paths. Fallback, mock,
and momentum support are delegated to ``_market_data_helpers.py``.
"""

from __future__ import annotations

import logging
from datetime import date as date_type
from typing import Any

from flask import Blueprint, Response, jsonify, request
from .envelope import error_response

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
from tradingagents.astock.data_sources.quality import DataQualityBanner
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
from ._helpers import _as_bool, bounded_int_arg, mock_data_enabled

bp = Blueprint("market_data", __name__)
logger = logging.getLogger(__name__)


@bp.route("/market/quote")
def market_quote() -> tuple[Response, int]:
    """Research-market quote: delegates to trade quote's live/fetch logic."""
    from . import routes_trade
    from datetime import datetime as _dt
    # Use the same quote-fetching function from routes_trade
    symbol = request.args.get("symbol", "").strip()
    if not symbol:
        return error_response("symbol is required", 400)
    cached = routes_trade._load_cached_quote(symbol)
    if cached:
        ts = cached.get("cached_at")
        if isinstance(ts, str):
            try:
                ts = _dt.fromisoformat(ts)
            except (ValueError, TypeError):
                ts = None
        return jsonify(DataQualityBanner.enrich(cached, source="cache", ts=ts)), 200
    live = routes_trade._fetch_realtime_quote(symbol)
    if live:
        ts = live.get("timestamp")
        if isinstance(ts, str):
            try:
                ts = _dt.fromisoformat(ts)
            except (ValueError, TypeError):
                ts = None
        routes_trade._save_to_cache(symbol, live)
        return jsonify(DataQualityBanner.enrich(live, source="live", ts=ts)), 200
    synthetic = routes_trade._build_deterministic_quote(symbol)
    ts = synthetic.get("timestamp")
    if isinstance(ts, str):
        try:
            ts = _dt.fromisoformat(ts)
        except (ValueError, TypeError):
            ts = None
    routes_trade._save_to_cache(symbol, synthetic)
    return jsonify(DataQualityBanner.enrich(synthetic, source="mock", ts=ts)), 200


@bp.route("/market/dragon-tiger")
def dragon_tiger() -> tuple[Response, int]:
    """Fetch daily dragon & tiger board."""
    from datetime import datetime as _dt
    if mock_data_enabled() or _as_bool(request.args.get("mock"), False):
        data = mock_dragon_tiger()
        return jsonify(DataQualityBanner.enrich(data, source="mock")), 200
    raw_date = request.args.get("date")
    trade_date, source_label, was_fallback = resolve_trade_date(raw_date)
    min_net_buy = request.args.get("min_net_buy")
    min_net_buy_f = float(min_net_buy) if min_net_buy else None
    try:
        data = daily_dragon_tiger(trade_date=trade_date, min_net_buy=min_net_buy_f)
        ts = _dt.now()
        banner = DataQualityBanner.banner(source="live" if not was_fallback else "fallback", ts=ts)
        result = {**data, **banner}
        if was_fallback:
            result["_note"] = f"今日非交易日，展示 {source_label} 数据"
        return jsonify(result), 200
    except Exception as exc:
        logger.warning("Dragon-tiger live request failed for %s: %s", trade_date, exc)
        fallback = {
            "date": trade_date,
            "total_records": 0,
            "stocks": [],
            "note": "龙虎榜实时数据暂不可用",
        }
        banner = DataQualityBanner.banner(source="fallback", ts=_dt.now())
        return jsonify({**fallback, **banner}), 200


@bp.route("/market/sectors")
def sectors() -> tuple[Response, int]:
    """Industry sector ranking with unified fallback handling."""
    from datetime import datetime as _dt
    if mock_data_enabled() or _as_bool(request.args.get("mock"), False):
        data = mock_sectors()
        return jsonify(DataQualityBanner.enrich(data, source="mock")), 200
    try:
        top_n = bounded_int_arg("top_n", 20, minimum=1, maximum=100)
    except ValueError:
        return error_response("invalid_top_n", 400)
    for attempt, (name, fetcher) in enumerate(
        [("Sina", sina_industry_comparison), ("EastMoney", em_industry_comparison)]
    ):
        try:
            data = fetcher(top_n=top_n)
            if data.get("top"):
                banner = DataQualityBanner.banner(source="live", ts=_dt.now())
                result = {**data, **banner}
                return jsonify(result), 200
        except Exception as exc:
            logger.debug("Failed to fetch northbound data (attempt %d): %s", attempt, exc)
            if attempt == 0:
                continue
    duckdb_data = query_duckdb_valuations(top_n=top_n)
    if duckdb_data and duckdb_data.get("rows"):
        banner = DataQualityBanner.banner(source="duckdb", ts=_dt.now())
        return jsonify({**duckdb_data, **banner, "_note": fallback_note("duckdb")}), 200
    mock = mock_sectors()
    mock["_note"] = fallback_note("mock")
    return jsonify(DataQualityBanner.enrich(mock, source="mock")), 200


@bp.route("/market/northbound")
def northbound() -> tuple[Response, int]:
    """Shanghai / Shenzhen Stock Connect real-time flow."""
    from datetime import datetime as _dt
    if mock_data_enabled() or _as_bool(request.args.get("mock"), False):
        data = mock_northbound()
        return jsonify(DataQualityBanner.enrich(data, source="mock")), 200
    try:
        data = hsgt_realtime()
        if data:
            banner = DataQualityBanner.banner(source="live", ts=_dt.now())
            return jsonify({**{"flow": data, "total_points": len(data)}, **banner}), 200
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
            banner = DataQualityBanner.banner(source="duckdb", ts=_dt.now())
            return jsonify({**banner, "flow": flow, "total_points": len(flow), "_note": fallback_note("duckdb")}), 200
    mock = mock_northbound()
    return jsonify(DataQualityBanner.enrich(mock, source="mock")), 200


@bp.route("/market/blocks")
def stock_blocks() -> tuple[Response, int]:
    """Concept / industry / region blocks a stock belongs to."""
    from datetime import datetime as _dt
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)
    try:
        limit = bounded_int_arg("limit", 10, minimum=1, maximum=100)
    except ValueError as exc:
        return error_response(str(exc), 400)
    if mock_data_enabled() or _as_bool(request.args.get("mock"), False):
        data = mock_stock_blocks(symbol)
        data["items"] = data["items"][:limit]
        data["count"] = len(data["items"])
        return jsonify(DataQualityBanner.enrich(data, source="mock")), 200
    real_items = None
    error_msg = None
    try:
        real_items = concept_blocks(symbol)
    except Exception as exc:
        error_msg = f"东方财富接口请求失败: {exc}"
    if real_items:
        banner = DataQualityBanner.banner(source="live", ts=_dt.now())
        return jsonify({**{"symbol": symbol, "items": real_items[:limit], "count": min(len(real_items), limit)}, **banner}), 200
    duckdb_data = query_duckdb_valuations(symbol=symbol)
    if duckdb_data and duckdb_data.get("rows"):
        banner = DataQualityBanner.banner(source="duckdb", ts=_dt.now())
        return jsonify({**{"symbol": symbol, "items": duckdb_data["rows"][:limit], "count": min(len(duckdb_data["rows"]), limit), "_note": fallback_note("duckdb")}, **banner}), 200
    mock_data = mock_stock_blocks(symbol)
    mock_data["items"] = mock_data["items"][:limit]
    mock_data["count"] = len(mock_data["items"])
    return jsonify(DataQualityBanner.enrich(mock_data, source="mock")), 200


@bp.route("/market/leading-pool", methods=["GET"])
def leading_pool() -> tuple[Response, int]:
    """Get the cached leading stock pool summary (read-only)."""

    try:
        summary = get_leading_pool_summary()
        summary["trade_date"] = resolve_trade_date()[0]
        return jsonify(summary), 200
    except Exception as exc:
        return error_response(str(exc), 500)


@bp.route("/market/leading-pool/refresh", methods=["POST"])
def refresh_leading_pool_endpoint() -> tuple[Response, int]:
    """Refresh the leading pool; POST keeps this provider write behind auth."""
    try:
        refresh_leading_pool()
        summary = get_leading_pool_summary()
        summary["trade_date"] = resolve_trade_date()[0]
        return jsonify(summary), 200
    except Exception as exc:
        logger.warning("Failed to refresh leading pool: %s", exc)
        return error_response("leading_pool_refresh_failed", 503)


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
        return error_response(str(exc), 500)


@bp.route("/market/momentum", methods=["GET"])
def momentum_realtime() -> tuple[Response, int]:
    """Return live momentum data for leading stocks."""
    from datetime import datetime as _dt
    stocks = compute_momentum_scores(fetch_real_momentum())
    trade_date = resolve_trade_date()[0]
    has_real = any(stock["source"] == "real" for stock in stocks)

    # Compute aggregate metrics from the real stocks data when available
    real_prices = [s["price"] for s in stocks if s.get("price", 0) > 0 and s["source"] == "real"]
    real_scores = [s["momentum_score"] for s in stocks if s.get("momentum_score", 0) > 0]

    if has_real and real_prices:
        avg_price = sum(real_prices) / len(real_prices)
        avg_score = sum(real_scores) / len(real_scores) if real_scores else 0
        top_score = max(real_scores) if real_scores else 0
        bottom_score = min(real_scores) if real_scores else 0
        metrics = {
            "avg_price": round(avg_price, 2),
            "avg_momentum_score": round(avg_score, 1),
            "top_momentum_score": round(top_score, 1),
            "bottom_momentum_score": round(bottom_score, 1),
            "real_data_count": len(real_prices),
            "fallback_count": len(stocks) - len(real_prices),
        }
    else:
        metrics = {
            "avg_price": 0,
            "avg_momentum_score": 0,
            "top_momentum_score": 0,
            "bottom_momentum_score": 0,
            "real_data_count": 0,
            "fallback_count": len(stocks),
            "note": "无实时数据，展示回测/缓存数据",
        }

    try:
        pool_summary = get_leading_pool_summary()
    except Exception as exc:
        logger.debug("Failed to get leading pool summary: %s", exc)
        pool_summary = {"trade_date": trade_date, "source": "unknown", "count": len(stocks)}

    source_label = "live" if has_real else "fallback"
    banner = DataQualityBanner.banner(source=source_label, ts=_dt.now())
    return jsonify({
        "code": 0,
        "message": "success",
        "trade_date": trade_date,
        "pool_info": {
            "source": pool_summary.get("source", "hardcoded"),
            "count": pool_summary.get("count", len(stocks)),
            "sectors": list(pool_summary.get("sectors", {}).keys())[:10],
        },
        "data": {
            "stocks": stocks,
            "metrics": metrics,
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
        **banner,
    }), 200


@bp.route("/market/overview", methods=["GET"])
def market_overview() -> tuple[Response, int]:
    """Market summary with real-time indices and sector performance."""
    from datetime import datetime as _dt
    try:
        resp = router.get_market_summary()
        if resp.status == "ok" and resp.data:
            banner = DataQualityBanner.banner(source="live", ts=_dt.now())
            return jsonify({**{"status": "ok", "data": resp.data}, **banner}), 200
    except Exception as exc:
        logger.debug("Failed to get market overview from router: %s", exc)
    banner = DataQualityBanner.banner(source="mock", ts=_dt.now())
    return jsonify({
        "status": "fallback",
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
        **banner,
    }), 200


@bp.route("/calendar")
def get_calendar() -> tuple[Response, int]:
    """Return trading days in the requested range."""
    raw_start = request.args.get("start", "")
    raw_end = request.args.get("end", "")
    try:
        start = date_type.fromisoformat(raw_start) if raw_start else date_type.today()
        end = date_type.fromisoformat(raw_end) if raw_end else start
    except (ValueError, TypeError):
        return error_response("invalid date format, use YYYY-MM-DD", 400)

    if end < start:
        return error_response("end must be >= start", 400)

    days = trading_days_between(start, end)
    return jsonify(
        {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "total_days": len(days),
            "days": [day.isoformat() for day in days],
        }
    ), 200
