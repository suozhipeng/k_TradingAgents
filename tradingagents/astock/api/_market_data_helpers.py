"""Internal helpers for market-data routes.

Keeps route registration in ``routes_market_data.py`` while moving fallback,
mock, and momentum support into a dedicated module.
"""

from __future__ import annotations

import logging
import random
import hashlib
from datetime import date as date_type
from datetime import datetime
from typing import Any

from tradingagents.astock.data_sources.calendar import (
    is_trading_day,
    prev_trading_day,
)
from tradingagents.astock.data_sources.leading_pool import get_dynamic_leading_pool
from tradingagents.astock.data_sources.router import AStockDataFacade
from tradingagents.astock.execution.strategies.momentum_rotation import (
    get_leading_stocks,
)

logger = logging.getLogger(__name__)
router = AStockDataFacade()


def query_duckdb_valuations(
    symbol: str | None = None,
    top_n: int = 20,
) -> dict[str, Any] | None:
    """Query recent valuation-like records from DuckDB as a fallback source.

    Uses the store's existing DuckDB connection instead of opening a
    separate ``duckdb.connect()`` to avoid double-connection conflicts.
    """
    from flask import current_app

    store = current_app.config.get("STORE") if current_app else None
    if store is None:
        return None
    try:
        conn = getattr(store, "conn", None) or getattr(store, "_conn", None)
        if conn is None:
            return None

        result = None
        if symbol:
            rows = conn.execute(
                "SELECT symbol, trade_date, pe, pb, market_cap, source FROM valuations "
                "WHERE symbol = ? ORDER BY trade_date DESC LIMIT ?",
                [symbol, top_n],
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT symbol, trade_date, pe, pb, market_cap, source FROM valuations "
                "ORDER BY trade_date DESC LIMIT ?",
                [top_n],
            ).fetchall()
        if rows:
            result = {
                "source": "duckdb",
                "rows": [
                    {
                        "symbol": str(row[0]),
                        "trade_date": str(row[1]),
                        "pe": float(row[2]) if row[2] is not None else None,
                        "pb": float(row[3]) if row[3] is not None else None,
                        "market_cap": float(row[4]) if row[4] is not None else None,
                        "data_source": str(row[5]),
                    }
                    for row in rows
                ],
            }
        return result
    except Exception as exc:
        logger.debug("DuckDB fallback query failed: %s", exc)
        return None


def fallback_note(source: str) -> str:
    """Generate a user-facing note for the current data source."""
    notes = {
        "real": "",
        "duckdb": "⚠️ 实时接口不可用，展示的是最近一次拉取的真实数据",
        "mock": "⚠️ 实时数据不可用，展示的是模拟数据（非交易时段或网络限制）",
    }
    return notes.get(source, "")


def resolve_trade_date(raw_date: str | None = None) -> tuple[str, str, bool]:
    """Resolve a trade date, falling back to the previous trading day.

    If ``is_trading_day()`` fails (network unavailable), tries DuckDB
    valuations table for the most recent known trade date as a last resort.
    """
    if raw_date:
        value = raw_date
    else:
        value = datetime.now().strftime("%Y-%m-%d")

    try:
        dt = date_type.fromisoformat(value)
        if is_trading_day(dt):
            return value, "today", False
        prev = prev_trading_day(dt)
        return prev.isoformat(), f"prev({value})", True
    except (ValueError, TypeError):
        return value, "invalid", False
    except Exception:
        # is_trading_day() failed (network) — fall back to DuckDB
        try:
            from flask import current_app
            store = current_app.config.get("STORE") if current_app else None
            if store and hasattr(store, "query_kline"):
                # Try to get the latest trade_date from any symbol's kline
                symbols = store.list_symbols()
                if symbols:
                    df = store.query_kline(symbols[0], interval="1d", limit=1)
                    if df is not None and not df.empty and "bar_time" in df.columns:
                        latest = df.iloc[-1]["bar_time"]
                        return str(latest)[:10], "duckdb_fallback", True
        except Exception:
            pass
        return value, "network_unavailable", False


