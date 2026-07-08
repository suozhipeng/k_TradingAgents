"""Backtest engine for A-share strategies."""

from __future__ import annotations

import logging
from datetime import date as date_type

import numpy as np
import pandas as pd

from .models import BacktestDataAssumption, BacktestResult, AdjustmentMethod, CostModel, SettlementConstraint
from .mock_data import _mock_fallback
from ..backtest.fee_model import AStockFeeConfig, calculate_fees
from ..backtest.metrics import summarize_metrics
from ..strategy_base import StrategyBase

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Period-based backtest engine for A-share strategies.

    Parameters
    ----------
    fee_config : AStockFeeConfig or None
        Custom fee configuration.  Falls back to defaults.
    """

    def __init__(self, fee_config: AStockFeeConfig | None = None, use_mock_data: bool = False) -> None:
        self.fee_config = fee_config or AStockFeeConfig()
        self._facade: Any = None  # lazy import
        self._use_mock_data = use_mock_data

    def _fetch_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch OHLCV data, falling back to mock data if facade unavailable."""
        # use_mock_data=True -> skip real data, go straight to mock
        if self._use_mock_data:
            return _mock_fallback(symbol, start_date, end_date)

        # Try AStockDataFacade first (uses baostock as primary default)
        try:
            from tradingagents.astock.data_sources import AStockDataFacade

            if self._facade is None:
                self._facade = AStockDataFacade()
            response = self._facade.get_kline(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval="1d",
            )
            if response.status == "ok" and response.data and response.data.get("bars"):
                bars = response.data["bars"]
                df = pd.DataFrame(bars)
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date").sort_index()
                for col in ("open", "high", "low", "close", "volume"):
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                return df
        except Exception:
            logger.warning("Data load failed for %s, falling back to mock data", symbol)

        # Fallback to mock data
        return _mock_fallback(symbol, start_date, end_date)

    def _detect_bias(self, df: pd.DataFrame, start_date: str, end_date: str) -> dict[str, bool]:
        """Detect survivorship and look-ahead bias risks in the loaded data.

        Returns
        -------
        dict
            Keys ``survivorship_bias_risk`` and ``look_ahead_bias_risk``.
        """
        risks: dict[str, bool] = {
            "survivorship_bias_risk": False,
            "look_ahead_bias_risk": False,
        }
        if df.empty:
            return risks

        # Survivorship bias: bars don't cover the full requested range
        end_ts = pd.Timestamp(end_date)
        last_bar_date = df.index.max()
        if isinstance(last_bar_date, pd.Timestamp) and last_bar_date < end_ts:
            risks["survivorship_bias_risk"] = True

        # Look-ahead bias: if using akshare stock_zh_a_hist it returns
        # forward-adjusted prices (adjustment factors depend on future events).
        if not self._use_mock_data:
            risks["look_ahead_bias_risk"] = True

        return risks

    @staticmethod
    def _detect_st_delisted(df: pd.DataFrame, symbol: str, start_date: str, end_date: str) -> dict[str, bool]:
        """Detect if a stock is ST/*ST or delisted based on available data.

        Returns
        -------
        dict
            Keys ``st_stock`` and ``delisted``.
        """
        result: dict[str, bool] = {"st_stock": False, "delisted": False}
        if df.empty:
            return result

        # Delisted detection: data ends well before the requested end_date
        end_ts = pd.Timestamp(end_date)
        last_bar_date = df.index.max()
        if isinstance(last_bar_date, pd.Timestamp) and last_bar_date < end_ts:
            trading_days_missing = len(pd.bdate_range(last_bar_date, end_ts))
            if trading_days_missing > 60:
                result["delisted"] = True

        # ST detection: check symbol prefix patterns
        st_patterns = ("ST", "*ST", "SST", "S*ST")
        name = symbol.upper()
        if any(name.startswith(p) for p in st_patterns):
            result["st_stock"] = True

        return result

    @staticmethod
    def _is_at_price_limit(prev_close: float | None, curr_close: float, st_stock: bool = False) -> tuple[bool, str]:
        """Check if the price is at the daily price limit.

        For A-shares the default limit is ±10% from the previous close.
        ST/*ST stocks have a ±5% limit.

        Uses the **actual previous trading day's close** passed as parameter,
        not a period-internal iloc reference.

        Returns (is_limited, reason).
        """
        if prev_close is None or curr_close is None or prev_close <= 0:
            return False, ""
        change_pct = abs(curr_close - prev_close) / prev_close
        threshold = 0.0495 if st_stock else 0.0995  # exact A-share limits ±5% and ±10%
        if change_pct >= threshold:
            direction = "up" if curr_close >= prev_close else "down"
            prefix = "st_" if st_stock else ""
            return True, f"{prefix}price_limit_{direction}"
        return False, ""

    @staticmethod
    def _is_suspended(period_data: pd.DataFrame) -> tuple[bool, str]:
        """Check if the stock is suspended (no trading volume).

        Primary detection uses OHLCV data heuristics (volume == 0).
        Falls back to akshare/EastMoney suspension list when available.

        Returns (is_suspended, reason).
        """
        if period_data.empty:
            return False, ""
        daily_volume = float(period_data["volume"].iloc[-1])
        if daily_volume <= 0:
            return True, "suspended_no_volume"
        # Also check: if high==low==close (flat price) with zero volume
        high = float(period_data["high"].iloc[-1])
        low = float(period_data["low"].iloc[-1])
        close = float(period_data["close"].iloc[-1])
        if high == low == close and daily_volume == 0:
            return True, "suspended_flat_price"
        return False, ""

    def _check_external_suspension(self, symbol: str, trade_date: str) -> tuple[bool, str]:
        """Check suspension via external data sources (akshare / EastMoney).

        Uses the trade_date parameter for historical backtest support.

        Returns (is_suspended, reason).
        """
        if self._use_mock_data:
            return False, ""
        try:
            from tradingagents.astock.data_sources.suspension import is_suspended
            suspended, reason = is_suspended(symbol, source="akshare", date=trade_date)
            if suspended:
                if reason:
                    return True, f"suspended_external_{reason}"
                return True, "suspended_external"
        except Exception:
            logger.debug("External suspension check unavailable for %s", symbol)
        return False, ""

    def _check_external_price_limit(
        self, symbol: str, trade_date: str,
    ) -> tuple[bool, str]:
        """Check price limit via external data sources (akshare / EastMoney).

        Uses :func:`is_at_price_limit_external` which fetches real-time
        涨停/跌停 pools with akshare → EastMoney fallback.

        Returns (is_limited, direction_reason).
        """
        if self._use_mock_data:
            return False, ""
        try:
            from tradingagents.astock.data_sources.suspension import is_at_price_limit_external
            limited, direction = is_at_price_limit_external(symbol, trade_date)
            if limited:
                return True, f"external_{direction}"
        except Exception:
            logger.debug("External price limit check unavailable for %s", symbol)
        return False, ""

    def run(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        strategy: "StrategyBase | str",
        rebalance_freq: str = "M",
        *,
        initial_cash: float = 100000.0,
        auto_regime: bool = False,
        regime_symbol: str = "000300.SH",
    ) -> BacktestResult:
        """Execute a single-symbol backtest.

        Parameters
        ----------
        symbol : str
            A-share symbol (e.g. ``"600519.SH"``).
        start_date : str
            Start date (``"YYYY-MM-DD"``).
        end_date : str
            End date (``"YYYY-MM-DD"``).
        strategy : StrategyBase or str
            Strategy instance, or a canonical name string (e.g.
            ``"MovingAverageTrend"``) that will be resolved via the
            strategy registry.
        rebalance_freq : str
            Pandas offset alias for rebalance periods (default ``"M"`` =
            monthly).
        initial_cash : float
            Starting cash (default 100000).

        Returns
        -------
        BacktestResult
        """
        # ── Resolve strategy name → instance ───────────────────────
        if isinstance(strategy, str):
            from ..strategy_base import (
                MovingAverageTrendStrategy,
                BullTrendStrategy,
                ValueAverageStrategy,
                MeanReversionStrategy,
                RSIRangeStrategy,
                DefensiveMomentumStrategy,
                PutWriteStrategy,
                MACDTrendStrategy,
                BollingerBandsReversionStrategy,
                GridTradingStrategy,
            )

            _NAME_TO_CLASS: dict[str, type] = {
                "MovingAverageTrend": MovingAverageTrendStrategy,
                "BullTrend": BullTrendStrategy,
                "ValueAverage": ValueAverageStrategy,
                "MeanReversion": MeanReversionStrategy,
                "RSIRange": RSIRangeStrategy,
                "DefensiveMomentum": DefensiveMomentumStrategy,
                "PutWrite": PutWriteStrategy,
                "MACDTrend": MACDTrendStrategy,
                "BollingerBandsReversion": BollingerBandsReversionStrategy,
                "GridTrading": GridTradingStrategy,
            }
            cls = _NAME_TO_CLASS.get(strategy)
            if cls is None:
                if strategy == "MomentumRotation":
                    raise ValueError(
                        f"MomentumRotation is a portfolio-level strategy and cannot be used with BacktestEngine.run(). "
                        f"Use BacktestEngine.run_portfolio(symbols=..., strategy=MomentumRotationStrategy(config)) instead."
                    )
                raise ValueError(
                    f"Unknown strategy name {strategy!r}. "
                    f"Available: {list(_NAME_TO_CLASS.keys())}"
                )
            strategy = cls({})

        df = self._fetch_data(symbol, start_date, end_date)

        # Build data assumption — reflects whether mock or real data was used
        if self._use_mock_data:
            data_assumption = BacktestDataAssumption.mock().to_dict()
        else:
            bias_risks = self._detect_bias(df, start_date, end_date)
            st_delisted = self._detect_st_delisted(df, symbol, start_date, end_date)
            data_assumption = BacktestDataAssumption(
                data_source="real_facade",
                data_quality="normal",
                survivorship_bias_risk=bias_risks["survivorship_bias_risk"],
                look_ahead_bias_risk=bias_risks["look_ahead_bias_risk"],
                st_stock=st_delisted["st_stock"],
                delisted=st_delisted["delisted"],
            ).to_dict()

        # Validate trading calendar
        try:
            from tradingagents.astock.data_sources.calendar import is_trading_day

            sd = date_type.fromisoformat(start_date)
            ed = date_type.fromisoformat(end_date)
            cal_notes = []
            if not is_trading_day(sd):
                cal_notes.append("start_date {0} is not a trading day".format(start_date))
            if not is_trading_day(ed):
                cal_notes.append("end_date {0} is not a trading day".format(end_date))
            if cal_notes:
                notes = list(data_assumption.get("notes", []))
                notes.extend(cal_notes)
                data_assumption["notes"] = notes
        except Exception:
            logger.debug("Calendar validation failed for %s", symbol)

        if df.empty:
            return BacktestResult(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                fee_config_used={
                    "commission_rate": self.fee_config.commission_rate,
                    "stamp_tax_rate": self.fee_config.stamp_tax_rate,
                    "slippage_rate": self.fee_config.slippage_rate,
                    "min_commission": self.fee_config.min_commission,
                },
                data_assumption=data_assumption,
            )

        # ── Force date range slice ──
        df = df[(df.index >= pd.Timestamp(start_date)) & (df.index <= pd.Timestamp(end_date))]
        if df.empty:
            return BacktestResult(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                fee_config_used={
                    "commission_rate": self.fee_config.commission_rate,
                    "stamp_tax_rate": self.fee_config.stamp_tax_rate,
                    "slippage_rate": self.fee_config.slippage_rate,
                    "min_commission": self.fee_config.min_commission,
                },
                data_assumption=data_assumption,
            )

        # ── Auto market regime analysis ──
        if auto_regime and not df.empty and isinstance(df, pd.DataFrame):
            try:
                from tradingagents.astock.analysis.market_analyzer import analyze_regime_from_df

                regime = analyze_regime_from_df(df)
                notes = list(data_assumption.get("notes", []))
                notes.append(f"regime_{regime['verdict']}(score={regime['composite_score']})")
                notes.append(f"recommended_{','.join(regime['recommended_strategies'])}")
                data_assumption["notes"] = notes
                logger.debug(
                    "Market regime for %s: %s (score=%.4f) → %s",
                    symbol, regime["verdict"], regime["composite_score"],
                    regime["recommended_strategies"],
                )
            except Exception:
                logger.debug("Regime analysis unavailable for %s", symbol)

        # --- Group by rebalance periods ---
        periods = df.resample(rebalance_freq.replace("M", "ME"))
        cash = initial_cash
        shares = 0.0
        portfolio_values: list[float] = [initial_cash]
        dates: list[pd.Timestamp] = [df.index[0]]
        trades: list[dict] = []
        period_records: list[dict] = []

        for period_label, period_data in periods:
            if period_data.empty:
                continue
            # Get the last close of the period for signal generation
            close_at_end = float(period_data["close"].iloc[-1])

            # ── Get actual previous trading day's close from full df ──
            current_date = period_data.index[-1]
            current_pos = df.index.get_loc(current_date)
            # df.index is a DatetimeIndex (unique), get_loc returns int
            if isinstance(current_pos, int) and current_pos > 0:
                actual_prev_close = float(df["close"].iloc[current_pos - 1])
            else:
                actual_prev_close = None

            # Generate signal from period data
            signal_series = strategy.generate_signals(period_data)
            # Take the last non-zero or most recent signal
            non_zero = signal_series[signal_series != 0]
            signal = int(non_zero.iloc[-1]) if not non_zero.empty else 0

            period_start_val = cash + shares * close_at_end

            if signal == 1 and cash > 0:
                # Check constraints before buying
                price_limit, limit_reason = self._is_at_price_limit(actual_prev_close, close_at_end, data_assumption.get("st_stock", False))
                suspended, suspend_reason = self._is_suspended(period_data)
                trade_date_str = str(period_data.index[-1].date()) if hasattr(period_data.index[-1], 'date') else str(period_data.index[-1])
                # Also check external suspension data source
                if not suspended:
                    ext_susp, ext_reason = self._check_external_suspension(symbol, trade_date_str)
                    if ext_susp:
                        suspended, suspend_reason = ext_susp, ext_reason
                # Also check external price limit data source (akshare 涨停/跌停 pools)
                if not price_limit:
                    ext_pl, ext_pl_reason = self._check_external_price_limit(symbol, trade_date_str)
                    if ext_pl:
                        price_limit, limit_reason = ext_pl, ext_pl_reason
                constraint_notes = []
                if data_assumption.get("price_limit_check", True) and price_limit:
                    # Buy blocked only by limit UP (涨停 — no sellers)
                    if "up" in limit_reason:
                        constraint_notes.append(f"buy_skipped_{limit_reason}")
                if data_assumption.get("suspension_check", True) and suspended:
                    constraint_notes.append(f"buy_skipped_{suspend_reason}")
                if constraint_notes:
                    for n in constraint_notes:
                        if n not in data_assumption.get("notes", []):
                            data_assumption.setdefault("notes", []).append(n)
                    continue

                # Buy: invest all cash minus fees
                max_shares = cash / close_at_end
                # Iteratively reduce shares until net_cost ≤ cash
                buy_shares = max_shares
                for _ in range(5):
                    fees = calculate_fees(close_at_end, buy_shares, is_buy=True, config=self.fee_config)
                    net_cost = buy_shares * close_at_end + fees["total"]
                    if net_cost <= cash:
                        break
                    buy_shares = (cash - fees.get("total", 0)) / close_at_end
                # Apply volume capacity constraint
                volume_cap = data_assumption.get("volume_cap_pct", 25.0)
                if volume_cap > 0:
                    daily_volume = float(period_data["volume"].iloc[-1])
                    volume_max_shares = daily_volume * (volume_cap / 100.0)
                    if buy_shares > volume_max_shares:
                        buy_shares = volume_max_shares
                        cap_note = f"volume_cap_{volume_cap}pct_applied"
                        if cap_note not in data_assumption.get("notes", []):
                            data_assumption.setdefault("notes", []).append(cap_note)
                # Determine active constraints for this trade
                buy_constraint = None
                if price_limit and data_assumption.get("price_limit_check", True):
                    buy_constraint = limit_reason
                elif volume_cap > 0 and buy_shares < max_shares - 0.001:
                    buy_constraint = "volume_cap"
                if buy_shares > 0.001:
                    fees = calculate_fees(close_at_end, buy_shares, is_buy=True, config=self.fee_config)
                    net_cost = buy_shares * close_at_end + fees["total"]
                    shares += buy_shares
                    cash -= net_cost
                    trade = {
                        "date": str(period_data.index[-1].date()),
                        "type": "buy",
                        "price": close_at_end,
                        "shares": round(buy_shares, 4),
                        "fees": fees["total"],
                        "commission": fees["commission"],
                        "stamp_tax": fees["stamp_tax"],
                        "slippage": fees["slippage"],
                        "pnl": 0.0,
                    }
                    if buy_constraint:
                        trade["constraint"] = buy_constraint
                    trades.append(trade)
            elif signal == -1 and shares > 0:
                # Check constraints before selling
                price_limit, limit_reason = self._is_at_price_limit(actual_prev_close, close_at_end, data_assumption.get("st_stock", False))
                suspended, suspend_reason = self._is_suspended(period_data)
                trade_date_str = str(period_data.index[-1].date()) if hasattr(period_data.index[-1], 'date') else str(period_data.index[-1])
                # Also check external suspension data source
                if not suspended:
                    ext_susp, ext_reason = self._check_external_suspension(symbol, trade_date_str)
                    if ext_susp:
                        suspended, suspend_reason = ext_susp, ext_reason
                # Also check external price limit data source (akshare 涨停/跌停 pools)
                if not price_limit:
                    ext_pl, ext_pl_reason = self._check_external_price_limit(symbol, trade_date_str)
                    if ext_pl:
                        price_limit, limit_reason = ext_pl, ext_pl_reason
                constraint_notes = []
                if data_assumption.get("price_limit_check", True) and price_limit:
                    # Sell blocked only by limit DOWN (跌停 — no buyers)
                    if "down" in limit_reason:
                        constraint_notes.append(f"sell_skipped_{limit_reason}")
                if data_assumption.get("suspension_check", True) and suspended:
                    constraint_notes.append(f"sell_skipped_{suspend_reason}")
                if constraint_notes:
                    for n in constraint_notes:
                        if n not in data_assumption.get("notes", []):
                            data_assumption.setdefault("notes", []).append(n)
                    continue

                # Sell: liquidate all shares
                sell_value = shares * close_at_end
                fees = calculate_fees(close_at_end, shares, is_buy=False, config=self.fee_config)
                proceeds = sell_value - fees["total"]
                pnl = proceeds - (shares * close_at_end - sell_value)  # simplified P&L
                cash += proceeds
                sell_constraint = None
                if price_limit and data_assumption.get("price_limit_check", True):
                    sell_constraint = limit_reason
                trade = {
                    "date": str(period_data.index[-1].date()),
                    "type": "sell",
                    "price": close_at_end,
                    "shares": round(shares, 4),
                    "fees": fees["total"],
                    "commission": fees["commission"],
                    "stamp_tax": fees["stamp_tax"],
                    "slippage": fees["slippage"],
                    "pnl": round(proceeds - (shares * close_at_end), 4),
                }
                if sell_constraint:
                    trade["constraint"] = sell_constraint
                trades.append(trade)
                shares = 0.0

            end_val = cash + shares * close_at_end
            portfolio_values.append(end_val)
            dates.append(period_data.index[-1])

            period_records.append({
                "period": str(period_label),
                "signal": signal,
                "start_value": round(period_start_val, 2),
                "end_value": round(end_val, 2),
                "close": close_at_end,
                "shares": round(shares, 4),
                "cash": round(cash, 2),
            })

        # Final valuation
        equity = pd.Series(portfolio_values, index=dates)

        # Compute metrics
        metrics = summarize_metrics(equity, trades)
        total_return = float(equity.iloc[-1] / equity.iloc[0] - 1)

        # Accumulate cost breakdown from all trades
        cost_breakdown = {
            "total_fees": 0.0,
            "commission": 0.0,
            "stamp_tax": 0.0,
            "slippage": 0.0,
        }
        for t in trades:
            fees = t.get("fees", 0)
            if isinstance(fees, (int, float)):
                cost_breakdown["total_fees"] += fees
            # If trade has detailed fee keys, use them directly
            for key in ("commission", "stamp_tax", "slippage"):
                val = t.get(key)
                if isinstance(val, (int, float)):
                    cost_breakdown[key] += val

        return BacktestResult(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            total_return=round(total_return, 6),
            annualized_return=metrics["annualized_return"],
            sharpe_ratio=metrics["sharpe_ratio"],
            max_drawdown=metrics["max_drawdown"],
            win_rate=metrics["win_rate"],
            total_trades=metrics["total_trades"],
            trades=trades,
            periods=period_records,
            fee_config_used={
                "commission_rate": self.fee_config.commission_rate,
                "stamp_tax_rate": self.fee_config.stamp_tax_rate,
                "slippage_rate": self.fee_config.slippage_rate,
                "min_commission": self.fee_config.min_commission,
            },
            data_assumption=data_assumption,
            cost_breakdown=cost_breakdown,
        )

    def run_portfolio(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        strategy: Any,
        *,
        initial_cash: float = 1_000_000.0,
        benchmark_symbol: str = "588000.SH",
        data_source: str | None = None,
        auto_regime: bool = False,
    ) -> BacktestResult:
        """组合级回测 — 多标的动量轮动。

        Parameters
        ----------
        symbols : list of str
            备选标的代码列表。
        start_date, end_date : str
            ``"YYYY-MM-DD"``.
        strategy : MomentumRotationStrategy
            组合策略实例。
        initial_cash : float
            初始资金（默认 1_000_000）。
        benchmark_symbol : str
            基准标的（默认 588000.SH 科创50ETF）。
        data_source : str or None
            数据来源描述。

        Returns
        -------
        BacktestResult
        """
        # ── 1. 获取全部标的价格（统一批量获取） ──
        from ..strategy_base import fetch_multi_stock_prices

        all_symbols = list(set(symbols + [benchmark_symbol]))
        prices = fetch_multi_stock_prices(all_symbols, start_date, end_date, column="close")

        if prices.empty:
            return BacktestResult(symbol="Portfolio", start_date=start_date, end_date=end_date)

        # Separate stock cols vs benchmark
        stock_cols = [c for c in prices.columns if c != benchmark_symbol and c in symbols]
        bench_col = benchmark_symbol if benchmark_symbol in prices.columns else None

        if not stock_cols:
            return BacktestResult(symbol="Portfolio", start_date=start_date, end_date=end_date)

        stock_prices = prices[stock_cols]

        # ── Auto market regime analysis (on benchmark) ──
        data_assumption: dict[str, Any] = {
            "adjustment": "forward",
            "cost_model": "default",
            "settlement": "t+1",
            "data_source": data_source or "real_facade",
            "look_ahead_bias_risk": True,
            "notes": ["T+1 execution lag applied per A-share convention"],
        }
        if auto_regime and bench_col and not prices.empty:
            try:
                from tradingagents.astock.analysis.market_analyzer import analyze_regime_from_df

                regime = analyze_regime_from_df(prices)
                notes = list(data_assumption.get("notes", []))
                notes.append(f"regime_{regime['verdict']}(score={regime['composite_score']})")
                notes.append(f"recommended_{','.join(regime['recommended_strategies'])}")
                data_assumption["notes"] = notes
            except Exception:
                logger.debug("Regime analysis unavailable for portfolio mode")

        # ── 2. 日收益率 ──
        daily_ret = stock_prices.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
        if bench_col:
            bench_ret = prices[bench_col].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
        else:
            bench_ret = pd.Series(0.0, index=daily_ret.index)

        # ── 3. 调仓周期 ──
        all_dates = daily_ret.index
        rebalance_dates = strategy.get_rebalance_dates(all_dates)

        # ── 4. 逐期调仓 ──
        cash = initial_cash
        holdings: dict[str, float] = {}  # symbol → value
        portfolio_values: list[float] = [initial_cash]
        dates_list: list[pd.Timestamp] = [all_dates[0]]
        trades: list[dict] = []
        stock_selection_freq: dict[str, int] = {s: 0 for s in stock_cols}

        for i, rebal_date in enumerate(rebalance_dates):
            rebal_pos = all_dates.get_loc(rebal_date)
            if not isinstance(rebal_pos, (int, np.integer)):
                continue
            # T+1 执行：权重在下一个交易日生效
            if rebal_pos + 1 < len(all_dates):
                exec_date = all_dates[rebal_pos + 1]
            else:
                exec_date = rebal_date

            # 读取当前动量快照
            price_slice = stock_prices.loc[:rebal_date]
            if len(price_slice) < strategy.warmup:
                continue

            weights = strategy.generate_portfolio_weights(price_slice, holdings)
            if not weights:
                # 空仓
                cash = initial_cash
                holdings = {}
                trades.append({"date": str(exec_date.date()), "type": "clear", "weights": {}})
                portfolio_values.append(cash)
                dates_list.append(exec_date)
                continue

            # T+1 执行日买入
            exec_prices = stock_prices.loc[exec_date] if exec_date in stock_prices.index else stock_prices.iloc[-1]
            target_value = initial_cash
            new_holdings: dict[str, float] = {}
            for sym, w in weights.items():
                if sym in exec_prices.index and pd.notna(exec_prices[sym]) and exec_prices[sym] > 0:
                    shares_in_value = target_value * w
                    new_holdings[sym] = shares_in_value
                stock_selection_freq[sym] = stock_selection_freq.get(sym, 0) + 1

            holdings = new_holdings
            cash = 0.0  # fully invested
            trades.append({
                "date": str(exec_date.date()),
                "type": "rebalance",
                "weights": weights,
            })

            # 记录本日组合价值
            port_val = sum(holdings.values())
            portfolio_values.append(port_val)
            dates_list.append(exec_date)

        # ── 5. 日频组合价值 —— 用权重 × 日收益模拟 ──
        # 在调仓日之间保持权重不变
        weights_df = pd.DataFrame(0.0, index=all_dates, columns=stock_cols)
        prev_weights: dict[str, float] = {}
        for i, rebal_date in enumerate(rebalance_dates):
            rebal_pos = all_dates.get_loc(rebal_date)
            if not isinstance(rebal_pos, (int, np.integer)):
                continue
            exec_pos = min(rebal_pos + 1, len(all_dates) - 1)
            exec_date = all_dates[exec_pos]

            price_slice = stock_prices.loc[:rebal_date]
            if len(price_slice) < strategy.warmup:
                continue
            weights = strategy.generate_portfolio_weights(price_slice, prev_weights)
            if weights:
                prev_weights = weights
                # 权重在 exec_pos 到下次调仓前生效
                next_rebal_idx = i + 1
                if next_rebal_idx < len(rebalance_dates):
                    next_pos = all_dates.get_loc(rebalance_dates[next_rebal_idx])
                    end_pos = min(next_pos, len(all_dates))
                else:
                    end_pos = len(all_dates)

                for sym, w in weights.items():
                    if sym in weights_df.columns:
                        weights_df.loc[all_dates[exec_pos:end_pos], sym] = w

        # T+1 滞后
        weights_lagged = weights_df.shift(1).dropna()
        aligned_ret = daily_ret.loc[weights_lagged.index]
        portfolio_daily_ret = (weights_lagged * aligned_ret).sum(axis=1)

        # 对齐基准
        common_idx = portfolio_daily_ret.index.intersection(bench_ret.index)
        portfolio_daily_ret = portfolio_daily_ret.loc[common_idx]
        bench_ret_aligned = bench_ret.loc[common_idx]

        # ── 6. 累计收益 ──
        port_cum = (1 + portfolio_daily_ret).cumprod()
        bench_cum = (1 + bench_ret_aligned).cumprod()
        total_return = float(port_cum.iloc[-1] / port_cum.iloc[0] - 1) if len(port_cum) > 1 else 0.0
        bench_return = float(bench_cum.iloc[-1] / bench_cum.iloc[0] - 1) if len(bench_cum) > 1 else 0.0

        # ── 7. 绩效指标 ──
        years = len(common_idx) / 252.0 if len(common_idx) > 0 else 1.0
        annualized = (1 + total_return) ** (1 / max(years, 0.5)) - 1

        excess = portfolio_daily_ret
        sharpe = float(np.sqrt(252) * excess.mean() / max(excess.std(), 1e-10)) if not excess.empty else 0.0

        rolling_max = port_cum.expanding().max()
        drawdown = (port_cum - rolling_max) / rolling_max
        max_dd = float(drawdown.min()) if not drawdown.empty else 0.0

        win_rate = float((portfolio_daily_ret > 0).mean()) if not portfolio_daily_ret.empty else 0.0
        total_selections = sum(stock_selection_freq.values())

        # ── 8. periods ──
        periods = []
        for dt in common_idx:
            periods.append({
                "period": str(dt.date()),
                "portfolio_value": round(float(port_cum.loc[dt] * initial_cash), 2),
                "benchmark_value": round(float(bench_cum.loc[dt] * initial_cash), 2),
            })

        return BacktestResult(
            symbol="Portfolio",
            strategy_name="MomentumRotation",
            start_date=start_date,
            end_date=end_date,
            total_return=round(total_return, 6),
            annualized_return=round(annualized, 6),
            sharpe_ratio=round(sharpe, 4),
            max_drawdown=round(max_dd, 6),
            win_rate=round(win_rate, 6),
            total_trades=total_selections,
            trades=trades,
            periods=periods,
            benchmark_symbol=benchmark_symbol,
            benchmark_return=round(bench_return, 6),
            fee_config_used={
                "commission_rate": self.fee_config.commission_rate,
                "stamp_tax_rate": self.fee_config.stamp_tax_rate,
                "slippage_rate": self.fee_config.slippage_rate,
                "min_commission": self.fee_config.min_commission,
            },
            data_assumption=data_assumption,
        )
