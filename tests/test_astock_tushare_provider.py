"""Tests for TushareProvider — permission mapping without network calls."""

from unittest.mock import patch

from tradingagents.astock.data_sources.base import ProviderCapability
from tradingagents.astock.data_sources.tushare_provider import TushareProvider


def test_tushare_missing_token():
    p = TushareProvider(token="")
    status = p.probe(ProviderCapability.TRADE_CALENDAR)
    assert status.state == "missing_token"
    assert "token" in (status.permission_hint or "").lower()


def test_tushare_capabilities_defined():
    p = TushareProvider(token="dummy")
    caps = p.capabilities()
    assert ProviderCapability.VALUATION_DAILY in caps
    assert ProviderCapability.FINANCIAL_INDICATORS in caps
    assert ProviderCapability.CAPITAL_FLOW_STOCK in caps
    assert ProviderCapability.INDUSTRY_MEMBERSHIP in caps
    assert ProviderCapability.TRADE_CALENDAR in caps


def test_tushare_probe_research_missing_token():
    p = TushareProvider(token="")
    status = p.probe(ProviderCapability.VALUATION_DAILY)
    assert status.state == "missing_token"


def test_tushare_probe_capability_distinction():
    """Verify that different capabilities produce correct state mapping."""
    p = TushareProvider(token="")
    # All probes without token should return missing_token
    for cap in [ProviderCapability.VALUATION_DAILY, ProviderCapability.FINANCIAL_INDICATORS,
                ProviderCapability.CAPITAL_FLOW_STOCK, ProviderCapability.NEWS]:
        s = p.probe(cap)
        assert s.state == "missing_token", f"{cap} should be missing_token"
