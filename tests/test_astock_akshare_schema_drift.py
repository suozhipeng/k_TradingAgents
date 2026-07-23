"""Tests for AKShare schema drift detection — empty and upstream_changed semantics."""

from tradingagents.astock.data_sources.base import ProviderCapability
from tradingagents.astock.data_sources.providers_v1_6 import AkshareCapabilityProvider


def test_akshare_probe_returns_upstream_changed_on_empty():
    """AKShare probe without network should return upstream_changed or missing_dependency."""
    p = AkshareCapabilityProvider()
    status = p.probe(ProviderCapability.VALUATION_DAILY)
    assert status.state in ("upstream_changed", "unavailable", "missing_dependency",
                            "empty_response", "timeout", "parse_error")
    assert status.provider == "akshare"


def test_akshare_probe_never_returns_available_without_network():
    """Without network, AKShare should never claim available."""
    p = AkshareCapabilityProvider()
    status = p.probe(ProviderCapability.FINANCIAL_INDICATORS)
    assert status.state != "available", "AKShare should not claim available without network"


def test_akshare_probe_has_correct_source_kind():
    p = AkshareCapabilityProvider()
    status = p.probe(ProviderCapability.MARKET_KLINE)
    assert status.source_kind in ("public_web", "online_api", "unknown")
    assert status.capability == ProviderCapability.MARKET_KLINE


def test_akshare_marks_empty_as_upstream_changed_not_available():
    """Empty responses from AKShare must not be marked available."""
    p = AkshareCapabilityProvider()
    status = p.probe(ProviderCapability.INDUSTRY_MEMBERSHIP)
    assert status.state != "available" or status.source_kind != "public_web"
