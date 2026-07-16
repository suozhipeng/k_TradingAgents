"""Infrastructure primitives: EventBus, KillSwitch, and StrategyRegistry."""

from __future__ import annotations

# Backward-compatible re-exports
from tradingagents.astock.execution.infrastructure.event_bus import EventBus  # noqa: F401
from tradingagents.astock.execution.infrastructure.kill_switch import KillSwitch, kill_switch  # noqa: F401
from tradingagents.astock.execution.infrastructure.registry import (  # noqa: F401
    StrategyRegistryEntry,
    get_registry,
    list_strategies,
    register,
    get_strategy,
)

__all__ = [
    "EventBus",
    "KillSwitch",
    "StrategyRegistryEntry",
    "get_registry",
    "get_strategy",
    "kill_switch",
    "list_strategies",
    "register",
]
