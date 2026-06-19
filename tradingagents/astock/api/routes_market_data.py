"""Market data API routes — dragon & tiger, sector rotation, north-bound capital.

All endpoints return JSON.  Error responses follow ``{\"error\": ..., \"status\": N}``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import Blueprint, Response, jsonify, request

from tradingagents.astock.data_sources.eastmoney import (
    concept_blocks,
    daily_dragon_tiger,
    hsgt_realtime,
    industry_comparison,
)

bp = Blueprint("market_data", __name__)


# ---------------------------------------------------------------------------
# GET /api/v1/market/dragon-tiger — 全市场龙虎榜
# ---------------------------------------------------------------------------


@bp.route("/market/dragon-tiger")
def dragon_tiger() -> tuple[Response, int]:
    """Fetch daily dragon & tiger board.

    Query params:
        date (str) — YYYY-MM-DD (default: today)
        min_net_buy (float) — minimum net buy in 10k CNY
        mock (bool) — use synthetic data for testing
    """
    if request.args.get("mock", "0") == "1":
        return jsonify(_mock_dragon_tiger()), 200

    trade_date = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")
    min_net_buy = request.args.get("min_net_buy")
    min_net_buy_f = float(min_net_buy) if min_net_buy else None

    try:
        data = daily_dragon_tiger(trade_date=trade_date, min_net_buy=min_net_buy_f)
        return jsonify(data), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/market/sectors — 行业板块排名
# ---------------------------------------------------------------------------


@bp.route("/market/sectors")
def sectors() -> tuple[Response, int]:
    """Industry sector ranking.

    Query params:
        top_n (int) — number of sectors (default 20)
        mock (bool) — use synthetic data for testing
    """
    if request.args.get("mock", "0") == "1":
        return jsonify(_mock_sectors()), 200

    top_n = int(request.args.get("top_n", 20))
    try:
        data = industry_comparison(top_n=top_n)
        return jsonify(data), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/market/northbound — 北向资金
# ---------------------------------------------------------------------------


@bp.route("/market/northbound")
def northbound() -> tuple[Response, int]:
    """Shanghai / Shenzhen Stock Connect real-time flow.

    Query params:
        mock (bool) — use synthetic data for testing
    """
    if request.args.get("mock", "0") == "1":
        return jsonify(_mock_northbound()), 200

    try:
        data = hsgt_realtime()
        return jsonify({"flow": data, "total_points": len(data)}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/market/blocks — 个股所属概念/行业/地域板块
# ---------------------------------------------------------------------------


@bp.route("/market/blocks")
def stock_blocks() -> tuple[Response, int]:
    """Concept / industry / region blocks a stock belongs to."""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return jsonify({"error": "symbol is required", "status": 400}), 400

    if request.args.get("mock", "0") == "1":
        limit = int(request.args.get("limit", 10))
        data = _mock_stock_blocks(symbol)
        data["items"] = data["items"][:limit]
        data["count"] = len(data["items"])
        return jsonify(data), 200

    limit = int(request.args.get("limit", 10))
    try:
        items = concept_blocks(symbol)
        return jsonify({"symbol": symbol, "items": items[:limit], "count": min(len(items), limit)}), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500}), 500


# ---------------------------------------------------------------------------
# Mock data helpers (for testing / offline demo)
# ---------------------------------------------------------------------------


def _mock_dragon_tiger() -> dict[str, Any]:
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_records": 8,
        "stocks": [
            {"code": "002475.SZ", "name": "立讯精密", "reason": "日涨幅偏离值达7%",
             "close": 38.5, "change_pct": 10.0, "net_buy_wan": 12500.0,
             "buy_wan": 28000.0, "sell_wan": 15500.0, "turnover_pct": 8.5},
            {"code": "300750.SZ", "name": "宁德时代", "reason": "连续三个交易日内涨幅偏离值累计达20%",
             "close": 235.0, "change_pct": 7.5, "net_buy_wan": 8900.0,
             "buy_wan": 21000.0, "sell_wan": 12100.0, "turnover_pct": 3.2},
            {"code": "600519.SH", "name": "贵州茅台", "reason": "日振幅值达15%",
             "close": 1680.0, "change_pct": -3.2, "net_buy_wan": -5600.0,
             "buy_wan": 12000.0, "sell_wan": 17600.0, "turnover_pct": 0.8},
            {"code": "000858.SZ", "name": "五粮液", "reason": "日换手率达20%",
             "close": 145.0, "change_pct": 5.2, "net_buy_wan": 3400.0,
             "buy_wan": 8500.0, "sell_wan": 5100.0, "turnover_pct": 18.5},
            {"code": "601318.SH", "name": "中国平安", "reason": "日涨幅偏离值达7%",
             "close": 52.0, "change_pct": 7.0, "net_buy_wan": 6200.0,
             "buy_wan": 15000.0, "sell_wan": 8800.0, "turnover_pct": 2.1},
            {"code": "000333.SZ", "name": "美的集团", "reason": "连续三个交易日内涨幅偏离值累计达20%",
             "close": 72.0, "change_pct": 6.8, "net_buy_wan": 4800.0,
             "buy_wan": 11000.0, "sell_wan": 6200.0, "turnover_pct": 1.5},
            {"code": "002415.SZ", "name": "海康威视", "reason": "日振幅值达15%",
             "close": 35.0, "change_pct": -5.5, "net_buy_wan": -3200.0,
             "buy_wan": 6500.0, "sell_wan": 9700.0, "turnover_pct": 4.2},
            {"code": "600036.SH", "name": "招商银行", "reason": "日涨幅偏离值达7%",
             "close": 38.0, "change_pct": 7.2, "net_buy_wan": 5100.0,
             "buy_wan": 13000.0, "sell_wan": 7900.0, "turnover_pct": 1.8},
        ],
    }


def _mock_sectors() -> dict[str, Any]:
    sectors_data = [
        {"rank": 1, "name": "半导体", "change_pct": 4.8, "code": "BK0912",
         "up_count": 85, "down_count": 3, "leader": "中芯国际", "leader_change": 6.2},
        {"rank": 2, "name": "人工智能", "change_pct": 3.9, "code": "BK1130",
         "up_count": 72, "down_count": 5, "leader": "科大讯飞", "leader_change": 5.5},
        {"rank": 3, "name": "新能源汽车", "change_pct": 3.5, "code": "BK0927",
         "up_count": 68, "down_count": 8, "leader": "比亚迪", "leader_change": 4.2},
        {"rank": 4, "name": "消费电子", "change_pct": 2.8, "code": "BK0913",
         "up_count": 55, "down_count": 10, "leader": "立讯精密", "leader_change": 10.0},
        {"rank": 5, "name": "创新药", "change_pct": 2.5, "code": "BK0962",
         "up_count": 42, "down_count": 6, "leader": "恒瑞医药", "leader_change": 3.8},
        {"rank": 6, "name": "军工", "change_pct": 2.2, "code": "BK0877",
         "up_count": 48, "down_count": 12, "leader": "中航西飞", "leader_change": 4.0},
        {"rank": 7, "name": "光伏", "change_pct": 1.8, "code": "BK0985",
         "up_count": 35, "down_count": 15, "leader": "隆基绿能", "leader_change": 2.5},
        {"rank": 8, "name": "机器人", "change_pct": 1.5, "code": "BK1159",
         "up_count": 30, "down_count": 8, "leader": "绿的谐波", "leader_change": 3.2},
        {"rank": 9, "name": "券商", "change_pct": 1.2, "code": "BK0473",
         "up_count": 38, "down_count": 12, "leader": "中信证券", "leader_change": 1.8},
        {"rank": 10, "name": "白酒", "change_pct": 0.8, "code": "BK0477",
         "up_count": 22, "down_count": 18, "leader": "贵州茅台", "leader_change": -3.2},
    ]
    return {"top": sectors_data, "bottom": sectors_data[-3:], "total": len(sectors_data)}


def _mock_northbound() -> dict[str, Any]:
    # Generate 10 mock data points
    flow = []
    for i in range(10):
        hour = 9 + i // 4
        minute = (i % 4) * 15
        flow.append(
            {
                "time": f"{hour:02d}:{minute:02d}",
                "hgt_yi": round(5.0 + 0.3 * i, 2),
                "sgt_yi": round(3.0 + 0.2 * i, 2),
            }
        )
    return {"flow": flow, "total_points": len(flow)}


def _mock_stock_blocks(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "count": 3,
        "items": [
            {"name": "白酒", "code": "BK0477", "change_pct": 0.8, "lead_stock": "贵州茅台"},
            {"name": "消费", "code": "BK0480", "change_pct": 1.2, "lead_stock": "五粮液"},
            {"name": "沪深300", "code": "BK0500", "change_pct": 0.4, "lead_stock": "贵州茅台"},
        ],
    }
