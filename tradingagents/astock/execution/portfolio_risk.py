"""Portfolio risk calculation engine for Phase 36.

Provides functions for:
- Value-at-Risk (VaR) computation
- Industry exposure analysis
- Brinson-style performance attribution
- Aggregate risk exposure summary
"""

from __future__ import annotations

import math
from typing import Any

from tradingagents.astock.schemas.portfolio import Attribution, RiskExposure
from tradingagents.astock.schemas.trading_execution import Position


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _norm_ppf(p: float) -> float:
    """Standard normal inverse CDF (z-score) via Python's built-in NormalDist.

    Uses the ``statistics.NormalDist`` class (Python 3.8+) which implements
    the highly accurate Peter J. Acklam approximation (relative error < 1e-15).

    Parameters
    ----------
    p : float
        Cumulative probability in ``(0, 1)``.

    Returns
    -------
    float
        The z-score such that ``Φ(z) ≈ p``.

    Raises
    ------
    ValueError
        If *p* is not in ``(0, 1)``.
    """
    from statistics import NormalDist

    _NORMAL = NormalDist()  # standard N(0,1)

    if not 0 < p < 1:
        msg = f"confidence must be in (0, 1), got {p}"
        raise ValueError(msg)
    return _NORMAL.inv_cdf(p)


