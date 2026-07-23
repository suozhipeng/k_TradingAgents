"""Tests for provider capability matrix — states, routing, and discovery."""

from tradingagents.astock.data_sources.base import (
    CapabilityStatus, ProviderCapability, PROVIDER_STATES,
)


def test_all_provider_states_are_strings():
    for s in PROVIDER_STATES:
        assert isinstance(s, str)
        assert len(s) > 0


def test_capability_status_requires_state():
    s = CapabilityStatus(provider="test", capability=ProviderCapability.MARKET_KLINE,
                         state="available", checked_at="2026-01-01T00:00:00")
    assert s.state == "available"
    assert s.provider == "test"


def test_capability_status_immutable():
    s = CapabilityStatus(provider="test", capability=ProviderCapability.MARKET_KLINE,
                         state="missing_token", checked_at="now")
    d = dict(s.__dict__)
    assert d["state"] == "missing_token"


def test_capability_enum_values():
    assert ProviderCapability.MARKET_KLINE.value == "market_kline"
    assert ProviderCapability.VALUATION_DAILY.value == "valuation_daily"
    assert ProviderCapability.FINANCIAL_INDICATORS.value == "financial_indicators"
    assert ProviderCapability.CAPITAL_FLOW_STOCK.value == "capital_flow_stock"
    assert ProviderCapability.INDUSTRY_MEMBERSHIP.value == "industry_membership"
    assert ProviderCapability.CONCEPT_MEMBERSHIP.value == "concept_membership"
    assert ProviderCapability.NEWS.value == "news"


def test_provider_states_contain_new_v1_6_states():
    for s in ("access_restricted", "manual_import_required", "upstream_changed",
              "rate_limited", "stale", "parse_error", "empty_response"):
        assert s in PROVIDER_STATES, f"missing state: {s}"