def get_current_leading_stocks() -> list[dict[str, Any]]:
    """Return the current leading-stock pool using dynamic data when possible."""
    try:
        leaders, source = get_dynamic_leading_pool()
        if leaders:
            return [
                {
                    "symbol": leader.get("symbol", ""),
                    "name": leader.get("name", ""),
                    "sector": leader.get("sector", ""),
                    "price": leader.get("price", 0),
                    "change_pct": leader.get("leader_change", 0),
                    "turnover_rate": leader.get("turnover_rate", 0),
                    "market_cap": leader.get("market_cap", 0),
                    "pb": leader.get("pb", 0),
                    "pool_source": source,
                }
                for leader in leaders
            ]
    except Exception as exc:
        logger.warning("Dynamic leading pool failed, using fallback: %s", exc)

    fallback, _ = get_leading_stocks()
    return [{**stock, "pool_source": "fallback"} for stock in fallback]


def fetch_real_momentum() -> list[dict[str, Any]]:
    """Fetch leading-stock valuation data with fallback-safe defaults."""
    leading_stocks = get_current_leading_stocks()

    stocks: list[dict[str, Any]] = []
    for stock in leading_stocks:
        symbol = stock.get("symbol", "")
        name = stock.get("name", "")
        sector = stock.get("sector", "")

        if not symbol and not name:
            continue

        try:
            if symbol:
                resp = router.get_valuation(symbol)
                if resp.status == "ok" and resp.data and isinstance(resp.data, dict):
                    price = resp.data.get("price", 0)
                    stocks.append(
                        {
                            "symbol": symbol,
                            "name": name or stock.get("name", ""),
                            "sector": sector or stock.get("sector", ""),
                            "price": round(price, 2),
                            "turnover_rate": resp.data.get("turnover_rate", 0),
                            "market_cap": resp.data.get("market_cap", 0),
                            "pb": resp.data.get("pb", 0),
                            "source": "real",
                            "pool_source": stock.get("pool_source", "unknown"),
                        }
                    )
                    continue
            if stock.get("price", 0) > 0:
                stocks.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "sector": sector,
                        "price": stock.get("price", 0),
                        "turnover_rate": stock.get("turnover_rate", 0),
                        "market_cap": stock.get("market_cap", 0),
                        "pb": stock.get("pb", 0),
                        "source": "fallback",
                        "pool_source": stock.get("pool_source", "fallback"),
                    }
                )
            else:
                stocks.append(_fallback_stock(symbol, name, sector, stock.get("pool_source", "fallback")))
        except Exception:
            stocks.append(_fallback_stock(symbol, name, sector, stock.get("pool_source", "fallback")))
    return stocks


