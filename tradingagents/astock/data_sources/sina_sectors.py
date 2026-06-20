"""Sina Finance sector (板块) data via AKShare.

Alternative to EastMoney's push2 API which is often unreachable outside
trading hours.  Uses Sina's sector-endpoint through AKShare's
``stock_sector_spot()``, so it works even when EastMoney is blocked.

Returns the same shape as ``industry_comparison`` in ``eastmoney.py``
so the frontend doesn't need to change.
"""

from __future__ import annotations

from typing import Any


def industry_comparison(top_n: int = 100) -> dict[str, Any]:
    """Industry sector ranking by change percentage via Sina Finance.

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
    import akshare as ak

    df = ak.stock_sector_spot()
    if df is None or df.empty:
        return {"top": [], "bottom": [], "total": 0}

    rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        total_stocks = int(row.get("公司家数", 0))
        rows.append(
            {
                "rank": i + 1,
                "name": str(row.get("板块", "")),
                "change_pct": round(float(row.get("涨跌幅", 0)), 2),
                "code": str(row.get("label", "")),
                "market_cap": 0,  # Sina data does not provide market cap
                "circulating_cap": 0,
                "up_count": 0,  # Sina data does not provide up/down split
                "down_count": 0,
                "leader": str(row.get("股票名称", "")),
                "leader_change": round(float(row.get("个股-涨跌幅", 0)), 2),
            }
        )

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
    }
