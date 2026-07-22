"""Canonical DuckDB-only A-share backtest engine."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 100_000.0
    lot_size: int = 100
    commission_rate: float = 0.0003
    stamp_tax_rate: float = 0.001
    slippage_rate: float = 0.0005
    strategy_version: str = "ma5_ma20_v1"


class CanonicalBacktest:
    """Run a reproducible MA5/MA20 backtest over Canonical DuckDB rows."""

    source_table = "kline_bars"

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()

    @staticmethod
    def _normalise(frame: pd.DataFrame) -> pd.DataFrame:
        required = {"trade_date", "close"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"missing backtest columns: {sorted(missing)}")
        df = frame.copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        if "open" not in df.columns:
            df["open"] = df["close"]
        df["open"] = pd.to_numeric(df["open"], errors="coerce")
        df = df.dropna(subset=["trade_date", "open", "close"])
        df = df[(df["open"] > 0) & (df["close"] > 0)].sort_values("trade_date").reset_index(drop=True)
        if df.empty:
            raise ValueError("backtest requires valid canonical bars")
        return df

    def run_frame(self, frame: pd.DataFrame, symbol: str = "") -> dict[str, Any]:
        df = self._normalise(frame)
        if len(df) < 22:
            raise ValueError("backtest requires at least 22 canonical daily bars")
        cfg = self.config
        df["ma5"] = df["close"].rolling(5).mean()
        df["ma20"] = df["close"].rolling(20).mean()
        df["cross_up"] = (df["ma5"] > df["ma20"]) & (df["ma5"].shift(1) <= df["ma20"].shift(1))
        df["cross_down"] = (df["ma5"] < df["ma20"]) & (df["ma5"].shift(1) >= df["ma20"].shift(1))

        cash = cfg.initial_cash
        shares = 0
        entry_date = None
        trades: list[dict[str, Any]] = []
        equity_curve: list[dict[str, Any]] = []

        for index, row in df.iterrows():
            # Signal at today's close executes at the next trading day's open.
            if index + 1 < len(df):
                next_row = df.iloc[index + 1]
                execution_date = next_row["trade_date"].date().isoformat()
                execution_price = float(next_row["open"])
                if shares == 0 and bool(row["cross_up"]):
                    price = execution_price * (1 + cfg.slippage_rate)
                    quantity = int(cash // (price * cfg.lot_size)) * cfg.lot_size
                    if quantity > 0:
                        gross = price * quantity
                        fee = gross * cfg.commission_rate
                        cash -= gross + fee
                        shares = quantity
                        entry_date = execution_date
                        trades.append({"date": execution_date, "side": "buy", "price": price, "shares": quantity, "fee": fee})
                elif shares > 0 and bool(row["cross_down"]):
                    # T+1: entry_date must be strictly before execution_date.
                    if entry_date and execution_date > entry_date:
                        price = execution_price * (1 - cfg.slippage_rate)
                        gross = price * shares
                        fee = gross * (cfg.commission_rate + cfg.stamp_tax_rate)
                        cash += gross - fee
                        trades.append({"date": execution_date, "side": "sell", "price": price, "shares": shares, "fee": fee})
                        shares = 0
                        entry_date = None
            equity_curve.append({"date": row["trade_date"].date().isoformat(), "value": round(cash + shares * float(row["close"]), 8)})

        if shares:
            last = df.iloc[-1]
            price = float(last["close"]) * (1 - cfg.slippage_rate)
            gross = price * shares
            fee = gross * (cfg.commission_rate + cfg.stamp_tax_rate)
            cash += gross - fee
            trades.append({"date": last["trade_date"].date().isoformat(), "side": "sell", "price": price, "shares": shares, "fee": fee, "forced_exit": True})
            shares = 0

        final_value = round(cash, 8)
        run_seed = json.dumps({"symbol": symbol, "start": equity_curve[0]["date"], "end": equity_curve[-1]["date"], "config": cfg.__dict__}, sort_keys=True)
        run_id = "backtest_" + hashlib.sha256(run_seed.encode()).hexdigest()[:20]
        return {
            "run_id": run_id,
            "symbol": symbol,
            "strategy_version": cfg.strategy_version,
            "source_table": self.source_table,
            "data_start": equity_curve[0]["date"],
            "data_end": equity_curve[-1]["date"],
            "initial_cash": cfg.initial_cash,
            "final_value": final_value,
            "return_rate": round((final_value / cfg.initial_cash) - 1, 8),
            "trades": trades,
            "equity_curve": equity_curve,
            "no_lookahead": True,
            "a_share_rules": {"lot_size": cfg.lot_size, "t_plus_one": True, "fees": True, "slippage": True},
        }

    def run(self, store: Any, symbol: str, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        """Read bars from Canonical DuckDB only; Provider access is impossible here."""
        sql = 'SELECT * FROM "kline_bars" WHERE symbol = ?'
        params: list[str] = [symbol]
        if start:
            sql += " AND trade_date >= ?"
            params.append(start)
        if end:
            sql += " AND trade_date <= ?"
            params.append(end)
        sql += " ORDER BY trade_date"
        frame = store.conn.execute(sql, params).fetchdf()
        return self.run_frame(frame, symbol=symbol)

    def persist(self, store: Any, result: dict[str, Any]) -> str:
        conn = store.conn
        conn.execute("""CREATE TABLE IF NOT EXISTS backtest_runs (
            run_id VARCHAR PRIMARY KEY, symbol VARCHAR, strategy_version VARCHAR,
            source_table VARCHAR, data_start DATE, data_end DATE,
            initial_cash DOUBLE, final_value DOUBLE, return_rate DOUBLE,
            result_json VARCHAR, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS backtest_trades (
            run_id VARCHAR, trade_date DATE, side VARCHAR, price DOUBLE,
            shares INTEGER, fee DOUBLE, forced_exit BOOLEAN DEFAULT FALSE
        )""")
        run_id = result["run_id"]
        conn.execute("DELETE FROM backtest_trades WHERE run_id = ?", [run_id])
        conn.execute("DELETE FROM backtest_runs WHERE run_id = ?", [run_id])
        conn.execute("INSERT INTO backtest_runs VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)", [run_id, result["symbol"], result["strategy_version"], result["source_table"], result["data_start"], result["data_end"], result["initial_cash"], result["final_value"], result["return_rate"], json.dumps(result, ensure_ascii=False, sort_keys=True)])
        for trade in result["trades"]:
            conn.execute("INSERT INTO backtest_trades VALUES (?,?,?,?,?,?,?)", [run_id, trade["date"], trade["side"], trade["price"], trade["shares"], trade["fee"], trade.get("forced_exit", False)])
        conn.commit()
        return run_id
