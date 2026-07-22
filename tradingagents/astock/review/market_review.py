"""Deterministic market review engine.

The engine consumes already-normalized Canonical DuckDB rows. It never calls a
Provider and never requires an LLM. Every derived metric has a stable fact ID,
data cutoff, and source table so a later natural-language layer can cite it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

import pandas as pd


_RUN_DDL = """
CREATE TABLE IF NOT EXISTS market_review_runs (
    run_id VARCHAR PRIMARY KEY,
    as_of DATE NOT NULL,
    status VARCHAR NOT NULL,
    sentiment_state VARCHAR NOT NULL,
    report_json VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

_FACT_DDL = """
CREATE TABLE IF NOT EXISTS market_review_facts (
    fact_id VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    metric VARCHAR NOT NULL,
    value_json VARCHAR NOT NULL,
    as_of DATE NOT NULL,
    source_table VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


class MarketReviewEngine:
    """Compute and persist a reproducible market review from canonical rows."""

    source_table = "kline_bars"

    def __init__(self, store: Any | None = None) -> None:
        self.store = store

    @staticmethod
    def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
        required = {"symbol", "trade_date", "close"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"missing market review columns: {sorted(missing)}")
        df = frame.copy()
        df["symbol"] = df["symbol"].astype(str).str.strip()
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["symbol", "trade_date", "close"])
        df = df[df["close"] > 0].sort_values(["symbol", "trade_date"])
        if "sector" not in df.columns:
            df["sector"] = "未分类"
        df["sector"] = df["sector"].fillna("未分类").astype(str)
        df["return_1d"] = df.groupby("symbol")["close"].pct_change()
        return df

    @staticmethod
    def _fact(run_id: str, metric: str, value: Any, as_of: date) -> dict[str, Any]:
        digest = hashlib.sha256(
            f"{run_id}:{metric}:{json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)}".encode()
        ).hexdigest()[:16]
        return {
            "fact_id": f"fact_{digest}",
            "run_id": run_id,
            "metric": metric,
            "value": value,
            "as_of": as_of.isoformat(),
            "source_table": MarketReviewEngine.source_table,
        }

    def compute(self, frame: pd.DataFrame, as_of: str | date | None = None) -> dict[str, Any]:
        """Return deterministic facts and report without writing anything."""
        df = self._normalize(frame)
        if df.empty:
            raise ValueError("market review requires at least one valid canonical row")

        cutoff = pd.Timestamp(as_of).date() if as_of else max(df["trade_date"])
        latest = df[df["trade_date"] <= cutoff]
        latest = latest.sort_values(["symbol", "trade_date"]).groupby("symbol", as_index=False).tail(1)
        changes = latest["return_1d"].dropna()
        advancing = int((changes > 0).sum())
        declining = int((changes < 0).sum())
        unchanged = int((changes == 0).sum())
        total = advancing + declining + unchanged
        breadth = round((advancing - declining) / total, 6) if total else 0.0
        avg_return = round(float(changes.mean()), 8) if not changes.empty else 0.0

        if breadth >= 0.25 and avg_return >= 0:
            sentiment = "强势"
        elif breadth <= -0.25 and avg_return <= 0:
            sentiment = "弱势"
        else:
            sentiment = "震荡"

        sector_rows = []
        for sector, group in latest.groupby("sector", dropna=False):
            values = group["return_1d"].dropna()
            sector_rows.append({
                "sector": str(sector),
                "stock_count": int(len(group)),
                "average_return": round(float(values.mean()), 8) if not values.empty else 0.0,
            })
        sector_rows.sort(key=lambda item: item["average_return"], reverse=True)

        run_seed = f"{cutoff.isoformat()}:{len(latest)}:{breadth}:{avg_return}"
        run_id = "review_" + hashlib.sha256(run_seed.encode()).hexdigest()[:20]
        facts = [
            self._fact(run_id, "advancing", advancing, cutoff),
            self._fact(run_id, "declining", declining, cutoff),
            self._fact(run_id, "unchanged", unchanged, cutoff),
            self._fact(run_id, "breadth", breadth, cutoff),
            self._fact(run_id, "average_return", avg_return, cutoff),
            self._fact(run_id, "sector_strength", sector_rows, cutoff),
        ]
        report = {
            "run_id": run_id,
            "as_of": cutoff.isoformat(),
            "status": "ok",
            "sentiment_state": sentiment,
            "market_breadth": {
                "advancing": advancing,
                "declining": declining,
                "unchanged": unchanged,
                "breadth": breadth,
            },
            "average_return": avg_return,
            "sector_strength": sector_rows,
            "facts": facts,
            "llm_used": False,
        }
        return report

    def persist(self, report: dict[str, Any]) -> str:
        """Persist one report atomically and idempotently in Canonical DuckDB."""
        if self.store is None:
            raise ValueError("store is required for persistence")
        conn = self.store.conn
        conn.execute(_RUN_DDL)
        conn.execute(_FACT_DDL)
        run_id = str(report["run_id"])
        conn.execute("DELETE FROM market_review_facts WHERE run_id = ?", [run_id])
        conn.execute("DELETE FROM market_review_runs WHERE run_id = ?", [run_id])
        conn.execute(
            "INSERT INTO market_review_runs "
            "(run_id, as_of, status, sentiment_state, report_json) VALUES (?, ?, ?, ?, ?)",
            [run_id, report["as_of"], report["status"], report["sentiment_state"], json.dumps(report, ensure_ascii=False, sort_keys=True)],
        )
        for fact in report["facts"]:
            conn.execute(
                "INSERT INTO market_review_facts "
                "(fact_id, run_id, metric, value_json, as_of, source_table) VALUES (?, ?, ?, ?, ?, ?)",
                [fact["fact_id"], run_id, fact["metric"], json.dumps(fact["value"], ensure_ascii=False, sort_keys=True), fact["as_of"], fact["source_table"]],
            )
        conn.commit()
        return run_id

    def run(self, frame: pd.DataFrame, as_of: str | date | None = None) -> dict[str, Any]:
        report = self.compute(frame, as_of=as_of)
        if self.store is not None:
            self.persist(report)
        return report
