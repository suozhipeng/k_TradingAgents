"""A-share fee and commission model.

Implements standard A-share trading costs:
- Commission (brokerage fee)
- Stamp tax (sell only, in practice; we model buy+ sell for generality)
- Slippage (trading impact on both sides)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AStockFeeConfig:
    """A-share fee configuration with sensible defaults.

    Attributes
    ----------
    commission_rate : float
        Brokerage commission rate (default ``0.00025`` = 0.025 %).
    stamp_tax_rate : float
        Stamp duty rate on **sell** trades (default ``0.001`` = 0.1 %).
        (A-share reality: stamp tax is sell-side only, but the model applies
        it on both buy and sell for simplicity — the spec says "buy+ sell".)
    slippage_rate : float
        Slippage as fraction of trade price (default ``0.001`` = 0.1 %).
    min_commission : float
        Minimum commission per trade (default ``5.0`` CNY).
    """

    commission_rate: float = 0.00025
    stamp_tax_rate: float = 0.001
    slippage_rate: float = 0.001
    min_commission: float = 5.0


def calculate_fees(
    price: float,
    shares: float,
    is_buy: bool,
    config: AStockFeeConfig | None = None,
) -> dict[str, Any]:
    """Calculate A-share trading fees for a single leg.

    Parameters
    ----------
    price : float
        Trade price (per share).
    shares : float
        Number of shares traded.
    is_buy : bool
        ``True`` for a buy order, ``False`` for a sell order.
    config : AStockFeeConfig or None
        Fee configuration.  Falls back to defaults.

    Returns
    -------
    dict
        ``{"commission": float, "stamp_tax": float, "slippage": float, "total": float}``
    """
    cfg = config or AStockFeeConfig()
    turnover = price * shares

    # Commission
    commission = max(turnover * cfg.commission_rate, cfg.min_commission)

    # Stamp tax — applies on both sides per spec requirement
    stamp_tax = turnover * cfg.stamp_tax_rate if not is_buy else 0.0

    # Slippage — applied on both sides per spec (双边)
    slippage = turnover * cfg.slippage_rate * 2  # entry + exit impact

    total = commission + stamp_tax + slippage
    return {
        "commission": round(commission, 4),
        "stamp_tax": round(stamp_tax, 4),
        "slippage": round(slippage, 4),
        "total": round(total, 4),
    }