def _portfolio_value(positions: list[Position], cash: float) -> float:
    """Total NAV = sum of position market values + cash."""
    return sum(p.market_value for p in positions) + cash


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def calculate_var(
    positions: list[Position],
    cash: float,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Compute parametric Value-at-Risk for the portfolio.

    Uses a simple parametric approach: estimates the standard deviation
    of portfolio returns from position-level P&L data, then computes
    ``VaR = z * sigma * nav`` where *z* is the normal quantile at the
    given confidence level.

    Parameters
    ----------
    positions : list[Position]
        Current open positions.
    cash : float
        Cash held.
    confidence : float
        Confidence level in ``(0, 1)`` (default ``0.95``).

    Returns
    -------
    tuple[float, float]
        ``(var_value, var_pct)`` where both are **positive** numbers
        representing potential loss (e.g. ``var_value=12500`` means a
        possible loss of ¥12 500).  ``var_pct`` is relative to NAV.
    """
    nav = _portfolio_value(positions, cash)
    if nav <= 0 or not positions:
        return 0.0, 0.0

    # Compute per-position returns and weights
    weights: list[float] = []
    returns: list[float] = []
    for p in positions:
        cost_basis = p.market_value - p.pnl
        ret = p.pnl / cost_basis if cost_basis != 0 else 0.0
        w = p.market_value / nav
        weights.append(w)
        returns.append(ret)

    # Portfolio expected return (weighted average)
    portfolio_return = sum(w * r for w, r in zip(weights, returns, strict=False))

    # Variance of portfolio returns: sum_i sum_j w_i w_j sigma_ij
    # Simplified: treat each position return as independent, compute
    # weighted std of individual returns.
    n = len(returns)
    if n < 2:
        # Single position — use absolute return as volatility proxy
        sigma = abs(portfolio_return) if portfolio_return != 0 else 0.01
    else:
        # Weighted standard deviation of position returns
        mean_ret = sum(returns) / n
        variance = sum(w * (r - mean_ret) ** 2 for w, r in zip(weights, returns, strict=False))
        # Bessel correction for weighted sample
        variance *= n / max(n - 1, 1)
        sigma = math.sqrt(variance) if variance > 0 else 0.01

    z = _norm_ppf(confidence)
    var_value = z * sigma * nav
    var_pct = z * sigma

    return round(var_value, 2), round(var_pct, 6)


def calculate_industry_exposure(
    positions: list[Position],
) -> dict[str, float]:
    """Compute industry exposure as a fraction of total position value.

    Industry is inferred from the A-share symbol prefix:

    ========== ===========
    Prefix     Industry
    ========== ===========
    ``600xxx`` 金融 (Financial)
    ``000xxx`` 主板 (Main Board)
    ``300xxx`` 创业板 (ChiNext / Growth Enterprise)
    ``688xxx`` 科创板 (STAR Market / Sci-Tech)
    Other      其他 (Other)
    ========== ===========

    Parameters
    ----------
    positions : list[Position]
        Current open positions.

    Returns
    -------
    dict[str, float]
        Mapping of ``industry_name → allocation_pct`` (values in ``[0, 1]``).
    """
    if not positions:
        return {}

    total_value = sum(p.market_value for p in positions)
    if total_value <= 0:
        return {}

    industry_map: dict[str, float] = {}

    for p in positions:
        industry = _infer_industry(p.symbol)
        industry_map[industry] = industry_map.get(industry, 0.0) + p.market_value

    return {ind: round(val / total_value, 6) for ind, val in industry_map.items()}


def _infer_industry(symbol: str) -> str:
    """Map A-share stock symbol to an industry bucket."""
    sym = symbol.strip()
    if sym.startswith("600"):
        return "金融"          # Financial
    if sym.startswith("000"):
        return "主板"          # Main Board
    if sym.startswith("300"):
        return "创业板"        # ChiNext / Growth Enterprise
    if sym.startswith("688"):
        return "科创板"        # STAR Market / Sci-Tech
    return "其他"              # Other


def calculate_attribution(
    positions: list[Position],
    benchmark_return: float = 0.0,
) -> dict[str, Any]:
    """Brinson-style performance attribution.

    Decomposes excess portfolio return into selection and timing effects.
    Also computes cost impact from implied trade fees.

    Parameters
    ----------
    positions : list[Position]
        Current open positions.
    benchmark_return : float
        Benchmark return over the period (default ``0.0``).

    Returns
    -------
    dict
        Keys match :class:`~tradingagents.astock.schemas.portfolio.Attribution`
        field names: ``benchmark_return``, ``selection_effect``,
        ``timing_effect``, ``cost_impact``, ``slippage_impact``, ``residual``.
    """
    if not positions:
        return {
            "benchmark_return": benchmark_return,
            "selection_effect": 0.0,
            "timing_effect": 0.0,
            "cost_impact": 0.0,
            "slippage_impact": 0.0,
            "residual": 0.0,
        }

    nav = sum(p.market_value for p in positions)
    if nav <= 0:
        return {
            "benchmark_return": benchmark_return,
            "selection_effect": 0.0,
            "timing_effect": 0.0,
            "cost_impact": 0.0,
            "slippage_impact": 0.0,
            "residual": 0.0,
        }

    # Group positions by industry sector, compute sector weight and return
    sectors: dict[str, dict[str, float]] = {}
    for p in positions:
        sector = _infer_industry(p.symbol)
        cost_basis = p.market_value - p.pnl
        ret = p.pnl / cost_basis if cost_basis != 0 else 0.0

        if sector not in sectors:
            sectors[sector] = {"weight": 0.0, "return": 0.0, "count": 0}
        sectors[sector]["weight"] += p.market_value / nav
        sectors[sector]["return"] += ret
        sectors[sector]["count"] += 1

    # Average sector returns
    for s in sectors.values():
        s["return"] /= max(s["count"], 1)

    # Portfolio return
    portfolio_return = sum(
        s["weight"] * s["return"] for s in sectors.values()
    )

    # Brinson decomposition (simplified — equal benchmark sector weights)
    # When benchmark sector weights are unknown, we assume equal weighting
    # across active sectors.
    n_sectors = len(sectors)
    benchmark_sector_weight = 1.0 / max(n_sectors, 1)

    selection_effect = 0.0
    timing_effect = 0.0

    for s in sectors.values():
        # Allocation (timing) effect: over-/under-weighting sectors
        timing_effect += (s["weight"] - benchmark_sector_weight) * benchmark_return
        # Selection effect: choosing better stocks within sectors
        selection_effect += benchmark_sector_weight * (s["return"] - benchmark_return)

    # Cost impact: estimate trade fees from position P&L as a fraction of NAV
    # (positions with non-zero P&L imply some trading cost)
    total_fees_est = sum(
        abs(p.pnl) * 0.0003 for p in positions  # ~3 bps implied cost
    )
    cost_impact = total_fees_est / nav if nav > 0 else 0.0

    # Slippage impact: rough estimate based on position size concentration
    largest_weight = max((p.market_value / nav for p in positions), default=0.0)
    slippage_impact = largest_weight * 0.001  # 10 bps on largest position

    # Residual = portfolio_return - benchmark_return - selection - timing
    excess = portfolio_return - benchmark_return
    residual = excess - selection_effect - timing_effect + cost_impact + slippage_impact

    return {
        "benchmark_return": round(benchmark_return, 6),
        "selection_effect": round(selection_effect, 6),
        "timing_effect": round(timing_effect, 6),
        "cost_impact": round(cost_impact, 6),
        "slippage_impact": round(slippage_impact, 6),
        "residual": round(residual, 6),
    }


def calculate_risk_exposure(
    positions: list[Position],
    cash: float,
    historical_returns: Any = None,
) -> dict[str, Any]:
    """Aggregate risk exposure summary for a portfolio.

    Combines VaR, industry concentration, liquidity, and stress metrics
    into a single dict matching the
    :class:`~tradingagents.astock.schemas.portfolio.RiskExposure` schema.

    Parameters
    ----------
    positions : list[Position]
        Current open positions.
    cash : float
        Cash held.
    historical_returns : Any, optional
        A sequence of historical portfolio returns (``pd.Series``, ``list``,
        or ``None``).  Used for max-drawdown calculation.  ``None`` yields
        ``max_drawdown=0``.

    Returns
    -------
    dict
        Keys match :class:`~tradingagents.astock.schemas.portfolio.RiskExposure`
        field names: ``industry_concentration``, ``top_holding_pct``,
        ``beta``, ``liquidity_score``, ``var_95``, ``max_drawdown``,
        ``stress_loss_pct``.
    """
    nav = _portfolio_value(positions, cash)

    # --- VaR ---
    var_value, var_pct = calculate_var(positions, cash, confidence=0.95)

    # --- Industry exposure & concentration ---
    industry_exposure = calculate_industry_exposure(positions)
    if industry_exposure:
        # Herfindahl–Hirschman Index for concentration
        hhi = sum(v * v for v in industry_exposure.values())
        # Normalise to [0, 1]: (HHI - 1/N) / (1 - 1/N)
        n = len(industry_exposure)
        industry_concentration = (hhi - 1.0 / n) / (1.0 - 1.0 / n) if n > 1 else 1.0
    else:
        industry_concentration = 0.0

    # --- Top holding concentration ---
    if positions and nav > 0:
        top_holding_pct = max(p.market_value / nav for p in positions)
    else:
        top_holding_pct = 0.0

    # --- Max drawdown ---
    if historical_returns is not None:
        try:
            # Accept pd.Series, list, or any iterable
            values = list(historical_returns)
            if len(values) >= 2:
                peak = values[0]
                max_dd = 0.0
                for v in values:
                    if v > peak:
                        peak = v
                    dd = (peak - v) / peak if peak != 0 else 0.0
                    if dd > max_dd:
                        max_dd = dd
            else:
                max_dd = 0.0
        except Exception:
            max_dd = 0.0
    else:
        max_dd = 0.0

    # --- Liquidity score ---
    # Higher score = more liquid.  Based on position size distribution:
    # if no single position exceeds 20 % of NAV, score is high.
    # Formula: 1.0 - (sum of squared weights above threshold)
    if positions and nav > 0:
        weights = [p.market_value / nav for p in positions]
        # Penalise concentration: score = 1 - HHI_adjusted
        hhi_positions = sum(w * w for w in weights)
        n_pos = len(weights)
        min_hhi = 1.0 / max(n_pos, 1)
        # Normalised concentration, invert for liquidity
        concentration = (hhi_positions - min_hhi) / (1.0 - min_hhi) if n_pos > 1 else 1.0
        liquidity_score = round(max(0.0, 1.0 - concentration), 6)
    else:
        liquidity_score = 0.0

    # --- Stress loss (2.5 × VaR_95) ---
    stress_loss_pct = round(var_pct * 2.5, 6)

    return {
        "industry_concentration": round(industry_concentration, 6),
        "top_holding_pct": round(top_holding_pct, 6),
        "beta": 1.0,  # default — real calc needs market returns
        "liquidity_score": liquidity_score,
        "var_95": round(var_value, 2),
        "max_drawdown": round(max_dd, 6),
        "stress_loss_pct": stress_loss_pct,
    }
