"""EastMoney data API — rate-limited HTTP client + data functions.

Provides a unified rate-limited HTTP client (``em_get``) and data retrieval
functions for EastMoney datacenter / push2 endpoints, following the same
anti-crawling patterns used in the upstream a-stock-data SKILL.

All eastmoney.com requests go through ``em_get()`` which enforces:
- Serial rate limiting (min interval + jitter)
- Reusable session (Keep-Alive)
- Default User-Agent
"""

from __future__ import annotations

import logging

import random
import time
from datetime import datetime
from typing import Any

import requests

from .calendar import prev_trading_day
logger = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

# ── Rate-limited HTTP client ─────────────────────────────────────────────

_session = requests.Session()
_session.headers.update({"User-Agent": UA})

EM_MIN_INTERVAL = 1.0  # min seconds between EastMoney calls
_last_call: list[float] = [0.0]  # module-level last-call timestamp


def em_get(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = 15,
    **kwargs: Any,
) -> requests.Response:
    """EastMoney unified HTTP request with rate limiting.

    All ``eastmoney.com`` endpoints should use this instead of raw
    ``requests.get`` to avoid IP blocking.
    """
    wait = EM_MIN_INTERVAL - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        return _session.get(
            url, params=params, headers=headers, timeout=timeout, **kwargs
        )
    finally:
        _last_call[0] = time.time()


def set_min_interval(seconds: float) -> None:
    """Adjust the minimum interval between EastMoney calls."""
    global EM_MIN_INTERVAL  # noqa: PLW0603
    EM_MIN_INTERVAL = seconds


# ── Datacenter query helper ──────────────────────────────────────────────


def datacenter_query(
    report_name: str,
    columns: str = "ALL",
    filter_str: str = "",
    page_size: int = 50,
    sort_columns: str = "",
    sort_types: str = "-1",
) -> list[dict]:
    """EastMoney datacenter unified query.

    Used by: dragon & tiger, lock-up calendar, margin trading,
    block trading, shareholder counts, dividends.
    """
    params: dict[str, str] = {
        "reportName": report_name,
        "columns": columns,
        "filter": filter_str,
        "pageNumber": "1",
        "pageSize": str(page_size),
        "sortColumns": sort_columns,
        "sortTypes": sort_types,
        "source": "WEB",
        "client": "WEB",
    }
    r = em_get(DATACENTER_URL, params=params, timeout=15)
    d = r.json()
    if d.get("result") and d["result"].get("data"):
        return d["result"]["data"]  # type: ignore[no-any-return]
    return []


# ── Dragon & Tiger (龙虎榜) ────────────────────────────────────────────


def daily_dragon_tiger(
    trade_date: str | None = None,
    min_net_buy: float | None = None,
) -> dict[str, Any]:
    """Full market dragon & tiger board for a given date.

    Parameters
    ----------
    trade_date : str or None
        YYYY-MM-DD.  Defaults to today.
    min_net_buy : float or None
        Minimum net buy amount in 10k CNY.  ``None`` = no filter.

    Returns
    -------
    dict with keys: ``date``, ``total_records``, ``stocks``.
    Each stock has: ``code``, ``name``, ``reason``, ``close``,
    ``change_pct``, ``net_buy_wan``, ``buy_wan``, ``sell_wan``,
    ``turnover_pct``.
    """
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")

    data = datacenter_query(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        filter_str=f"(TRADE_DATE>='{trade_date}')(TRADE_DATE<='{trade_date}')",
        page_size=500,
        sort_columns="BILLBOARD_NET_AMT",
        sort_types="-1",
    )
    if not data:
        # Non-trading day or data not yet published — fall back to previous trading day
        from datetime import date as date_type
        try:
            today = date_type.fromisoformat(trade_date)
            prev = prev_trading_day(today)
            prev_date = prev.isoformat()
            data = datacenter_query(
                "RPT_DAILYBILLBOARD_DETAILSNEW",
                filter_str=f"(TRADE_DATE>='{prev_date}')(TRADE_DATE<='{prev_date}')",
                page_size=500,
                sort_columns="BILLBOARD_NET_AMT",
                sort_types="-1",
            )
            if data:
                trade_date = prev_date
            else:
                return {
                    "date": trade_date,
                    "total_records": 0,
                    "stocks": [],
                    "note": "无数据（非交易日或盘后未更新）",
                }
        except Exception:
            return {
                "date": trade_date,
                "total_records": 0,
                "stocks": [],
                "note": "无数据（非交易日或盘后未更新）",
            }

    actual_date = str(data[0].get("TRADE_DATE", ""))[:10] if data else trade_date
    stocks = []
    for row in data:
        net_buy = (row.get("BILLBOARD_NET_AMT") or 0) / 10000
        if min_net_buy is not None and net_buy < min_net_buy:
            continue
        stocks.append(
            {
                "code": row.get("SECURITY_CODE", ""),
                "name": row.get("SECURITY_NAME_ABBR", ""),
                "reason": row.get("EXPLANATION", ""),
                "close": float(row.get("CLOSE_PRICE") or 0),
                "change_pct": round(float(row.get("CHANGE_RATE") or 0), 2),
                "net_buy_wan": round(net_buy, 1),
                "buy_wan": round((row.get("BILLBOARD_BUY_AMT") or 0) / 10000, 1),
                "sell_wan": round((row.get("BILLBOARD_SELL_AMT") or 0) / 10000, 1),
                "turnover_pct": round(float(row.get("TURNOVERRATE") or 0), 2),
            }
        )
    return {"date": actual_date, "total_records": len(stocks), "stocks": stocks}


