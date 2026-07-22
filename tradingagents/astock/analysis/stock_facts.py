"""Deterministic stock-analysis facts with lineage and risk signals."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

import pandas as pd


class StockFactsEngine:
    """Compute technical, valuation, and risk facts from canonical rows only."""

    source_table = "kline_bars"

    def __init__(self, store: Any | None = None) -> None:
        self.store = store

    @staticmethod
    def _normalise(frame: pd.DataFrame) -> pd.DataFrame:
        required = {"symbol", "trade_date", "close"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"missing stock analysis columns: {sorted(missing)}")
        df = frame.copy()
        df["symbol"] = df["symbol"].astype(str).str.strip()
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["symbol", "trade_date", "close"])
        df = df[df["close"] > 0].sort_values("trade_date")
        if "volume" not in df.columns:
            df["volume"] = 0.0
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
        return df

    @staticmethod
    def _fact(run_id: str, metric: str, value: Any, as_of: date) -> dict[str, Any]:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        digest = hashlib.sha256(f"{run_id}:{metric}:{raw}".encode()).hexdigest()[:16]
        return {
            "fact_id": f"stock_fact_{digest}",
            "metric": metric,
            "value": value,
            "as_of": as_of.isoformat(),
            "source_table": StockFactsEngine.source_table,
        }

    def compute(self, frame: pd.DataFrame, symbol: str | None = None, as_of: str | date | None = None) -> dict[str, Any]:
        df = self._normalise(frame)
        if symbol:
            df = df[df["symbol"] == symbol]
        if df.empty:
            raise ValueError("stock analysis requires canonical rows")
        symbol = str(df["symbol"].iloc[0])
        cutoff = pd.Timestamp(as_of).date() if as_of else max(df["trade_date"])
        df = df[df["trade_date"] <= cutoff].copy()
        if df.empty:
            raise ValueError("no canonical rows at requested cutoff")
        close = df["close"]
        latest = float(close.iloc[-1])
        ma5 = float(close.tail(5).mean())
        ma20 = float(close.tail(20).mean())
        returns = close.pct_change().dropna()
        momentum = round(float((latest / float(close.iloc[0])) - 1), 8) if len(close) > 1 else 0.0
        volatility = round(float(returns.std()) if len(returns) > 1 else 0.0, 8)
        volume_latest = float(df["volume"].iloc[-1])
        volume_avg = float(df["volume"].tail(20).mean())
        volume_ratio = round(volume_latest / volume_avg, 8) if volume_avg > 0 else 0.0

        facts: list[dict[str, Any]] = []
        for metric, value in (
            ("latest_close", round(latest, 8)),
            ("ma5", round(ma5, 8)),
            ("ma20", round(ma20, 8)),
            ("momentum", momentum),
            ("volatility", volatility),
            ("volume_ratio", volume_ratio),
        ):
            facts.append(self._fact("pending", metric, value, cutoff))

        risk_signals: list[dict[str, Any]] = []
        if volatility >= 0.05:
            risk_signals.append({"code": "high_volatility", "severity": "warning", "fact_metric": "volatility"})
        if volume_ratio >= 5:
            risk_signals.append({"code": "abnormal_volume", "severity": "warning", "fact_metric": "volume_ratio"})
        if latest < ma20:
            risk_signals.append({"code": "below_ma20", "severity": "info", "fact_metric": "ma20"})

        seed = f"{symbol}:{cutoff.isoformat()}:{latest}:{ma5}:{ma20}:{momentum}:{volatility}:{volume_ratio}"
        run_id = "stock_analysis_" + hashlib.sha256(seed.encode()).hexdigest()[:20]
        for fact in facts:
            fact["run_id"] = run_id
            fact["fact_id"] = self._fact(run_id, fact["metric"], fact["value"], cutoff)["fact_id"]
        return {
            "run_id": run_id,
            "symbol": symbol,
            "as_of": cutoff.isoformat(),
            "facts": facts,
            "risk_signals": risk_signals,
            "llm_used": False,
            "source_table": self.source_table,
        }

    def persist(self, report: dict[str, Any]) -> str:
        if self.store is None:
            raise ValueError("store is required for persistence")
        conn = self.store.conn
        conn.execute("""CREATE TABLE IF NOT EXISTS stock_analysis_runs (
            run_id VARCHAR PRIMARY KEY, symbol VARCHAR, as_of DATE,
            report_json VARCHAR, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS stock_analysis_facts (
            fact_id VARCHAR PRIMARY KEY, run_id VARCHAR, symbol VARCHAR,
            metric VARCHAR, value_json VARCHAR, as_of DATE, source_table VARCHAR
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS stock_risk_signals (
            run_id VARCHAR, symbol VARCHAR, code VARCHAR, severity VARCHAR,
            fact_metric VARCHAR, as_of DATE
        )""")
        run_id = report["run_id"]
        conn.execute("DELETE FROM stock_analysis_facts WHERE run_id = ?", [run_id])
        conn.execute("DELETE FROM stock_risk_signals WHERE run_id = ?", [run_id])
        conn.execute("DELETE FROM stock_analysis_runs WHERE run_id = ?", [run_id])
        conn.execute("INSERT INTO stock_analysis_runs(run_id,symbol,as_of,report_json) VALUES (?,?,?,?)", [run_id, report["symbol"], report["as_of"], json.dumps(report, ensure_ascii=False, sort_keys=True)])
        for fact in report["facts"]:
            conn.execute("INSERT INTO stock_analysis_facts(fact_id,run_id,symbol,metric,value_json,as_of,source_table) VALUES (?,?,?,?,?,?,?)", [fact["fact_id"], run_id, report["symbol"], fact["metric"], json.dumps(fact["value"], ensure_ascii=False), fact["as_of"], fact["source_table"]])
        for signal in report["risk_signals"]:
            conn.execute("INSERT INTO stock_risk_signals(run_id,symbol,code,severity,fact_metric,as_of) VALUES (?,?,?,?,?,?)", [run_id, report["symbol"], signal["code"], signal["severity"], signal["fact_metric"], report["as_of"]])
        conn.commit()
        return run_id

    def run(self, frame: pd.DataFrame, symbol: str | None = None, as_of: str | date | None = None) -> dict[str, Any]:
        report = self.compute(frame, symbol=symbol, as_of=as_of)
        if self.store is not None:
            self.persist(report)
        return report
