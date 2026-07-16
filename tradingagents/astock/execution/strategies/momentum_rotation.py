"""龙头股动量轮动策略 (Leading Stock Momentum Rotation).

基于风险调整动量的龙头股票主动轮动策略，核心思路：
1. 标的池：22 只 A 股各赛道龙头股票
2. 风险调整动量 = N日平均收益率 / √N日收益率方差
3. 定期调仓：每 K 个交易日，选正动量中调整动量前 L 只
4. 权重 = 调整动量归一化
5. 对比基准：科创 50ETF + 等权重组合

Reference:
    https://mp.weixin.qq.com/s/qlq37Ih5xjx-y6CzOFOwSQ
    https://mp.weixin.qq.com/s/BsuTF4JrDikMwkSnprFiKA
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from tradingagents.astock.execution.strategy_base import MomentumRotationStrategy

logger = logging.getLogger(__name__)

# ── 龙头股票获取（动态优先，硬编码兜底） ──────────────────────────

_DEFAULT_LEADING_STOCKS: list[dict[str, str]] = [
    {"symbol": "600111.SH", "name": "北方稀土", "sector": "有色"},
    {"symbol": "002460.SZ", "name": "赣锋锂业", "sector": "有色"},
    {"symbol": "601899.SH", "name": "紫金矿业", "sector": "有色"},
    {"symbol": "600988.SH", "name": "赤峰黄金", "sector": "有色"},
    {"symbol": "002230.SZ", "name": "科大讯飞", "sector": "科技"},
    {"symbol": "300750.SZ", "name": "宁德时代", "sector": "新能源"},
    {"symbol": "002594.SZ", "name": "比亚迪",   "sector": "新能源"},
    {"symbol": "603259.SH", "name": "药明康德", "sector": "医药"},
    {"symbol": "601939.SH", "name": "建设银行", "sector": "金融"},
    {"symbol": "688256.SH", "name": "寒武纪",   "sector": "科技"},
    {"symbol": "601606.SH", "name": "长城军工", "sector": "军工"},
    {"symbol": "688981.SH", "name": "中芯国际", "sector": "科技"},
    {"symbol": "300502.SZ", "name": "新易盛",   "sector": "科技"},
    {"symbol": "601138.SH", "name": "工业富联", "sector": "科技"},
    {"symbol": "300308.SZ", "name": "中际旭创", "sector": "科技"},
    {"symbol": "300476.SZ", "name": "胜宏科技", "sector": "科技"},
    {"symbol": "300394.SZ", "name": "天孚通信", "sector": "科技"},
    {"symbol": "688041.SH", "name": "海光信息", "sector": "科技"},
    {"symbol": "601336.SH", "name": "新华保险", "sector": "金融"},
    {"symbol": "600519.SH", "name": "贵州茅台", "sector": "消费"},
    {"symbol": "601288.SH", "name": "农业银行", "sector": "金融"},
    {"symbol": "601319.SH", "name": "中国人保", "sector": "金融"},
]

_LEADING_STOCKS_CACHE: list[dict[str, str]] | None = None
_LEADING_STOCKS_SOURCE: str = "default"
_leading_stocks_lock = threading.Lock()


def get_leading_stocks() -> tuple[list[dict[str, str]], str]:
    """Get leading stocks: try EastMoney dynamic → fallback default list.

    Returns (stocks, source_name).
    """
    global _LEADING_STOCKS_CACHE, _LEADING_STOCKS_SOURCE
    if _LEADING_STOCKS_CACHE is not None:
        return _LEADING_STOCKS_CACHE, _LEADING_STOCKS_SOURCE

    with _leading_stocks_lock:
        # Double-check after acquiring lock
        if _LEADING_STOCKS_CACHE is not None:
            return _LEADING_STOCKS_CACHE, _LEADING_STOCKS_SOURCE

    # Try EastMoney: all A-shares sorted by market cap
    try:
        import akshare as ak

        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty and "总市值" in df.columns:
            top = df.nlargest(25, "总市值")
            stocks = []
            for _, row in top.iterrows():
                code = str(row["代码"])
                sym = f"{code}.SH" if code.startswith("6") else f"{code}.SZ"
                stocks.append({
                    "symbol": sym,
                    "name": str(row["名称"]),
                    "sector": str(row.get("行业", "")),
                })
            if stocks:
                _LEADING_STOCKS_CACHE = stocks
                _LEADING_STOCKS_SOURCE = "eastmoney"
                return stocks, "eastmoney"
    except Exception:
        logger.warning("Failed to fetch leading stocks from eastmoney, using defaults")

    # Fallback to default
    _LEADING_STOCKS_CACHE = _DEFAULT_LEADING_STOCKS
    _LEADING_STOCKS_SOURCE = "default"
    return _DEFAULT_LEADING_STOCKS, "default"


def refresh_leading_stocks() -> tuple[list[dict[str, str]], str]:
    """Force re-fetch leading stocks, clearing cache."""
    global _LEADING_STOCKS_CACHE
    _LEADING_STOCKS_CACHE = None
    return get_leading_stocks()


BENCHMARK_SYMBOL = "588000.SH"  # 科创50ETF
BENCHMARK_NAME = "科创50ETF"
LEADING_STOCKS = _DEFAULT_LEADING_STOCKS  # alias for backward compat


@dataclass
class MomentumRotationResult:
    """回测结果."""

    strategy_name: str = "MomentumRotation"
    symbol: str = "龙头股组合"
    start_date: str = ""
    end_date: str = ""
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    periods: list[dict] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)
    # Strategy-specific
    benchmark_return: float = 0.0
    equal_weight_return: float = 0.0
    daily_returns: list[float] = field(default_factory=list)
    benchmark_daily_returns: list[float] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    stock_weights: list[dict] = field(default_factory=list)  # per-rebalance weights
    stock_selection_freq: dict[str, int] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)


def run_momentum_rotation(
    start_date: str = "2024-01-01",
    end_date: str | None = None,
    n: int = 20,
    k: int = 5,
    l: int = 5,
    initial_cash: float = 1_000_000.0,
) -> MomentumRotationResult:
    """运行龙头股动量轮动回测.

    Parameters
    ----------
    start_date : str
        回测开始日期 YYYY-MM-DD.
    end_date : str or None
        回测结束日期，默认今天.
    n : int
        动量计算周期（天），默认 20.
    k : int
        调仓间隔（交易日），默认 5.
    l : int
        持仓标的数量，默认 5.
    initial_cash : float
        初始资金.

    Returns
    -------
    MomentumRotationResult
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    result = MomentumRotationResult(
        start_date=start_date,
        end_date=end_date,
        params={"N": n, "K": k, "L": l, "initial_cash": initial_cash},
    )

    # ── 1. 获取数据 ──
    prices = _fetch_all_prices(start_date, end_date)
    if prices is None or prices.empty:
        logger.warning("No price data available for momentum rotation")
        return result

    # Separate benchmark from stocks
    stock_symbols_in_data = [s["symbol"] for s in LEADING_STOCKS if s["symbol"] in prices.columns]
    bench_in_data = BENCHMARK_SYMBOL if BENCHMARK_SYMBOL in prices.columns else None

    if not stock_symbols_in_data:
        logger.warning("No stock data available")
        return result

    stock_prices = prices[stock_symbols_in_data]
    result.dates = [str(d.date()) for d in stock_prices.index]

    # ── 2. 计算日收益率 ──
    daily_ret = stock_prices.pct_change().dropna()
    if bench_in_data:
        bench_ret = prices[BENCHMARK_SYMBOL].pct_change().dropna()
    else:
        bench_ret = pd.Series(0.0, index=daily_ret.index)

    # ── 3. 使用 MomentumRotationStrategy 生成权重 ──
    strat = MomentumRotationStrategy({"n": n, "k": k, "l": l, "warmup": n})
    all_dates = daily_ret.index
    rebalance_dates = strat.get_rebalance_dates(all_dates)
    weights_df = pd.DataFrame(0.0, index=all_dates, columns=stock_symbols_in_data)
    stock_selection_freq: dict[str, int] = {s: 0 for s in stock_symbols_in_data}

    prev_weights: dict[str, float] = {}
    for rebal_date in rebalance_dates:
        price_slice = stock_prices.loc[:rebal_date]
        if len(price_slice) < n:
            continue
        weights = strat.generate_portfolio_weights(price_slice, prev_weights)
        if not weights:
            prev_weights = {}
            continue

        prev_weights = weights
        # 记录选中频率
        for sym in weights:
            stock_selection_freq[sym] = stock_selection_freq.get(sym, 0) + 1

        # 权重生效至下次调仓前
        rebal_pos = all_dates.get_loc(rebal_date)
        if not isinstance(rebal_pos, (int, np.integer)):
            continue
        next_idx = rebal_pos + k
        if next_idx < len(all_dates):
            end_slice = all_dates[next_idx]
        else:
            end_slice = all_dates[-1]

        mask = (all_dates >= rebal_date) & (all_dates < end_slice)
        for sym, w in weights.items():
            if sym in weights_df.columns:
                weights_df.loc[mask, sym] = w

        # 记录调仓记录
        result.trades.append({
            "date": str(rebal_date.date()),
            "positions": [{"symbol": sym, "weight": round(float(w), 4)} for sym, w in weights.items()],
        })

    # ── 5. 滞后一天（T+1 执行） ──
    weights_lagged = weights_df.shift(1).dropna()
    daily_ret_aligned = daily_ret.loc[weights_lagged.index]

    # ── 6. 计算组合收益率 ──
    portfolio_ret = (weights_lagged * daily_ret_aligned).sum(axis=1)

    # ── 7. 等权重基准 ──
    ew_ret = daily_ret_aligned.mean(axis=1)

    # ── 8. 对齐基准 ──
    common_idx = portfolio_ret.index.intersection(bench_ret.index)
    portfolio_ret = portfolio_ret.loc[common_idx]
    ew_ret = ew_ret.loc[common_idx]
    bench_ret_aligned = bench_ret.loc[common_idx]

    # ── 9. 计算累计收益 ──
    portfolio_cum = (1 + portfolio_ret).cumprod()
    bench_cum = (1 + bench_ret_aligned).cumprod()
    ew_cum = (1 + ew_ret).cumprod()

    # 生成 periods（用于 equity curve）
    periods = []
    for dt in common_idx:
        periods.append(
            {
                "period": str(dt.date()),
                "portfolio_value": float(portfolio_cum.loc[dt] * initial_cash),
                "benchmark_value": float(bench_cum.loc[dt] * initial_cash),
                "equal_weight_value": float(ew_cum.loc[dt] * initial_cash),
            }
        )

    # ── 10. 计算绩效指标 ──
    total_return = float(portfolio_cum.iloc[-1] / portfolio_cum.iloc[0] - 1) if len(portfolio_cum) > 1 else 0.0
    benchmark_return = float(bench_cum.iloc[-1] / bench_cum.iloc[0] - 1) if len(bench_cum) > 1 else 0.0
    ew_return = float(ew_cum.iloc[-1] / ew_cum.iloc[0] - 1) if len(ew_cum) > 1 else 0.0

    # 年化收益
    years = len(common_idx) / 252 if len(common_idx) > 0 else 1
    annualized = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0.0

    # 夏普 (rf ≈ 0)
    excess = portfolio_ret
    sharpe = float(np.sqrt(252) * excess.mean() / excess.std()) if excess.std() > 0 else 0.0

    # 最大回撤
    rolling_max = portfolio_cum.expanding().max()
    drawdown = (portfolio_cum - rolling_max) / rolling_max
    max_dd = float(drawdown.min()) if not drawdown.empty else 0.0

    # 胜率
    win_rate = float((portfolio_ret > 0).mean()) if not portfolio_ret.empty else 0.0

    # 交易次数：选中次数
    total_selections = sum(stock_selection_freq.values())

    return MomentumRotationResult(
        total_return=round(total_return, 6),
        annualized_return=round(annualized, 6),
        sharpe_ratio=round(sharpe, 4),
        max_drawdown=round(max_dd, 6),
        win_rate=round(win_rate, 6),
        total_trades=total_selections,
        periods=periods,
        trades=result.trades,
        benchmark_return=round(benchmark_return, 6),
        equal_weight_return=round(ew_return, 6),
        daily_returns=[round(float(v), 6) for v in portfolio_ret.values],
        benchmark_daily_returns=[round(float(v), 6) for v in bench_ret_aligned.values],
        dates=[str(d.date()) for d in common_idx],
        stock_weights=result.trades,
        stock_selection_freq=stock_selection_freq,
        start_date=start_date,
        end_date=end_date,
        params={"N": n, "K": k, "L": l, "initial_cash": initial_cash},
    )


def _fetch_all_prices(start_date: str, end_date: str) -> pd.DataFrame | None:
    """Fetch adjusted close prices for all leading stocks + benchmark via unified API."""
    leading, _ = get_leading_stocks()
    all_symbols = [s["symbol"] for s in leading] + [BENCHMARK_SYMBOL]
    try:
        from tradingagents.astock.execution.strategy_base import fetch_multi_stock_prices
        df = fetch_multi_stock_prices(all_symbols, start_date, end_date, column="close")
        return df if not df.empty else None
    except Exception:
        return None
