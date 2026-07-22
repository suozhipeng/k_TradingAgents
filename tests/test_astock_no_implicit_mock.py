"""PR-3: 验证在 local-release 模式下 Mock 数据被禁止 — 即使 ASTOCK_MOCK_DATA_ENABLED=true。"""
import os
import pytest

from tradingagents.astock.api._helpers import mock_data_enabled


class TestMockDisabledUnderLocalRelease:

    def teardown_method(self):
        """Cleanup environment after each test."""
        for key in ("ASTOCK_LOCAL_RELEASE", "ASTOCK_MOCK_DATA_ENABLED"):
            os.environ.pop(key, None)

    def test_mock_returns_false_when_local_release_active(self):
        """local-release=true 且 mock=true 时, mock_data_enabled() 应返回 False."""
        os.environ["ASTOCK_LOCAL_RELEASE"] = "true"
        os.environ["ASTOCK_MOCK_DATA_ENABLED"] = "true"
        assert mock_data_enabled() is False

    def test_mock_works_normally_without_local_release(self):
        """没有 local-release 时, mock_data_enabled() 服从环境变量."""
        os.environ.pop("ASTOCK_LOCAL_RELEASE", None)
        os.environ["ASTOCK_MOCK_DATA_ENABLED"] = "true"
        assert mock_data_enabled() is True

    def test_mock_off_when_local_release_and_mock_off(self):
        """local-release=true 且 mock=false 时返回 False."""
        os.environ["ASTOCK_LOCAL_RELEASE"] = "true"
        os.environ["ASTOCK_MOCK_DATA_ENABLED"] = "false"
        assert mock_data_enabled() is False

    def test_returns_false_when_no_vars_set(self):
        """没有任何变量时默认为 False."""
        os.environ.pop("ASTOCK_LOCAL_RELEASE", None)
        os.environ.pop("ASTOCK_MOCK_DATA_ENABLED", None)
        assert mock_data_enabled() is False
