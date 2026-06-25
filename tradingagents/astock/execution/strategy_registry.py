"""Strategy registry — maintain a discoverable catalog of all available strategies.

Phase 32 replaces the implicit import-based registration model
(``execution/__init__.py`` ``__all__``) with an explicit ``StrategyRegistry``
that every strategy class can self-register into.

Design rationale
----------------
- A single ``StrategyRegistry`` dict indexed by ``strategy_name``.
- Each entry carries metadata: category, default params, search space, suitability.
- The registry is populated by a ``register()`` function called from each
  strategy module (or aggregated in a registry module).

This is a **Phase 32 definition** — the actual registration calls will be
added to each strategy file in a follow-up phase. For now the schema exists
and the registry dict is populated from the existing ``DEFAULT_SEARCH_SPACES``
in ``optimizer.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Registry entry schema ──────────────────────────────────────────────


@dataclass
class StrategyRegistryEntry:
    """Metadata for a single strategy in the lab registry.

    Attributes
    ----------
    name : str
        Canonical strategy name (e.g. ``"MovingAverageTrend"``).
    category : str
        Strategy category (``"trend"``, ``"mean_reversion"``,
        ``"momentum"``, ``"volatility"``, ``"option"``, ``"grid"``).
    description : str
        One-line description.
    params_schema : dict[str, Any]
        Mapping from parameter name → default value (for frontend form).
    search_space : dict[str, list[Any]] or None
        Optimizer search space (parameter name → candidate values).
    suitability : list[str]
        Market conditions the strategy is suitable for
        (``"trending"``, ``"ranging"``, ``"volatile"``, ``"all"``).
    """

    name: str
    category: str = "unsorted"
    description: str = ""
    params_schema: dict[str, Any] = field(default_factory=dict)
    search_space: dict[str, list[Any]] | None = None
    suitability: list[str] = field(default_factory=lambda: ["all"])


# ── Registry dict ──────────────────────────────────────────────────────


_STRATEGY_REGISTRY: dict[str, StrategyRegistryEntry] = {}


def register(entry: StrategyRegistryEntry) -> None:
    """Register a strategy in the global lab registry."""
    _STRATEGY_REGISTRY[entry.name] = entry


def get_registry() -> dict[str, StrategyRegistryEntry]:
    """Return a copy of the current registry."""
    return dict(_STRATEGY_REGISTRY)


def get_strategy(name: str) -> StrategyRegistryEntry | None:
    """Look up a registered strategy by canonical name."""
    return _STRATEGY_REGISTRY.get(name)


def list_strategies(*, category: str | None = None) -> list[StrategyRegistryEntry]:
    """List registered strategies, optionally filtered by category."""
    if category is None:
        return list(_STRATEGY_REGISTRY.values())
    return [e for e in _STRATEGY_REGISTRY.values() if e.category == category]


# ── Pre-populate from existing strategies ──────────────────────────────

import logging

from .optimizer import DEFAULT_SEARCH_SPACES

_log = logging.getLogger(__name__)

# Map strategy name → category
_CATEGORY_MAP: dict[str, str] = {
    "MovingAverageTrend": "trend",
    "BullTrend": "trend",
    "ValueAverage": "valuation",
    "MeanReversion": "mean_reversion",
    "RSIRange": "mean_reversion",
    "DefensiveMomentum": "momentum",
    "PutWrite": "option",
    "MACDTrend": "trend",
    "BollingerBandsReversion": "volatility",
    "GridTrading": "grid",
}

for name, category in _CATEGORY_MAP.items():
    search_space = DEFAULT_SEARCH_SPACES.get(name)
    register(
        StrategyRegistryEntry(
            name=name,
            category=category,
            description=f"{name} strategy — see ``strategy_base.py`` for details.",
            search_space=search_space,
        )
    )

_log.debug("Strategy registry populated with %d entries", len(_STRATEGY_REGISTRY))

__all__ = [
    "StrategyRegistryEntry",
    "register",
    "get_registry",
    "get_strategy",
    "list_strategies",
    "_STRATEGY_REGISTRY",
]