def compute_momentum_scores(real_stocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute momentum scores with deterministic fallback values.

    When real price/turnover/market_cap data is available, scores are computed
    from those fields.  When all data is unavailable (source=fallback), a
    deterministic hash-based score is derived from the stock symbol so that
    results are stable across calls but still differentiate each stock.
    """
    has_real = any(stock["source"] == "real" and stock["price"] > 0 for stock in real_stocks)

    if has_real:
        prices = [stock["price"] for stock in real_stocks if stock["price"] > 0]
        if prices:
            min_p, max_p = min(prices), max(prices)
            price_range = max_p - min_p if max_p != min_p else 1.0
        else:
            min_p = 0
            price_range = 1.0

        for stock in real_stocks:
            if stock["price"] > 0:
                price_rank = (stock["price"] - min_p) / price_range * 100
                turnover_score = min(stock["turnover_rate"] * 50, 30)
                cap_score = min(stock["market_cap"] / 100, 30)
                stock["momentum_score"] = round(
                    min(price_rank * 0.4 + turnover_score + cap_score, 100),
                    1,
                )
            else:
                stock["momentum_score"] = 0.0
    else:
        # Use a cryptographic digest rather than Python's process-salted hash.
        for index, stock in enumerate(real_stocks):
            symbol = stock.get("symbol", "") or stock.get("name", "")
            if not symbol:
                symbol = f"stock_{index}"
            # Hash the symbol to get a stable base in [0, 99].
            h = int.from_bytes(hashlib.sha256(symbol.encode("utf-8")).digest()[:2], "big")
            base_score = (h % 95) + 5  # 5..99
            stock["momentum_score"] = round(base_score, 1)
            stock["source"] = "fallback"

    real_stocks.sort(key=lambda item: item["momentum_score"], reverse=True)
    for index, item in enumerate(real_stocks, start=1):
        item["rank"] = index
    return real_stocks


def mock_dragon_tiger() -> dict[str, Any]:
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


def mock_sectors() -> dict[str, Any]:
    sectors_data = [
        {"rank": 1, "name": "半导体", "change_pct": 4.8, "code": "BK0912",
         "up_count": 85, "down_count": 3, "leader": "中芯国际", "leader_change": 6.2,
         "market_cap": 3580000000000, "circulating_cap": 2850000000000},
        {"rank": 2, "name": "人工智能", "change_pct": 3.9, "code": "BK1130",
         "up_count": 72, "down_count": 5, "leader": "科大讯飞", "leader_change": 5.5,
         "market_cap": 4200000000000, "circulating_cap": 3100000000000},
        {"rank": 3, "name": "新能源汽车", "change_pct": 3.5, "code": "BK0927",
         "up_count": 68, "down_count": 8, "leader": "比亚迪", "leader_change": 4.2,
         "market_cap": 5100000000000, "circulating_cap": 3800000000000},
        {"rank": 4, "name": "消费电子", "change_pct": 2.8, "code": "BK0913",
         "up_count": 55, "down_count": 10, "leader": "立讯精密", "leader_change": 10.0,
         "market_cap": 2800000000000, "circulating_cap": 2100000000000},
        {"rank": 5, "name": "创新药", "change_pct": 2.5, "code": "BK0962",
         "up_count": 42, "down_count": 6, "leader": "恒瑞医药", "leader_change": 3.8,
         "market_cap": 1900000000000, "circulating_cap": 1650000000000},
        {"rank": 6, "name": "军工", "change_pct": 2.2, "code": "BK0877",
         "up_count": 48, "down_count": 12, "leader": "中航西飞", "leader_change": 4.0,
         "market_cap": 2200000000000, "circulating_cap": 1500000000000},
        {"rank": 7, "name": "光伏", "change_pct": 1.8, "code": "BK0985",
         "up_count": 35, "down_count": 15, "leader": "隆基绿能", "leader_change": 2.5,
         "market_cap": 1600000000000, "circulating_cap": 1350000000000},
        {"rank": 8, "name": "机器人", "change_pct": 1.5, "code": "BK1159",
         "up_count": 30, "down_count": 8, "leader": "绿的谐波", "leader_change": 3.2,
         "market_cap": 980000000000, "circulating_cap": 720000000000},
        {"rank": 9, "name": "券商", "change_pct": 1.2, "code": "BK0473",
         "up_count": 38, "down_count": 12, "leader": "中信证券", "leader_change": 1.8,
         "market_cap": 4500000000000, "circulating_cap": 3800000000000},
        {"rank": 10, "name": "白酒", "change_pct": 0.8, "code": "BK0477",
         "up_count": 22, "down_count": 18, "leader": "贵州茅台", "leader_change": -3.2,
         "market_cap": 3800000000000, "circulating_cap": 3500000000000},
    ]
    return {"top": sectors_data, "bottom": sectors_data[-3:], "total": len(sectors_data)}


def mock_northbound() -> dict[str, Any]:
    flow = []
    for index in range(10):
        hour = 9 + index // 4
        minute = (index % 4) * 15
        flow.append(
            {
                "time": f"{hour:02d}:{minute:02d}",
                "hgt_yi": round(5.0 + 0.3 * index, 2),
                "sgt_yi": round(3.0 + 0.2 * index, 2),
            }
        )
    return {"flow": flow, "total_points": len(flow)}


def mock_stock_blocks(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "count": 3,
        "items": [
            {"name": "白酒", "code": "BK0477", "change_pct": 0.8, "lead_stock": "贵州茅台"},
            {"name": "消费", "code": "BK0480", "change_pct": 1.2, "lead_stock": "五粮液"},
            {"name": "沪深300", "code": "BK0500", "change_pct": 0.4, "lead_stock": "贵州茅台"},
        ],
    }


def _fallback_stock(symbol: str, name: str, sector: str, pool_source: str = "fallback") -> dict[str, Any]:
    return {
        "symbol": symbol,
        "name": name,
        "sector": sector,
        "price": 0,
        "turnover_rate": 0,
        "market_cap": 0,
        "pb": 0,
        "source": "fallback",
        "pool_source": pool_source,
    }
