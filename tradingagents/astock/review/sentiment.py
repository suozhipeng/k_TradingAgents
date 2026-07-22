"""Sentiment state machine — limit-up/down, ladder, gap-up, cycle phase."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd


SENTIMENT_VERSION = "v1.0"


def _determine_cycle_phase(limit_up: int, limit_down: int, advance_ratio: float,
                            profit_score: float) -> str:
    """Pure deterministic state machine — ordered from most bearish to most bullish.

    States: ice (freeze) → ebb → divergence → repair → start → ferment → climax
    """
    net = limit_up - limit_down
    # Extremely bearish
    if limit_down >= 20 or advance_ratio < 0.2:
        return "ice"
    # Bearish
    if limit_down >= 10 or net < -10:
        return "ebb"
    # Declining momentum
    if profit_score < -15:
        return "divergence"
    # Recovering — moderate, not yet trending up
    if advance_ratio > 0.35 and limit_up < 15 and limit_down < 10:
        return "repair"
    # Overheating (check before other uptrend states)
    if limit_up >= 30 and net > 10 and advance_ratio > 0.5:
        return "climax"
    # Uptrend developing
    if limit_up >= 22 and net > 5 and advance_ratio > 0.4:
        return "ferment"
    # Uptrend starting
    if limit_up >= 15 and net > 3:
        return "start"
    return "repair"


def compute_sentiment(breadth_result: dict[str, Any],
                      limit_up_count: int = 0, limit_down_count: int = 0,
                      first_board: int = 0, second_board: int = 0,
                      third_plus_board: int = 0,
                      gap_up_count: int = 0, gap_up_rate: float = 0.0,
                      yesterday_limit_up_avg: float = 0.0,
                      yesterday_ladder_avg: float = 0.0) -> dict[str, Any]:
    """Compute sentiment metrics and cycle phase.

    Parameters
    ----------
    breadth_result : dict
        Output from ``compute_breadth()``.  Must contain ``advance_ratio``.
    limit_up_count, limit_down_count, ... : various
        Market data.  Pass 0 when unavailable — the engine marks partial state.

    Returns
    -------
    dict with data_state, cycle_phase, and all sentiment metrics.
    """
    # If provider/source data is entirely missing
    if breadth_result.get("data_state") != "available":
        return {
            "data_state": "unavailable",
            "reason": "breadth unavailable",
            "cycle_phase": None,
            "cycle_version": SENTIMENT_VERSION,
        }

    trade_date = breadth_result.get("trade_date", "unknown")
    advance_ratio = breadth_result.get("advance_ratio", 0.0)

    # Profit / loss scores
    profit_score = round(advance_ratio * 100 - 50, 2)
    loss_score = round(-profit_score, 2)

    phase = _determine_cycle_phase(limit_up_count, limit_down_count, advance_ratio, profit_score)

    seed = json.dumps({"date": trade_date, "phase": phase, "profit_score": profit_score}, sort_keys=True)
    run_id = "sentiment_" + hashlib.sha256(seed.encode()).hexdigest()[:12]

    return {
        "run_id": run_id,
        "trade_date": trade_date,
        "limit_up": limit_up_count,
        "limit_down": limit_down_count,
        "first_board": first_board,
        "second_board": second_board,
        "third_plus_board": third_plus_board,
        "max_ladder_height": third_plus_board,  # simplified; real data would scan ladders
        "gap_up_count": gap_up_count,
        "gap_up_rate": round(gap_up_rate, 4),
        "yesterday_limit_up_avg_pct": round(yesterday_limit_up_avg, 4),
        "yesterday_ladder_avg_pct": round(yesterday_ladder_avg, 4),
        "profit_score": profit_score,
        "loss_score": loss_score,
        "cycle_phase": phase,
        "cycle_version": SENTIMENT_VERSION,
        "data_state": "available",
    }


def persist_sentiment(conn, result: dict[str, Any]) -> None:
    from tradingagents.astock.review.schema import ensure_review_tables
    ensure_review_tables(conn)
    td = result["trade_date"]
    conn.execute("""DELETE FROM market_sentiment_daily WHERE trade_date = ?""", [td])
    conn.execute("""INSERT INTO market_sentiment_daily VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [
        td,
        result["limit_up"], result["limit_down"],
        result["first_board"], result["second_board"], result["third_plus_board"],
        result["max_ladder_height"],
        result["gap_up_count"], result["gap_up_rate"],
        result["yesterday_limit_up_avg_pct"],
        result["yesterday_ladder_avg_pct"],
        result["profit_score"], result["loss_score"],
        result["cycle_phase"],
        result["cycle_version"],
        result["data_state"],
    ])
    conn.commit()
