"""
Trading mode enum — defines the operational capability level of each trade endpoint.

This is the foundational type for Phase 30 live-trading readiness: every
trade-related API, schema, and page carries a ``TradingMode`` tag so the
system and its users know what level of action is possible.

Modes (strictly ordered)
------------------------
``research``       Analysis-only. No trade placement, no simulated execution.
                   Returns advisory signals and research conclusions.

``paper``          Simulated trading with virtual funds. All fills are virtual,
                   all positions are paper-only. Trades carry ``actionable=false``
                   and ``execution_signal="ResearchOnly"``.

``managed``        Semi-automated with human-in-the-loop confirmation. The
                   system proposes trades; a human must confirm each one.
                   Real orders are placed only after confirmation.

``live-ready``     Fully automated real-money trading. Every safety gate
                   (risk, kill-switch, reconciliation) is active. This mode
                   must not be enabled unless explicitly configured.

Usage
-----
    from tradingagents.astock.trading_mode import TradingMode, ExecutionCapability

    mode = TradingMode.PAPER
    assert mode.can_place_order is False   # paper cannot place real orders
    assert mode.requires_confirmation is False
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class TradingMode(str, Enum):
    """Operational capability level of a trading endpoint.

    Enum values are lowercase strings for JSON serialisation.
    """

    RESEARCH = "research"
    PAPER = "paper"
    MANAGED = "managed"
    LIVE_READY = "live-ready"

    # ── computed properties ───────────────────────────────────────────

    @property
    def can_place_order(self) -> bool:
        """Whether this mode can initiate order placement."""
        return self in (TradingMode.PAPER, TradingMode.MANAGED, TradingMode.LIVE_READY)

    @property
    def can_execute(self) -> bool:
        """Whether this mode can execute actual fills."""
        return self is TradingMode.LIVE_READY

    @property
    def requires_confirmation(self) -> bool:
        """Whether a human confirmation gate is required before execution."""
        return self is TradingMode.MANAGED

    @property
    def is_simulated(self) -> bool:
        """Whether this mode uses virtual execution (no real fills)."""
        return self in (TradingMode.RESEARCH, TradingMode.PAPER)

    @property
    def order_status_supported(self) -> list[str]:
        """Order status values applicable in this mode."""
        base = ["created", "submitted", "cancelled", "rejected", "error"]
        if self in (TradingMode.PAPER, TradingMode.MANAGED, TradingMode.LIVE_READY):
            base.extend(["confirmed", "partial_filled", "filled", "expired"])
        return base

    @classmethod
    def from_string(cls, value: str) -> Optional[TradingMode]:
        """Safe parser — returns ``None`` for unrecognised values."""
        try:
            return cls(value.lower().strip())
        except (ValueError, AttributeError):
            return None


class ExecutionCapability:
    """Describes what a trade endpoint is capable of at runtime.

    This schema is designed to be included in every trade API response
    ``meta`` block so the frontend can adapt its UI accordingly.

    Parameters
    ----------
    mode : TradingMode
        The operational mode of this endpoint.
    can_place_order : bool
        Whether the endpoint can initiate order placement.
    can_query : bool
        Whether the endpoint can return state/quote data.
    can_execute : bool
        Whether the endpoint can execute fills.
    requires_confirmation : bool
        Whether a human confirmation is required.
    is_mock : bool
        Whether the data source is a mock/stub.
    provider : str, optional
        Name of the upstream provider (e.g. ``"eastmoney"``, ``"qmt_mock"``).
    """

    def __init__(
        self,
        mode: TradingMode,
        *,
        can_place_order: bool = False,
        can_query: bool = True,
        can_execute: bool = False,
        requires_confirmation: bool = False,
        is_mock: bool = False,
        provider: str | None = None,
    ) -> None:
        self.mode = mode
        self.can_place_order = can_place_order
        self.can_query = can_query
        self.can_execute = can_execute
        self.requires_confirmation = requires_confirmation
        self.is_mock = is_mock
        self._provider = provider

    @property
    def provider(self) -> str:
        return self._provider or f"{self.mode.value}_mode"

    def to_dict(self) -> dict:
        """Serialise to a dict suitable for JSON ``meta`` blocks."""
        return {
            "capability": self.mode.value,
            "can_place_order": self.can_place_order,
            "can_query": self.can_query,
            "can_execute": self.can_execute,
            "requires_confirmation": self.requires_confirmation,
            "is_mock": self.is_mock,
            "provider": self.provider,
        }

    # ── Pre-built factory methods ─────────────────────────────────────

    @classmethod
    def research(cls, *, provider: str | None = None) -> ExecutionCapability:
        """Pre-built research-only capability."""
        return cls(
            TradingMode.RESEARCH,
            can_place_order=False,
            can_query=True,
            can_execute=False,
            requires_confirmation=False,
            is_mock=False,
            provider=provider or "research_analysis",
        )

    @classmethod
    def paper(cls, *, provider: str | None = None) -> ExecutionCapability:
        """Pre-built paper-trading capability."""
        return cls(
            TradingMode.PAPER,
            can_place_order=True,
            can_query=True,
            can_execute=False,
            requires_confirmation=False,
            is_mock=False,
            provider=provider or "paper_simulator",
        )

    @classmethod
    def managed(cls, *, provider: str | None = None) -> ExecutionCapability:
        """Pre-built managed (human-confirmed) capability."""
        return cls(
            TradingMode.MANAGED,
            can_place_order=True,
            can_query=True,
            can_execute=False,
            requires_confirmation=True,
            is_mock=False,
            provider=provider or "managed_gateway",
        )

    @classmethod
    def live_ready(cls, *, provider: str | None = None) -> ExecutionCapability:
        """Pre-built live-ready (full execution) capability."""
        return cls(
            TradingMode.LIVE_READY,
            can_place_order=True,
            can_query=True,
            can_execute=True,
            requires_confirmation=False,
            is_mock=False,
            provider=provider or "live_broker",
        )

    @classmethod
    def mock(cls, *, mode: str = "research", provider: str | None = None) -> ExecutionCapability:
        """Pre-built mock capability for testing / placeholder endpoints."""
        base_mode = TradingMode.from_string(mode) or TradingMode.RESEARCH
        return cls(
            base_mode,
            can_place_order=False,
            can_query=True,
            can_execute=False,
            requires_confirmation=False,
            is_mock=True,
            provider=provider or "mock_stub",
        )


__all__ = [
    "TradingMode",
    "ExecutionCapability",
]
