"""Provider Capability enum, status model, and base class (V1.6.1 Community Stack)."""

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
    ADJUSTMENT_FACTOR = "adjustment_factor"
    FINANCIAL_STATEMENTS = "financial_statements"
    FINANCIAL_INDICATORS = "financial_indicators"
    VALUATION_DAILY = "valuation_daily"
    CAPITAL_FLOW_STOCK = "capital_flow_stock"
    CAPITAL_FLOW_SECTOR = "capital_flow_sector"
    INDUSTRY_MEMBERSHIP = "industry_membership"
    CONCEPT_MEMBERSHIP = "concept_membership"
    NEWS = "news"
    ANNOUNCEMENTS = "announcements"
    CORPORATE_EVENTS = "corporate_events"
    LIMIT_UP_DOWN = "limit_up_down"


# V1.6.1 Community provider states (no commercial token states)
PROVIDER_STATES = frozenset({
    "available", "degraded", "stale", "unconfigured",
    "missing_dependency", "access_restricted",
    "timeout", "rate_limited", "upstream_changed",
    "parse_error", "empty_response", "manual_import_required",
    "unavailable",
})


@dataclass(frozen=True)
class CapabilityStatus:
    """Immutable result of a single Capability probe."""
    provider: str
    capability: ProviderCapability
    state: str                         # one of PROVIDER_STATES
    checked_at: str                    # ISO timestamp
    latency_ms: int | None = None
    rows: int | None = None
    source_kind: str = "unknown"       # online_api | public_web | local_import | derived | cache
    degradation_reason: str | None = None
    error_code: str | None = None
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
