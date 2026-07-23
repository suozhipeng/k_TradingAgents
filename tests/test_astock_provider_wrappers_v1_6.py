"""Tests for V1.6.1 community provider wrappers — Mootdx, AKShare, BaoStock, Cninfo."""

from tradingagents.astock.data_sources.base import ProviderCapability
from tradingagents.astock.data_sources.cninfo_provider import CninfoProvider
from tradingagents.astock.data_sources.providers_v1_6 import (
    AkshareCapabilityProvider, BaoStockCapabilityProvider,
    MootdxCapabilityProvider, register_v1_6_1_providers,
)
from tradingagents.astock.data_sources.registry import ProviderRegistry


def test_akshare_capabilities():
    p = AkshareCapabilityProvider()
    caps = p.capabilities()
    assert ProviderCapability.MARKET_KLINE in caps
    assert ProviderCapability.VALUATION_DAILY in caps


def test_mootdx_capabilities():
    p = MootdxCapabilityProvider()
    caps = p.capabilities()
    assert ProviderCapability.MARKET_KLINE in caps
    assert ProviderCapability.INDEX_KLINE in caps
    assert ProviderCapability.VALUATION_DAILY not in caps


def test_baostock_capabilities():
    p = BaoStockCapabilityProvider()
    caps = p.capabilities()
    assert ProviderCapability.TRADE_CALENDAR in caps
    assert ProviderCapability.ADJUSTMENT_FACTOR in caps


def test_cninfo_capabilities():
    p = CninfoProvider()
    caps = p.capabilities()
    assert ProviderCapability.ANNOUNCEMENTS in caps
    assert ProviderCapability.CORPORATE_EVENTS in caps


def test_register_v1_6_1_providers():
    r = ProviderRegistry()
    register_v1_6_1_providers(r)
    assert r.get_provider("akshare") is not None
    assert r.get_provider("mootdx") is not None
    assert r.get_provider("baostock") is not None
    assert r.get_provider("cninfo") is not None


def test_cninfo_probe_returns_state_without_network():
    p = CninfoProvider()
    status = p.probe(ProviderCapability.ANNOUNCEMENTS)
    assert status.state in ("unavailable", "access_restricted", "missing_dependency",
                            "unconfigured", "manual_import_required")
    assert status.capability == ProviderCapability.ANNOUNCEMENTS


def test_akshare_probe_returns_state_without_network():
    p = AkshareCapabilityProvider()
    status = p.probe(ProviderCapability.MARKET_KLINE)
    assert status.state in ("upstream_changed", "unavailable", "missing_dependency")
    assert status.capability == ProviderCapability.MARKET_KLINE
