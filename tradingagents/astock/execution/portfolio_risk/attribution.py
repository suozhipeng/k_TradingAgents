"""Brinson-style performance attribution.

Provides ``calculate_attribution`` which decomposes excess portfolio
return into selection and timing effects.
"""

from __future__ import annotations

from typing import Any, Dict, List

from tradingagents.astock.schemas.trading_execution import Position
from .exposure import _infer_industry


def calculate_attribution(
    positions: List[Position],
    benchmark_return: float = 0.0,
) -> Dict[str, Any]:
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
    sectors: Dict[str, Dict[str, float]] = {}
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
    n_sectors = len(sectors)
    benchmark_sector_weight = 1.0 / max(n_sectors, 1)

    selection_effect = 0.0
    timing_effect = 0.0

    for s in sectors.values():
        timing_effect += (s["weight"] - benchmark_sector_weight) * benchmark_return
        selection_effect += benchmark_sector_weight * (s["return"] - benchmark_return)

    # Cost impact
    total_fees_est = sum(
        abs(p.pnl) * 0.0003 for p in positions  # ~3 bps implied cost
    )
    cost_impact = total_fees_est / nav if nav > 0 else 0.0

    # Slippage impact
    largest_weight = max((p.market_value / nav for p in positions), default=0.0)
    slippage_impact = largest_weight * 0.001  # 10 bps on largest position

    # Residual
    excess = portfolio_return - benchmark_return
    residual = excess - selection_effect - timing_effect - cost_impact - slippage_impact

    return {
        "benchmark_return": round(benchmark_return, 6),
        "selection_effect": round(selection_effect, 6),
        "timing_effect": round(timing_effect, 6),
        "cost_impact": round(cost_impact, 6),
        "slippage_impact": round(slippage_impact, 6),
        "residual": round(residual, 6),
    }
