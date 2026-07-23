"""Market breadth calculator — advancing/declining, new high/low, median change."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

import pandas as pd


def compute_breadth(frame: pd.DataFrame, trade_date: date | None = None) -> dict[str, Any]:
    """Compute market breadth metrics from Canonical kline_bars.

    Parameters
    ----------
    frame : pd.DataFrame
        Must contain columns: symbol, trade_date, open, close (or change_pct).
    trade_date : date, optional
        Explicit review date.  When omitted the latest date in the frame is used.

    Returns
    -------
    dict
        Breadth result with data_state, or ``{'data_state': 'unavailable'}`` when
        input is empty or missing required columns.
    """
    required = {"symbol", "trade_date", "close"}
    if not required.issubset(frame.columns):
        return {"data_state": "unavailable", "reason": "missing required columns"}

    df = frame.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["trade_date", "close"]).reset_index(drop=True)

    if df.empty:
        return {"data_state": "unavailable", "reason": "empty canonical bars"}

    target_date = trade_date or df["trade_date"].max()
    day = df[df["trade_date"] == target_date]
    if day.empty:
        return {"data_state": "unavailable", "reason": f"no data for {target_date}"}

    day = day.copy()
    if "change_pct" not in day.columns and "open" in day.columns:
        day["open"] = pd.to_numeric(day["open"], errors="coerce")
        day["change_pct"] = (day["close"] - day["open"]) / day["open"].replace(0, float("nan")) * 100
        day = day.dropna(subset=["change_pct"])

    if day.empty:
        return {"data_state": "unavailable", "reason": "no valid change_pct"}

    advancing = int((day["change_pct"] > 0).sum())
    declining = int((day["change_pct"] < 0).sum())
    unchanged = int((day["change_pct"] == 0).sum())
    total = advancing + declining + unchanged
    advance_ratio = round(advancing / total, 4) if total else 0.0
    gain_ge_5 = int((day["change_pct"] >= 5).sum())
    loss_le_5 = int((day["change_pct"] <= -5).sum())

    # New high/low: compare each symbol with its own last 20 days
    new_high = 0
    new_low = 0
    for _, row in day.iterrows():
        sym_bars = df[(df["symbol"] == row["symbol"]) & (df["trade_date"] <= target_date)]
        if len(sym_bars) >= 10:
            recent = sym_bars.tail(20)
            if "high" in recent.columns and "low" in recent.columns:
                if row["close"] >= recent["high"].max():
                    new_high += 1
                if row["close"] <= recent["low"].min():
                    new_low += 1

    median_change = round(float(day["change_pct"].median()), 4)

    seed = json.dumps({"date": str(target_date), "advancing": advancing, "declining": declining}, sort_keys=True)
    run_id = "breadth_" + hashlib.sha256(seed.encode()).hexdigest()[:12]

    return {
        "run_id": run_id,
        "trade_date": str(target_date),
        "advancing": advancing,
        "declining": declining,
        "unchanged": unchanged,
        "total_traded": total,
        "advance_ratio": advance_ratio,
        "gain_ge_5pct": gain_ge_5,
        "loss_le_5pct": loss_le_5,
        "new_high": new_high,
        "new_low": new_low,
        "median_change_pct": median_change,
        "data_state": "available",
    }


def persist_breadth(conn, result: dict[str, Any]) -> None:
    from tradingagents.astock.review.schema import ensure_review_tables
    ensure_review_tables(conn)
    td = result["trade_date"]
    conn.execute("""DELETE FROM market_breadth_daily WHERE trade_date = ?""", [td])
    conn.execute("""INSERT INTO market_breadth_daily VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", [
        td, result["advancing"], result["declining"], result["unchanged"],
        result["advance_ratio"], result["gain_ge_5pct"], result["loss_le_5pct"],
        result["new_high"], result["new_low"], result["median_change_pct"],
        result["total_traded"], result["data_state"],
    ])
    conn.commit()
