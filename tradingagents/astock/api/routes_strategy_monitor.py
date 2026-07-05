"""Strategy monitor API — FR-19.

Provides a status overview of all registered strategies.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Response, jsonify

logger = logging.getLogger(__name__)

bp = Blueprint("strategy_monitor", __name__)

_STRATEGY_REGISTRY: dict[str, type] | None = None


def _get_registry() -> dict[str, type]:
    """Lazy-load the strategy registry."""
    global _STRATEGY_REGISTRY
    if _STRATEGY_REGISTRY is not None:
        return _STRATEGY_REGISTRY
    from tradingagents.astock.execution.strategy_base import (
        BollingerBandsReversionStrategy,
        BullTrendStrategy,
        DefensiveMomentumStrategy,
        GridTradingStrategy,
        MACDTrendStrategy,
        MeanReversionStrategy,
        MomentumRotationStrategy,
        MovingAverageTrendStrategy,
        PutWriteStrategy,
        RSIRangeStrategy,
        StockFlow,
        ValueAverageStrategy,
    )
    _STRATEGY_REGISTRY = {
        "MovingAverageTrend": MovingAverageTrendStrategy,
        "BullTrend": BullTrendStrategy,
        "ValueAverage": ValueAverageStrategy,
        "MeanReversion": MeanReversionStrategy,
        "RSIRange": RSIRangeStrategy,
        "DefensiveMomentum": DefensiveMomentumStrategy,
        "PutWrite": PutWriteStrategy,
        "MACDTrend": MACDTrendStrategy,
        "BollingerBands": BollingerBandsReversionStrategy,
        "GridTrading": GridTradingStrategy,
        "MomentumRotation": MomentumRotationStrategy,
        "StockFlow": StockFlow,
    }
    return _STRATEGY_REGISTRY


# ---------------------------------------------------------------------------
# GET /api/v1/strategies/status
# ---------------------------------------------------------------------------


@bp.route("/strategies/status")
def list_strategies() -> tuple[Response, int]:
    """Return all registered strategies with metadata."""
    try:
        registry = _get_registry()
        strategies = []
        for name, cls in registry.items():
            doc = (cls.__doc__ or "").strip().split("\n")[0] if cls.__doc__ else ""
            strategies.append({
                "name": name,
                "display_name": doc[:80] if doc else name,
                "doc_preview": doc[:120],
                "module": cls.__module__,
            })
        return jsonify({
            "strategies": strategies,
            "total": len(strategies),
            "status": "ok",
        }), 200
    except Exception as exc:
        return jsonify({"error": str(exc), "status": 500, "strategies": [], "total": 0}), 500


__all__ = ["bp"]
