"""Tests for V1.7 DataFacade — single entry point for all data access."""

from tradingagents.astock.data_sources.router_v17 import DataFacade


def test_datafacade_creates_and_registers_providers():
    f = DataFacade()
    assert f.get_provider("akshare") is not None
    assert f.get_provider("mootdx") is not None
    assert f.get_provider("baostock") is not None
    assert f.get_provider("cninfo") is not None


def test_datafacade_tencent_not_registered():
    f = DataFacade()
    assert f.get_provider("tencent") is None


def test_datafacade_qmt_not_registered():
    f = DataFacade()
    assert f.get_provider("qmt") is None


def test_datafacade_iwencai_not_registered():
    f = DataFacade()
    assert f.get_provider("iwencai") is None


def test_datafacade_probe_returns_status():
    f = DataFacade()
    from tradingagents.astock.data_sources.base import ProviderCapability
    status = f.probe("mootdx", ProviderCapability.MARKET_KLINE)
    assert status.state in ("available", "unavailable", "missing_dependency",
                            "empty_response", "timeout", "parse_error")
    assert status.provider == "mootdx"


def test_datafacade_probe_unknown_provider():
    f = DataFacade()
    from tradingagents.astock.data_sources.base import ProviderCapability
    status = f.probe("nonexistent", ProviderCapability.MARKET_KLINE)
    assert status.state == "unavailable"


def test_capability_matrix_returns_all_providers():
    f = DataFacade()
    matrix = f.capability_matrix()
    assert "akshare" in matrix
    assert "mootdx" in matrix
    assert "baostock" in matrix
    assert "cninfo" in matrix
    assert len(matrix) == 4


def test_policy_summary():
    f = DataFacade()
    summary = f.get_policy_summary()
    assert summary["mode"] in ("community", "unknown")
    assert len(summary["current_stack"]) > 0
    assert summary["commercial_provider_required"] is False
