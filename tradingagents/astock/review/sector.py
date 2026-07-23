"""Sector rotation and strength analysis — from Canonical DuckDB only."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd


def compute_sectors(frame: pd.DataFrame, sector_map: dict[str, str] | None = None,
                     previous_dates: list[str] | None = None) -> dict[str, Any]:
    """Compute sector performance, strength and rotation from Canonical kline_bars.

    Parameters
    ----------
    frame : pd.DataFrame
        Must contain columns: symbol, trade_date, close (open optional for change_pct).
    sector_map : dict, optional
        Mapping of symbol -> sector_name.  When omitted only returns summary.
    previous_dates : list, optional
        Previous trade dates for rotation comparison.

    Returns
    -------
    dict with sectors list or ``data_state='unavailable'``.
    """
    required = {"symbol", "trade_date", "close"}
    if not required.issubset(frame.columns):
        return {"data_state": "unavailable", "reason": "missing columns"}

    df = frame.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    if "open" in df.columns:
        df["open"] = pd.to_numeric(df["open"], errors="coerce")
    df = df.dropna(subset=["trade_date", "close"]).reset_index(drop=True)

    if df.empty:
        return {"data_state": "unavailable", "reason": "empty"}

    latest = df["trade_date"].max()
    day = df[df["trade_date"] == latest].copy()

    if "change_pct" not in day.columns:
        if "open" in day.columns:
            day["change_pct"] = (day["close"] - day["open"]) / day["open"].replace(0, float("nan")) * 100
        else:
            day["change_pct"] = 0.0
    day = day.dropna(subset=["change_pct"])

    if sector_map:
        day["sector"] = day["symbol"].map(sector_map)
        day = day.dropna(subset=["sector"])
        groups = day.groupby("sector")

        # Previous day comparison for rotation
        prev_sectors = {}
        if previous_dates:
            prev_df = df[df["trade_date"].isin(pd.to_datetime(previous_dates))].copy()
            if not prev_df.empty and "open" in prev_df.columns:
                prev_df["change_pct"] = (prev_df["close"] - prev_df["open"]) / prev_df["open"].replace(0, float("nan")) * 100
                prev_df["sector"] = prev_df["symbol"].map(sector_map)
                prev_df = prev_df.dropna(subset=["sector"])
                prev_groups = prev_df.groupby("sector")
                for name, grp in prev_groups:
                    prev_sectors[name] = round(float(grp["change_pct"].mean()), 4)

        sectors = []
        for name, grp in groups:
            avg_change = round(float(grp["change_pct"].mean()), 4)
            total_amount = float(grp["amount"].sum()) if "amount" in grp.columns else 0.0
            limit_up = int((grp["change_pct"] >= 9.8).sum())
            prev = prev_sectors.get(name)
            rotation = "strengthening" if prev is not None and avg_change > prev else (
                "weakening" if prev is not None and avg_change < prev else "stable"
            ) if prev is not None else "unknown"
            sectors.append({
                "sector_name": name,
                "change_pct": avg_change,
                "amount": total_amount,
                "limit_up_count": limit_up,
                "member_count": len(grp),
                "rotation_direction": rotation,
            })
        sectors.sort(key=lambda s: s["change_pct"], reverse=True)
        strength = round(float(day["change_pct"].mean()), 4)
    else:
        sectors = []
        strength = round(float(day["change_pct"].mean()), 4)

    seed = json.dumps({"date": str(latest.date()), "sectors": len(sectors)}, sort_keys=True)
    run_id = "sector_" + hashlib.sha256(seed.encode()).hexdigest()[:12]

    return {
        "run_id": run_id,
        "trade_date": str(latest.date()),
        "sectors": sectors,
        "market_strength": strength,
        "sector_rotation": "available",
        "data_state": "available" if sector_map else "partial",
    }


def persist_sectors(conn, result: dict[str, Any]) -> None:
    from tradingagents.astock.review.schema import ensure_review_tables
    ensure_review_tables(conn)
    td = result["trade_date"]
    conn.execute("DELETE FROM sector_performance_daily WHERE trade_date = ?", [td])
    for sec in result.get("sectors", []):
        conn.execute("""INSERT INTO sector_performance_daily VALUES (?,?,?,?,?,?,?,?,?,?,?)""", [
            td, sec["sector_name"], "industry", sec["change_pct"],
            sec["amount"], 0.0, 0.0, sec["limit_up_count"],
            0.0, 0, sec.get("rotation_direction", "unknown"),
        ])
    conn.commit()
