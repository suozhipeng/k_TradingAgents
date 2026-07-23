"""Tests for provider fallback semantics and field-level lineage."""

import duckdb

from tradingagents.astock.data_sources.base import CapabilityStatus, ProviderCapability
from tradingagents.astock.data_sources.registry import ProviderRegistry
from tradingagents.astock.store.provider_lineage import record_field_lineage


class _MockProvider:
    name = "mock_test"
    def capabilities(self):
        return {ProviderCapability.MARKET_KLINE}
    def probe(self, cap):
        return CapabilityStatus(provider=self.name, capability=cap, state="available", checked_at="now")
    def fetch(self, cap, **kw):
        return []


class _BrokenProvider:
    name = "broken_test"
    def capabilities(self):
        return {ProviderCapability.MARKET_KLINE, ProviderCapability.VALUATION_DAILY}
    def probe(self, cap):
        if cap == ProviderCapability.MARKET_KLINE:
            return CapabilityStatus(provider=self.name, capability=cap, state="available", checked_at="now")
        return CapabilityStatus(provider=self.name, capability=cap, state="missing_token", checked_at="now",
                                permission_hint="token not set")
    def fetch(self, cap, **kw):
        return []


def test_registry_routes_to_available():
    r = ProviderRegistry()
    r.register("primary", _MockProvider())
    name, status = r.best_available(ProviderCapability.MARKET_KLINE, {
        "market_kline": {"primary": "primary", "fallback": ["missing"]},
    })
    assert name == "primary"
    assert status.state == "available"


def test_registry_fallback_when_primary_unavailable():
    r = ProviderRegistry()
    # Register a provider without the capability
    r.register("broken", _BrokenProvider())
    # Broken has MARKET_KLINE available but VALUATION_DAILY missing_token
    name, status = r.best_available(ProviderCapability.MARKET_KLINE, {
        "market_kline": {"primary": "broken", "fallback": []},
    })
    assert name == "broken"
    assert status.state == "available"


def test_field_lineage_records():
    conn = duckdb.connect(":memory:")
    lid = record_field_lineage(
        conn,
        provider="tushare", provider_api="daily_basic", upstream_source="tushare",
        source_symbol="600519.SH", source_field="pe_ttm", normalized_field="pe_ttm",
        as_of="2026-07-22", quality_tag="normal",
    )
    assert lid.startswith("l_")
    rows = conn.execute("SELECT COUNT(*) FROM provider_field_lineage").fetchone()[0]
    assert rows == 1


def test_field_lineage_idempotent():
    conn = duckdb.connect(":memory:")
    lid1 = record_field_lineage(conn, provider="tushare", provider_api="daily_basic",
                                 upstream_source="tushare", source_symbol="A", source_field="pb",
                                 normalized_field="pb", as_of="2026-07-22")
    lid2 = record_field_lineage(conn, provider="tushare", provider_api="daily_basic",
                                 upstream_source="tushare", source_symbol="A", source_field="pb",
                                 normalized_field="pb", as_of="2026-07-22")
    assert lid1 == lid2
    assert conn.execute("SELECT COUNT(*) FROM provider_field_lineage").fetchone()[0] == 1
