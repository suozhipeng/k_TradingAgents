"""Market, research, backtest, paper-trade, indicator, and reference-data APIs."""

from __future__ import annotations

from .pg_common import *


class PGMarketDataMixin:
    """Market, research, backtest, paper-trade, indicator, and reference-data APIs."""

    async def insert_kline(
        self, symbol: str, df: pd.DataFrame, interval: str = "1d", source: str = ""
    ) -> int:
        """Batch insert/replace kline bars for *symbol*."""
        if df.empty:
            return 0
        df = df.copy()
        interval = self._normalise_interval(interval)
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "interval" not in df.columns:
            df["interval"] = interval
        else:
            df["interval"] = df["interval"].fillna(interval).apply(self._normalise_interval)
        if "adjust" not in df.columns:
            df["adjust"] = "none"
        if "quality" not in df.columns:
            df["quality"] = "normal"
        if "source" not in df.columns:
            df["source"] = source
        df = self._normalise_kline_times(df)
        # Normalise first to get actual available columns
        normalised = self._df_from_rows(df, KLINE_COLUMN_MAP)
        if normalised.empty:
            return 0
        columns = list(normalised.columns)
        pk_cols = ["symbol", "bar_time", "interval", "adjust"]
        sql = self._build_upsert_sql("kline_bars", columns, pk_cols)
        records = normalised.to_dict(orient="records")
        cleaned = []
        for rec in records:
            clean = {}
            for k, v in rec.items():
                if isinstance(v, pd.Timestamp):
                    v = v.to_pydatetime()
                elif pd.isna(v):
                    v = None
                clean[k] = v
            cleaned.append(clean)

        if self._sync:
            with self._sync_engine.connect() as conn:
                total = 0
                for record in cleaned:
                    result = conn.execute(text(sql), record)
                    total += result.rowcount
                conn.commit()
            return total
        else:
            async with self._async_session_factory() as session:
                total = 0
                for record in cleaned:
                    result = await session.execute(text(sql), record)
                    total += result.rowcount
                await session.commit()
            return total

    async def query_kline(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
        limit: int | None = None,
        include_cold: bool = False,
    ) -> pd.DataFrame:
        """Return kline bars as a DataFrame, sorted by bar_time (ascending).

        When *limit* is set, the SQL-level query uses a **descending** subquery
        with ``LIMIT N``, then re-wraps in an outer ``ORDER BY bar_time ASC`` so
        that the caller always receives chronologically ordered data regardless
        of whether a pushdown limit was applied.
        """
        # PostgreSQL keeps its K-line table online; cold Parquet archives are
        # a DuckDB-only feature.  Accept the flag for API parity rather than
        # failing an otherwise valid query during a backend switch.
        interval = self._normalise_interval(interval)
        inner = 'SELECT * FROM kline_bars WHERE symbol = :symbol AND "interval" = :interval'
        params: dict[str, Any] = {"symbol": symbol, "interval": interval}
        if start:
            inner += " AND bar_time >= :start"
            params["start"] = start
        if end:
            inner += " AND bar_time <= :end"
            params["end"] = end

        if limit is not None and limit > 0:
            inner += " ORDER BY bar_time DESC LIMIT :limit"
            params["limit"] = limit
            sql = f"SELECT * FROM ({inner}) sub ORDER BY bar_time ASC"
        else:
            sql = inner + " ORDER BY bar_time"

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                if not rows:
                    return pd.DataFrame()
                df = pd.DataFrame(rows, columns=result.keys())
            return df
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                if not rows:
                    return pd.DataFrame()
                df = pd.DataFrame(rows, columns=result.keys())
            return df

    # ---- valuations ---------------------------------------------------------

    async def insert_valuations(
        self, symbol: str, df: pd.DataFrame, source: str = ""
    ) -> int:
        """Batch insert/replace valuation data for *symbol*."""
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        df = self._canonicalise_dates(df, ["trade_date", "date"])
        normalised = self._df_from_rows(df, VALUATION_COLUMN_MAP)
        if normalised.empty:
            return 0
        columns = list(normalised.columns)
        pk_cols = ["symbol", "trade_date"]
        sql = self._build_upsert_sql("valuations", columns, pk_cols)
        records = normalised.to_dict(orient="records")
        cleaned = []
        for rec in records:
            clean = {}
            for k, v in rec.items():
                if isinstance(v, pd.Timestamp):
                    v = v.to_pydatetime()
                elif pd.isna(v):
                    v = None
                clean[k] = v
            cleaned.append(clean)

        if self._sync:
            with self._sync_engine.connect() as conn:
                total = 0
                for record in cleaned:
                    result = conn.execute(text(sql), record)
                    total += result.rowcount
                conn.commit()
            return total
        else:
            async with self._async_session_factory() as session:
                total = 0
                for record in cleaned:
                    result = await session.execute(text(sql), record)
                    total += result.rowcount
                await session.commit()
            return total

    async def query_valuations(
        self, symbol: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        """Return valuations as a DataFrame, sorted by trade_date."""
        sql = "SELECT * FROM valuations WHERE symbol = :symbol"
        params: dict[str, Any] = {"symbol": symbol}
        if start:
            sql += " AND trade_date >= :start"
            params["start"] = start
        if end:
            sql += " AND trade_date <= :end"
            params["end"] = end
        sql += " ORDER BY trade_date"

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- order book snapshots -----------------------------------------------

    async def insert_order_book_snapshot(
        self, symbol: str, df: pd.DataFrame, source: str = ""
    ) -> int:
        """Batch insert/replace order book snapshots for *symbol*."""
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        return await self.insert_table_rows(
            "order_book_snapshots",
            self._df_from_rows(
                df,
                {
                    "symbol": "symbol",
                    "timestamp": "timestamp",
                    "bid_price": "bid_price",
                    "bid_volume": "bid_volume",
                    "ask_price": "ask_price",
                    "ask_volume": "ask_volume",
                    "source": "source",
                },
            ),
        )

    async def query_order_book(
        self, symbol: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        """Return order book snapshots as a DataFrame."""
        sql = "SELECT * FROM order_book_snapshots WHERE symbol = :symbol"
        params: dict[str, Any] = {"symbol": symbol}
        if start:
            sql += " AND timestamp >= :start"
            params["start"] = start
        if end:
            sql += " AND timestamp <= :end"
            params["end"] = end
        sql += " ORDER BY timestamp"

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- trade tape ---------------------------------------------------------

    async def insert_trade_tape(
        self, symbol: str, df: pd.DataFrame, source: str = ""
    ) -> int:
        """Batch insert/replace trade tape entries for *symbol*."""
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        return await self.insert_table_rows(
            "trade_tape",
            self._df_from_rows(
                df,
                {
                    "symbol": "symbol",
                    "timestamp": "timestamp",
                    "price": "price",
                    "volume": "volume",
                    "direction": "direction",
                    "source": "source",
                },
            ),
        )

    async def query_trade_tape(
        self, symbol: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        """Return trade tape entries as a DataFrame."""
        sql = "SELECT * FROM trade_tape WHERE symbol = :symbol"
        params: dict[str, Any] = {"symbol": symbol}
        if start:
            sql += " AND timestamp >= :start"
            params["start"] = start
        if end:
            sql += " AND timestamp <= :end"
            params["end"] = end
        sql += " ORDER BY timestamp"

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- research reports ---------------------------------------------------

    async def insert_research_reports(
        self, symbol: str, df: pd.DataFrame, source: str = ""
    ) -> int:
        """Batch insert/replace research reports for *symbol*."""
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        df = self._canonicalise_dates(df, ["report_date", "date"])
        return await self.insert_table_rows(
            "research_reports",
            self._df_from_rows(
                df,
                {
                    "symbol": "symbol",
                    "report_date": "report_date",
                    "title": "title",
                    "institution": "institution",
                    "analyst": "analyst",
                    "rating": "rating",
                    "pdf_url": "pdf_url",
                    "source": "source",
                },
            ),
        )

    async def query_research_reports(self, symbol: str) -> pd.DataFrame:
        sql = "SELECT * FROM research_reports WHERE symbol = :symbol ORDER BY report_date"
        params = {"symbol": symbol}
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- news items ---------------------------------------------------------

    async def insert_news_items(
        self, symbol: str, df: pd.DataFrame, source: str = ""
    ) -> int:
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "source" not in df.columns:
            df["source"] = source
        df = self._canonicalise_dates(df, ["publish_date", "date"])
        return await self.insert_table_rows(
            "news_items",
            self._df_from_rows(
                df,
                {
                    "symbol": "symbol",
                    "publish_date": "publish_date",
                    "title": "title",
                    "summary": "summary",
                    "url": "url",
                    "source": "source",
                },
            ),
        )

    async def query_news_items(self, symbol: str) -> pd.DataFrame:
        sql = "SELECT * FROM news_items WHERE symbol = :symbol ORDER BY publish_date"
        params = {"symbol": symbol}
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- announcements ------------------------------------------------------

    async def insert_announcements(self, symbol: str, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        df = self._canonicalise_dates(df, ["publish_date", "date"])
        return await self.insert_table_rows(
            "announcements",
            self._df_from_rows(
                df,
                {
                    "symbol": "symbol",
                    "publish_date": "publish_date",
                    "title": "title",
                    "summary": "summary",
                    "url": "url",
                },
            ),
        )

    async def query_announcements(self, symbol: str) -> pd.DataFrame:
        sql = "SELECT * FROM announcements WHERE symbol = :symbol ORDER BY publish_date DESC"
        params = {"symbol": symbol}
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- backtest results ---------------------------------------------------

    async def store_backtest_result(self, result: Any) -> int:
        """Store a backtest result (dict or BacktestResult-like object)."""
        if hasattr(result, "model_dump"):
            data = result.model_dump()
        elif isinstance(result, dict):
            data = dict(result)
        else:
            data = {}
        run_id = data.get("run_id", str(hash(str(data))))
        df = pd.DataFrame(
            [
                {
                    "run_id": run_id,
                    "symbol": str(data.get("symbol", "")),
                    "strategy_name": str(data.get("strategy_name", "unknown")),
                    "start_date": str(data.get("start_date", "")),
                    "end_date": str(data.get("end_date", "")),
                    "total_return": float(data.get("total_return", 0.0)),
                    "annualized_return": float(data.get("annualized_return", 0.0)),
                    "sharpe_ratio": float(data.get("sharpe_ratio", 0.0)),
                    "max_drawdown": float(data.get("max_drawdown", 0.0)),
                    "win_rate": float(data.get("win_rate", 0.0)),
                    "total_trades": int(data.get("total_trades", 0)),
                    "params_json": json.dumps(
                        {
                            k: v
                            for k, v in data.items()
                            if k
                            not in (
                                "run_id",
                                "symbol",
                                "strategy_name",
                                "start_date",
                                "end_date",
                                "total_return",
                                "annualized_return",
                                "sharpe_ratio",
                                "max_drawdown",
                                "win_rate",
                                "total_trades",
                            )
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        )
        return await self.insert_table_rows("backtest_results", df)

    async def get_backtest_results(
        self, strategy_name: str | None = None
    ) -> pd.DataFrame:
        if strategy_name:
            sql = "SELECT * FROM backtest_results WHERE strategy_name = :name ORDER BY created_at DESC"
            params = {"name": strategy_name}
        else:
            sql = "SELECT * FROM backtest_results ORDER BY created_at DESC"
            params = {}
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    async def clear_backtest_results(self) -> int:
        """Delete all stored backtest results. Returns number of rows deleted."""
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text("DELETE FROM backtest_results"))
                conn.commit()
                return result.rowcount
        else:
            async with self._async_session_factory() as session:
                result = await session.execute(text("DELETE FROM backtest_results"))
                await session.commit()
                return result.rowcount

    async def delete_backtest_result(self, run_id: str) -> int:
        """Delete a single backtest result by run_id. Returns 1 if deleted."""
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text("DELETE FROM backtest_results WHERE run_id = :rid"), {"rid": run_id})
                conn.commit()
                return result.rowcount
        else:
            async with self._async_session_factory() as session:
                result = await session.execute(
                    text("DELETE FROM backtest_results WHERE run_id = :rid"), {"rid": run_id}
                )
                await session.commit()
                return result.rowcount

    # ---- paper trades -------------------------------------------------------

    async def store_paper_trade(self, trade: dict[str, Any]) -> int:
        """Store a single paper trade record."""
        df = pd.DataFrame([trade])
        if "trade_id" not in df.columns:
            df["trade_id"] = str(hash(str(trade)))
        if "actionable" not in df.columns:
            df["actionable"] = False
        if "decision_scope" not in df.columns:
            df["decision_scope"] = "paper_trading_only"
        df = self._canonicalise_dates(df, ["trade_date", "date"])
        return await self.insert_table_rows("paper_trades", df)

    async def get_paper_trades(self, symbol: str | None = None) -> pd.DataFrame:
        if symbol:
            sql = "SELECT * FROM paper_trades WHERE symbol = :symbol ORDER BY trade_date"
            params = {"symbol": symbol}
        else:
            sql = "SELECT * FROM paper_trades ORDER BY trade_date"
            params = {}
        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- market indicators --------------------------------------------------

    async def insert_market_indicators(self, symbol: str, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        df = df.copy()
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        df = self._canonicalise_dates(df, ["trade_date", "date"])
        return await self.insert_table_rows(
            "market_indicators",
            self._df_from_rows(
                df,
                {
                    "symbol": "symbol",
                    "trade_date": "trade_date",
                    "ma_5": "ma_5",
                    "ma_20": "ma_20",
                    "ma_60": "ma_60",
                    "rsi_14": "rsi_14",
                    "atr_14": "atr_14",
                    "volume_ma_5": "volume_ma_5",
                },
            ),
        )

    async def query_market_indicators(
        self, symbol: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        sql = "SELECT * FROM market_indicators WHERE symbol = :symbol"
        params: dict[str, Any] = {"symbol": symbol}
        if start:
            sql += " AND trade_date >= :start"
            params["start"] = start
        if end:
            sql += " AND trade_date <= :end"
            params["end"] = end
        sql += " ORDER BY trade_date"

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- trading calendar ---------------------------------------------------

    async def insert_trading_calendar(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("trading_calendar", rows)

    # ---- security status history --------------------------------------------

    async def insert_security_status_history(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("security_status_history", rows)

    # ---- adjust factors -----------------------------------------------------

    async def insert_adjust_factors(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("adjust_factors", rows)

    async def query_adjust_factors(
        self,
        symbol: str,
        adjust: str = "qfq",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        sql = "SELECT * FROM adjust_factors WHERE symbol = :symbol AND adjust = :adjust"
        params: dict[str, Any] = {"symbol": symbol, "adjust": adjust}
        if start:
            sql += " AND trade_date >= :start"
            params["start"] = start
        if end:
            sql += " AND trade_date <= :end"
            params["end"] = end
        sql += " ORDER BY trade_date"

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- technical indicators -----------------------------------------------

    async def insert_technical_indicators(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        if isinstance(rows, pd.DataFrame):
            df = rows.copy()
        else:
            df = pd.DataFrame(rows)
        if df.empty:
            return 0
        df = self._normalise_kline_times(df)
        if "interval" in df.columns:
            df["interval"] = df["interval"].fillna("1d").apply(self._normalise_interval)
        return await self.insert_table_rows("technical_indicators", df)

    async def query_technical_indicators(
        self,
        symbol: str,
        indicator: str,
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        interval = self._normalise_interval(interval)
        sql = (
            "SELECT * FROM technical_indicators "
            "WHERE symbol = :symbol AND indicator = :indicator AND interval = :interval"
        )
        params: dict[str, Any] = {"symbol": symbol, "indicator": indicator, "interval": interval}
        if start:
            sql += " AND bar_time >= :start"
            params["start"] = start
        if end:
            sql += " AND bar_time <= :end"
            params["end"] = end
        sql += " ORDER BY bar_time"

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- data quality / snapshots / partitions / ingestion ------------------
    async def insert_industry_classification(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("industry_classification_history", rows)

    async def insert_suspension_events(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("suspension_events", rows)

    async def insert_price_limit_rules(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("price_limit_rules", rows)

    async def insert_corporate_actions(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("corporate_actions", rows)

    async def insert_security_master(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("security_master", rows)

    async def insert_data_sources(
        self, rows: pd.DataFrame | list[dict[str, Any]]
    ) -> int:
        return await self.insert_table_rows("data_sources", rows)


# ---------------------------------------------------------------------------
# Convenience factory
