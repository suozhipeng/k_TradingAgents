"""Dedicated tests for CninfoProvider."""

from tradingagents.astock.data_sources.base import ProviderCapability
from tradingagents.astock.data_sources.cninfo_provider import CninfoProvider


def test_cninfo_provider_has_correct_name():
    p = CninfoProvider()
    assert p.name == "cninfo"


def test_cninfo_capabilities_correct():
    p = CninfoProvider()
    caps = p.capabilities()
    assert ProviderCapability.ANNOUNCEMENTS in caps
    assert ProviderCapability.CORPORATE_EVENTS in caps
    assert ProviderCapability.MARKET_KLINE not in caps


def test_cninfo_probe_unconfigured_local_dir():
    """Without the local dir, probe should return appropriate state."""
    p = CninfoProvider(local_dir="/nonexistent/cninfo_dir")
    status = p.probe(ProviderCapability.ANNOUNCEMENTS)
    assert status.state in ("unconfigured", "missing_dependency", "unavailable")
    assert status.capability == ProviderCapability.ANNOUNCEMENTS


def test_cninfo_probe_unknown_capability():
    p = CninfoProvider()
    status = p.probe(ProviderCapability.MARKET_KLINE)
    assert status.state == "unavailable"
