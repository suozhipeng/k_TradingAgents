"""Sina Finance sector (板块) data via direct API.

Primary source: Sina Finance direct API (newSinaHy.php) which provides
stable industry sector data even when EastMoney/AkShare are unreachable.

Fallback chain:
  1. Sina Finance direct API (newSinaHy.php) ← PRIMARY
  2. AkShare stock_sector_spot()
  3. EastMoney push2 API
  4. Offline mock data (deterministic fallback)

Returns the same shape as ``industry_comparison`` in ``eastmoney.py``
so the frontend doesn't need to change.
"""

from __future__ import annotations

import logging
import random
import time

import re
from typing import Any
logger = logging.getLogger(__name__)

# ── Sina-specific anti-crawl helpers ──────────────────────────────────────

_SINA_LAST_CALL: list[float] = [0.0]
_SINA_MIN_INTERVAL = 1.0  # min seconds between Sina calls


def _sina_emulate_browser() -> None:
    """Random delay before Sina requests to avoid rate limits."""
    wait = _SINA_MIN_INTERVAL - (time.time() - _SINA_LAST_CALL[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))


def _sina_retry(fn, max_attempts: int = 3, base_delay: float = 1.0):
    """Retry with exponential backoff for Sina requests."""
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(delay)
    raise last_exc

try:
    import json
except ImportError:
    json = None  # type: ignore[assignment]


# ── Offline mock data (final fallback) ──────────────────────────────────


def _offline_sector_rows() -> list[dict[str, Any]]:
    """Deterministic fallback rows when all real sources are unavailable."""
    return [
        {"name": "消费白马", "change_pct": 2.86, "code": "BKX001", "leader": "贵州茅台", "leader_change": 1.92},
        {"name": "算力硬件", "change_pct": 2.31, "code": "BKX002", "leader": "中际旭创", "leader_change": 3.18},
        {"name": "高股息金融", "change_pct": 1.67, "code": "BKX003", "leader": "建设银行", "leader_change": 1.04},
        {"name": "创新药", "change_pct": 1.21, "code": "BKX004", "leader": "药明康德", "leader_change": 2.11},
        {"name": "新能源整车", "change_pct": 0.88, "code": "BKX005", "leader": "比亚迪", "leader_change": 1.47},
        {"name": "半导体设备", "change_pct": -0.36, "code": "BKX006", "leader": "北方华创", "leader_change": -0.42},
        {"name": "稀土永磁", "change_pct": -0.74, "code": "BKX007", "leader": "北方稀土", "leader_change": -0.66},
        {"name": "光伏组件", "change_pct": -1.08, "code": "BKX008", "leader": "隆基绿能", "leader_change": -0.95},
    ]


# ── Sina Finance direct API ─────────────────────────────────────────────


def _fetch_sina_industry() -> list[dict[str, Any]]:
    """Fetch industry sector data from Sina Finance direct API.

    URL: https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php

    Returns parsed sector list with change_pct, volume, leader info.
    """
    rows = []
    try:
        import requests

        url = "https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://finance.sina.com.cn/",
        }

        def _do_fetch():
            _sina_emulate_browser()
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200 or len(r.text) < 200:
                return []
            return re.findall(r'"([^"]+)":"([^"]*)"', r.text)

        pairs = _sina_retry(_do_fetch, max_attempts=3, base_delay=1.0)
        if not pairs:
            return []
        if not pairs:
            return []

        # Each sector has 13 comma-separated fields:
        # key, name, count, avg_price, change_pct, change_amount,
        # volume, amount, leader_code, leader_price, leader_high,
        # leader_low, leader_name
        fields_per_board = 13
        for _, val in pairs:
            parts = val.split(",")
            if len(parts) >= fields_per_board:
                change_pct = parts[4]
                rows.append(
                    {
                        "name": parts[1],
                        "change_pct": round(float(change_pct), 4) if change_pct and change_pct != "-" else 0.0,
                        "code": parts[0],
                        "count": int(parts[2]) if parts[2].isdigit() else 0,
                        "avg_price": round(float(parts[3]), 2) if parts[3] else 0,
                        "volume": parts[6],
                        "amount": parts[7],
                        "leader_code": parts[8],
                        "leader_price": round(float(parts[9]), 2) if parts[9] else 0,
                        "leader_high": round(float(parts[10]), 2) if parts[10] else 0,
                        "leader_low": round(float(parts[11]), 2) if parts[11] else 0,
                        "leader": parts[12],
                        "leader_change": 0,  # Not available in this format
                        "market_cap": 0,
                        "circulating_cap": 0,
                        "up_count": 0,
                        "down_count": 0,
                    }
                )

    except Exception:
        rows = []

    return rows


