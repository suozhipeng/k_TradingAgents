"""Market leaders — limit-up ladders, volume leaders, new high/low, strong/weak."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd


def compute_leaders(frame: pd.DataFrame) -> dict[str, Any]:
    """Compute limit-up ladders, volume leaders, and new high/low from canonical bars.

    Parameters
    ----------
    frame : pd.DataFrame
        Must contain columns: symbol, trade_date, open, close.
        Optional: volume, amount, turnover_rate.

    Returns
    -------
    dict with leaders lists or ``data_state='unavailable'``.
    """
    required = {"symbol", "trade_date", "open", "close"}
    if not required.issubset(frame.columns):
        return {"data_state": "unavailable", "reason": "missing columns"}

    df = frame.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    for col in ["open", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df = df.dropna(subset=["trade_date", "open", "close"]).reset_index(drop=True)

    if df.empty:
        return {"data_state": "unavailable", "reason": "empty"}

    latest_date = df["trade_date"].max()
    today = df[df["trade_date"] == latest_date].copy()

    # Change pct for today
    if "change_pct" not in today.columns:
        today["change_pct"] = (today["close"] - today["open"]) / today["open"].replace(0, float("nan")) * 100

    # Limit-up stocks (A-share: close >= open * 1.098 for ST * 1.05, simplified to 9.5%)
    limit_up = today[today["change_pct"] >= 9.5].sort_values("change_pct", ascending=False)
    limit_down = today[today["change_pct"] <= -9.5].sort_values("change_pct")

    # Volume leaders (top 20 by amount or volume)
    vol_col = None
    for col in ("amount", "volume", "turnover_rate"):
        if col in today.columns:
            vol_col = col
            break
    if vol_col:
        volume_leaders = today.nlargest(20, vol_col)[["symbol", "close", vol_col, "change_pct"]]
    else:
        volume_leaders = pd.DataFrame(columns=["symbol", "close", "change_pct"])

    # New high: close >= max of last 20 days
    new_high = []
    new_low = []
    lookback = df[df["trade_date"] <= latest_date].tail(200)
    for _, row in today.iterrows():
        sym_bars = lookback[lookback["symbol"] == row["symbol"]]
        if len(sym_bars) >= 10:
            if row["close"] >= sym_bars["close"].max():
                new_high.append(row["symbol"])
            if row["close"] <= sym_bars["close"].min():
                new_low.append(row["symbol"])

    # Limit-up ladder detection: count consecutive limit-up ending at latest_date
    ladders = []
    df_sorted = df.sort_values(["symbol", "trade_date"])
    for sym in limit_up["symbol"].unique():
        sym_bars = df_sorted[df_sorted["symbol"] == sym]
        # Count streak ending at latest_date
        current_streak = 0
        for i in range(len(sym_bars) - 1, -1, -1):
            bar = sym_bars.iloc[i]
            if bar["trade_date"] > latest_date:
                continue
            change = (bar["close"] - bar["open"]) / bar["open"] * 100 if bar["open"] > 0 else 0
            if change >= 9.5:
                if current_streak == 0 or (i + 1 < len(sym_bars) and
                    (sym_bars.iloc[i + 1]["trade_date"] - bar["trade_date"]).days <= 2):
                    current_streak += 1
                else:
                    break
            else:
                if current_streak > 0:
                    break
        if current_streak > 0:
            ladders.append({"symbol": sym, "ladder_height": current_streak})

    ladders.sort(key=lambda x: x["ladder_height"], reverse=True)

    seed = json.dumps({"date": str(latest_date.date()), "limit_up": len(limit_up), "ladders": len(ladders)}, sort_keys=True)
    run_id = "leaders_" + hashlib.sha256(seed.encode()).hexdigest()[:12]

    return {
        "run_id": run_id,
        "trade_date": str(latest_date.date()),
        "limit_up_stocks": [
            {"symbol": r["symbol"], "change_pct": round(float(r["change_pct"]), 2)}
            for _, r in limit_up.head(50).iterrows()
        ],
        "limit_down_stocks": [
            {"symbol": r["symbol"], "change_pct": round(float(r["change_pct"]), 2)}
            for _, r in limit_down.head(50).iterrows()
        ],
        "limit_up_ladders": ladders,
        "volume_leaders": [
            {"symbol": r["symbol"], "change_pct": round(float(r["change_pct"]), 2), "amount": round(float(r[vol_col]), 2)}
            for _, r in volume_leaders.iterrows()
        ],
        "new_high_count": len(new_high),
        "new_low_count": len(new_low),
        "new_high_stocks": new_high[:20],
        "new_low_stocks": new_low[:20],
        "data_state": "available",
    }


def persist_leaders(conn, result: dict[str, Any]) -> None:
    from tradingagents.astock.review.schema import ensure_review_tables
    ensure_review_tables(conn)
    td = result["trade_date"]
    conn.execute("DELETE FROM limit_up_daily WHERE trade_date = ?", [td])
    conn.execute("DELETE FROM limit_down_daily WHERE trade_date = ?", [td])
    conn.execute("DELETE FROM limit_up_ladders WHERE trade_date = ?", [td])
    conn.execute("DELETE FROM market_leaders_daily WHERE trade_date = ?", [td])

    for s in result.get("limit_up_stocks", []):
        conn.execute("INSERT INTO limit_up_daily(trade_date,symbol,gap_up_pct,data_state) VALUES (?,?,?,?)",
                     [td, s["symbol"], s["change_pct"], "available"])
    for s in result.get("limit_down_stocks", []):
        conn.execute("INSERT INTO limit_down_daily(trade_date,symbol,consecutive_days,data_state) VALUES (?,?,1,?)",
                     [td, s["symbol"], "available"])
    for ladder in result.get("limit_up_ladders", []):
        conn.execute("INSERT INTO limit_up_ladders(trade_date,symbol,ladder_height,data_state) VALUES (?,?,?,?)",
                     [td, ladder["symbol"], ladder["ladder_height"], "available"])
    for rank, leader in enumerate(result.get("volume_leaders", [])):
        conn.execute("INSERT INTO market_leaders_daily(trade_date,symbol,leader_type,rank,change_pct,amount,data_state) VALUES (?,?,?,?,?,?,?)",
                     [td, leader["symbol"], "volume", rank + 1, leader["change_pct"], leader["amount"], "available"])
    conn.commit()