# ── Sector rotation (行业板块排名) ──────────────────────────────────────


def industry_comparison(top_n: int = 20) -> dict[str, Any]:
    """Industry sector ranking by change percentage.

    Parameters
    ----------
    top_n : int
        Number of top/bottom sectors to return.

    Returns
    -------
    dict with keys: ``top``, ``bottom``, ``total``.
    Each entry has: ``rank``, ``name``, ``change_pct``, ``code``,
    ``up_count``, ``down_count``, ``leader``, ``leader_change``,
    ``market_cap`` (总市值, in CNY).
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params: dict[str, str] = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fs": "m:90+t:2",
        "fields": "f2,f3,f4,f12,f13,f14,f20,f21,f104,f105,f128,f136,f140,f141,f207",
    }
    r = em_get(url, params=params, timeout=15)
    d = r.json()
    items = d.get("data", {}).get("diff", [])
    if not items:
        return {"top": [], "bottom": [], "total": 0}

    rows = []
    for i, item in enumerate(items):
        rows.append(
            {
                "rank": i + 1,
                "name": item.get("f14", ""),
                "change_pct": item.get("f3", 0),
                "code": item.get("f12", ""),
                "market_cap": item.get("f20", 0),
                "circulating_cap": item.get("f21", 0),
                "up_count": item.get("f104", 0),
                "down_count": item.get("f105", 0),
                "leader": item.get("f140", ""),
                "leader_change": item.get("f136", 0),
            }
        )

    return {
        "top": rows[:top_n],
        "bottom": rows[-top_n:],
        "total": len(rows),
    }


# ── North-bound capital (北向资金) ─────────────────────────────────────


def hsgt_realtime() -> list[dict]:
    """Shanghai / Shenzhen Stock Connect real-time minute-level flow.

    Returns a list of dicts with keys: ``time``, ``hgt_yi``, ``sgt_yi``.
    Units: 100 million CNY.
    """
    try:
        r = em_get(
            "https://data.hexin.cn/market/hsgtApi/method/dayChart/",
            headers={
                "User-Agent": UA,
                "Host": "data.hexin.cn",
                "Referer": "https://data.hexin.cn/",
            },
            timeout=10,
        )
        d = r.json()
        times = d.get("time", [])
        hgt = d.get("hgt", [])
        sgt = d.get("sgt", [])
        n = len(times)
        result = []
        for i in range(n):
            result.append(
                {
                    "time": times[i] if i < len(times) else "",
                    "hgt_yi": hgt[i] if i < len(hgt) else None,
                    "sgt_yi": sgt[i] if i < len(sgt) else None,
                }
            )
        return result
    except Exception:
        return []


def concept_blocks(symbol: str) -> list[dict]:
    """Concept / industry / region blocks a stock belongs to.

    Returns a list of dicts: ``name``, ``code`` (BK code),
    ``change_pct``, ``lead_stock``.
    """
    url = "https://push2.eastmoney.com/api/qt/slist/get"
    params: dict[str, str] = {
        "fltt": "2",
        "invt": "2",
        "fields": "f14,f12,f3,f4,f104,f105",
        "type": "14",
        "fid": "f3",
        "sort": "f3",
        "np": "1",
        "pageSize": "500",
        "pageNum": "1",
        "seccode": symbol.split(".")[0] if "." in symbol else symbol,
        "slist": "true",
        "spt": "3",
    }
    try:
        r = em_get(url, params=params, timeout=15)
        d = r.json()
        items = d.get("data", {}).get("diff", []) or []
        boards = []
        for item in items:
            boards.append(
                {
                    "name": item.get("f14", ""),
                    "code": item.get("f12", ""),
                    "change_pct": item.get("f3", 0),
                    "lead_stock": item.get("f140", ""),
                }
            )
        return boards
    except Exception:
        return []
