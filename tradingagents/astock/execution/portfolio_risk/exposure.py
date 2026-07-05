"""Industry exposure analysis for a portfolio.

Provides ``calculate_industry_exposure`` which maps A-share symbols to
industry buckets and returns allocation percentages.
"""

from __future__ import annotations

from typing import Dict, List

from tradingagents.astock.schemas.trading_execution import Position


def _infer_industry(symbol: str) -> str:
    """Map A-share stock symbol to an industry bucket."""
    sym = symbol.strip()
    if sym.startswith("600"):
        return "金融"
    if sym.startswith("000"):
        return "主板"
    if sym.startswith("300"):
        return "创业板"
    if sym.startswith("688"):
        return "科创板"
    return "其他"


def calculate_industry_exposure(
    positions: List[Position],
) -> Dict[str, float]:
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

    industry_map: Dict[str, float] = {}

    for p in positions:
        industry = _infer_industry(p.symbol)
        industry_map[industry] = industry_map.get(industry, 0.0) + p.market_value

    return {ind: round(val / total_value, 6) for ind, val in industry_map.items()}
