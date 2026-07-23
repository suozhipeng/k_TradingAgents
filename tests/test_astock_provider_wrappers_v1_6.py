"""Tests for V1.6 provider wrappers — capability registration and upstream_changed."""

from tradingagents.astock.data_sources.providers_v1_6 import (
    AkshareCapabilityProvider,
    BaoStockCapabilityProvider,
    MootdxCapabilityProvider,
    register_v1_6_providers,
)
from tradingagents.astock.data_sources.base import ProviderCapability
from tradingagents.astock.data_sources.registry import ProviderRegistry


def test_akshare_capability_wrapper_has_expected_caps():
    p = AkshareCapabilityProvider()
    caps = p.capabilities()
    assert ProviderCapability.MARKET_KLINE in caps
    assert ProviderCapability.VALUATION_DAILY in caps


def test_mootdx_capability_wrapper():
    p = MootdxCapabilityProvider()
    caps = p.capabilities()
    assert ProviderCapability.MARKET_KLINE in caps
    assert ProviderCapability.INDEX_KLINE in caps
    assert ProviderCapability.VALUATION_DAILY not in caps


def test_baostock_capability_wrapper():
    p = BaoStockCapabilityProvider()
    caps = p.capabilities()
    assert ProviderCapability.TRADE_CALENDAR in caps
    assert ProviderCapability.CAPITAL_FLOW_STOCK not in caps


def test_register_v1_6_providers():
    r = ProviderRegistry()
    register_v1_6_providers(r)
    assert r.get_provider("tushare") is not None
    assert r.get_provider("akshare") is not None
    assert r.get_provider("mootdx") is not None
    assert r.get_provider("baostock") is not None


def test_akshare_probe_returns_state_without_network():
    """AKShare probe should return a state even without actual network/API."""
    p = AkshareCapabilityProvider()
    status = p.probe(ProviderCapability.INDEX_KLINE)
    # Without network this could be any failure state — just check it has one
    assert status.state in ("upstream_changed", "unavailable", "missing_dependency")
    assert status.capability == ProviderCapability.INDEX_KLINE
