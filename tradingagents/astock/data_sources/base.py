"""Provider Capability enum, status model, and base class."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ProviderCapability(StrEnum):
    """Every measurable financial data capability a provider can offer."""
    MARKET_KLINE = "market_kline"
    INDEX_KLINE = "index_kline"
    REALTIME_QUOTE = "realtime_quote"
    TRADE_CALENDAR = "trade_calendar"
    SECURITY_MASTER = "security_master"
    FINANCIAL_STATEMENTS = "financial_statements"
    FINANCIAL_INDICATORS = "financial_indicators"
    VALUATION_DAILY = "valuation_daily"
    CAPITAL_FLOW_STOCK = "capital_flow_stock"
    CAPITAL_FLOW_SECTOR = "capital_flow_sector"
    INDUSTRY_MEMBERSHIP = "industry_membership"
    CONCEPT_MEMBERSHIP = "concept_membership"
    NEWS = "news"
    ANNOUNCEMENTS = "announcements"
    LIMIT_UP_DOWN = "limit_up_down"


# Unified status values from V1.6 §31.3
PROVIDER_STATES = frozenset({
    "available", "degraded", "stale", "unconfigured",
    "missing_dependency", "missing_token", "permission_required",
    "insufficient_points", "timeout", "rate_limited",
    "upstream_changed", "parse_error", "empty_response", "unavailable",
})


@dataclass(frozen=True)
class CapabilityStatus:
    """Immutable result of a single Capability probe."""
    provider: str
    capability: ProviderCapability
    state: str                         # one of PROVIDER_STATES
    checked_at: str                    # ISO timestamp
    latency_ms: int | None = None
    permission_hint: str | None = None  # e.g. "requires 2000 points" / "needs major_news permission"
    error_code: str | None = None
    detail_rows: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


class FinancialDataProvider:
    """Minimal interface every data provider must implement."""

    name: str

    def capabilities(self) -> set[ProviderCapability]:
        raise NotImplementedError

    def probe(self, capability: ProviderCapability) -> CapabilityStatus:
        raise NotImplementedError

    def fetch(self, capability: ProviderCapability, **kwargs: Any):
        raise NotImplementedError