# ── AkShare fallback ────────────────────────────────────────────────────


def _fetch_akshare_industry() -> list[dict[str, Any]]:
    """Fetch industry sector data via AkShare.

    Fallback when Sina API is unavailable.
    """
    rows = []
    try:
        import akshare as ak

        df = ak.stock_sector_spot()
        if df is not None and not df.empty:
            for i, (_, row) in enumerate(df.iterrows()):
                rows.append(
                    {
                        "rank": i + 1,
                        "name": str(row.get("板块", "")),
                        "change_pct": round(float(row.get("涨跌幅", 0)), 2),
                        "code": str(row.get("label", "")),
                        "market_cap": 0,
                        "circulating_cap": 0,
                        "up_count": 0,
                        "down_count": 0,
                        "leader": str(row.get("股票名称", "")),
                        "leader_change": round(float(row.get("个股-涨跌幅", 0)), 2),
                    }
                )
    except Exception:
        rows = []

    return rows


# ── EastMoney push2 fallback ────────────────────────────────────────────


def _fetch_eastmoney_industry(top_n: int = 100) -> list[dict[str, Any]]:
    """Fetch industry sector data from EastMoney push2 API.

    Fallback when both Sina and AkShare are unavailable.
    """
    rows = []
    try:
        import requests

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
                "Referer": "https://quote.eastmoney.com/",
                "Accept": "*/*",
            }
        )

        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1",
            "pz": str(top_n),
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "m:90+t:2,m:90+t:3,m:90+t:4,m:90+t:5",
            "fields": "f12,f14,f3,f2,f4,f104,f105,f140",
        }

        r = session.get(url, params=params, timeout=10)
        d = r.json()
        items = d.get("data", {}).get("diff", [])

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
    except Exception:
        rows = []

    return rows


# ── Main public API ─────────────────────────────────────────────────────


def industry_comparison(top_n: int = 100) -> dict[str, Any]:
    """Industry sector ranking by change percentage.

    Priority order:
      1. Sina Finance direct API (newSinaHy.php) ← PRIMARY
      2. AkShare stock_sector_spot()
      3. EastMoney push2 API
      4. Offline mock data (deterministic fallback)

    Parameters
    ----------
    top_n : int
        Number of top/bottom sectors to return.

    Returns
    -------
    dict with keys: ``top``, ``bottom``, ``total``.
    Each entry has: ``rank``, ``name``, ``change_pct``, ``code``,
    ``up_count``, ``down_count`` (estimated), ``leader``,
    ``leader_change``, ``market_cap`` (0 = unavailable from Sina).
    """
    rows = []
    source = "mock"

    # Priority 1: Sina Finance direct API
    rows = _fetch_sina_industry()
    if rows:
        source = "sina"
    else:
        # Priority 2: AkShare
        rows = _fetch_akshare_industry()
        if rows:
            source = "akshare"
        else:
            # Priority 3: EastMoney push2
            rows = _fetch_eastmoney_industry(top_n)
            if rows:
                source = "eastmoney"
            else:
                # Priority 4: Offline mock
                for i, row in enumerate(_offline_sector_rows()):
                    rows.append(
                        {
                            "rank": i + 1,
                            "name": row["name"],
                            "change_pct": row["change_pct"],
                            "code": row["code"],
                            "market_cap": 0,
                            "circulating_cap": 0,
                            "up_count": 0,
                            "down_count": 0,
                            "leader": row["leader"],
                            "leader_change": row["leader_change"],
                        }
                    )
                    source = "mock"

    # Sort by change_pct descending
    rows.sort(key=lambda x: x["change_pct"], reverse=True)

    # Re-rank after sorting
    for i, r in enumerate(rows):
        r["rank"] = i + 1

    n = min(top_n, len(rows))
    return {
        "top": rows[:n],
        "bottom": rows[-n:] if n > 0 else [],
        "total": len(rows),
        "_source": source,
    }
