"""PR-3: 验证 Provider 健康探测的异常隔离 — 单个适配器故障不影响其他。"""
import pytest

from tradingagents.astock.api.routes_data_health import _probe_adapter


def test_probe_available_adapter_returns_ok():
    """一个正常适配器返回 available=True."""
    healthy_class = type("HealthyAdapter", (), {"health_check": staticmethod(lambda: True)})
    result = _probe_adapter("healthy", healthy_class)
    assert result["available"] is True
    assert result["name"] == "healthy"
    assert result["error"] is None


def test_probe_unavailable_adapter_returns_false():
    """一个不可用的适配器返回 available=False 且不影响其他 probe."""

    class BrokenAdapter:
        @staticmethod
        def health_check():
            raise RuntimeError("adapter is broken")

    result = _probe_adapter("broken", BrokenAdapter)
    assert result["available"] is False
    assert "broken" in result["error"]


def test_probe_without_health_check_falls_back_to_get_kline():
    """没有 health_check 方法时 fallback 到 get_kline."""

    class AdapterWithKline:
        def get_kline(self, symbol: str):
            return {"symbol": symbol, "bars": []}

    result = _probe_adapter("kline_ok", AdapterWithKline)
    assert result["available"] is True


def test_probe_class_without_health_check_or_get_kline():
    """既没有 health_check 也没有 get_kline 时上报错误."""

    class EmptyAdapter:
        pass

    result = _probe_adapter("empty", EmptyAdapter)
    assert result["error"] is not None


def test_probe_no_mock_returns_false():
    """没有 mock 标注的适配器上报 mock=False."""

    class CleanAdapter:
        pass

    result = _probe_adapter("no_mock", CleanAdapter)
    assert result["mock"] is False
