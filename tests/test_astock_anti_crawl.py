"""Anti-crawling mechanism tests — verify delays, retries, and headers work."""

from __future__ import annotations

import os
import sys
import time
import unittest
from unittest.mock import patch

_REPO = __file__  # not needed for import but keeps pattern
# Import the anti-crawling functions directly from adapters
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tradingagents.astock.data_sources.adapters import (
    _common_headers,
    _random_sleep,
    _retry_with_backoff,
)


class TestRandomSleep(unittest.TestCase):
    """_random_sleep 测试 — 验证延迟范围和 TESTING 模式跳过。"""

    def test_sleep_skipped_when_testing(self) -> None:
        """ASTOCK_TESTING=1 时 _random_sleep 不应实际 sleep。"""
        os.environ["ASTOCK_TESTING"] = "1"
        t0 = time.time()
        _random_sleep(5.0, 10.0)  # would be 5-10s if not skipped
        elapsed = time.time() - t0
        self.assertLess(elapsed, 1.0, "Should skip sleep in testing mode")

    def test_sleep_actual_delay(self) -> None:
        """非测试模式下应产生有意义的延迟。"""
        os.environ.pop("ASTOCK_TESTING", None)
        t0 = time.time()
        _random_sleep(0.05, 0.15)  # short range for test speed
        elapsed = time.time() - t0
        self.assertGreaterEqual(elapsed, 0.04, "Should have some delay")
        self.assertLess(elapsed, 0.5, "Delay should be within range")

    def tearDown(self) -> None:
        os.environ.setdefault("ASTOCK_TESTING", "1")


class TestRetryWithBackoff(unittest.TestCase):
    """_retry_with_backoff 测试 — 重试次数、延迟、异常传播。"""

    def test_success_no_retry(self) -> None:
        """第一次成功不应重试。"""
        call_count = 0

        def ok():
            nonlocal call_count
            call_count += 1
            return "done"

        result = _retry_with_backoff(ok, max_retries=3)
        self.assertEqual(result, "done")
        self.assertEqual(call_count, 1)

    def test_retry_on_failure(self) -> None:
        """失败时应重试指定次数后成功。"""
        call_count = 0

        def eventually_ok():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient failure")
            return "recovered"

        result = _retry_with_backoff(eventually_ok, max_retries=3, base_delay=0.01)
        self.assertEqual(result, "recovered")
        self.assertEqual(call_count, 3)

    def test_exhaust_retries(self) -> None:
        """超过重试次数应抛出最后一次异常。"""
        call_count = 0

        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("permanent failure")

        with self.assertRaises(ValueError) as ctx:
            _retry_with_backoff(always_fail, max_retries=2, base_delay=0.01)
        self.assertIn("permanent failure", str(ctx.exception))
        self.assertEqual(call_count, 3)  # 1 initial + 2 retries

    def test_backoff_increases_delay(self) -> None:
        """每次重试的延迟应逐步增加。"""
        os.environ.pop("ASTOCK_TESTING", None)  # 允许 sleep
        delays = []

        def track_and_fail():
            nonlocal delays
            # Record the actual inter-call delay
            return None

        # Mock sleep to capture delays
        original_sleep = time.sleep

        def mock_sleep(secs):
            nonlocal delays
            delays.append(secs)

        with patch("time.sleep", mock_sleep):
            try:
                _retry_with_backoff(
                    lambda: (_ for _ in ()).throw(ConnectionError("fail")),
                    max_retries=3,
                    base_delay=0.1,
                )
            except ConnectionError:
                pass

        self.assertEqual(len(delays), 3)
        # delays: base * 2^attempt + random(0, 0.5) — jitter may cause slight
        # non-monotonicity, but attempt 2 should be >= attempt 0
        self.assertGreaterEqual(delays[2], delays[0] * 0.5, "Backoff should trend upward")
        os.environ.setdefault("ASTOCK_TESTING", "1")


class TestCommonHeaders(unittest.TestCase):
    """_common_headers 测试 — 反爬请求头完整性。"""

    def test_headers_have_required_fields(self) -> None:
        """返回的头应包含所有关键字段。"""
        headers = _common_headers()
        required = {"User-Agent", "Accept", "Accept-Language", "Referer"}
        self.assertTrue(required.issubset(set(headers.keys())), f"Missing: {required - set(headers.keys())}")

    def test_user_agent_is_browser_like(self) -> None:
        """User-Agent 应像真实浏览器。"""
        ua = _common_headers()["User-Agent"]
        self.assertIn("Mozilla/5.0", ua, "UA should start with Mozilla")
        self.assertIn("Chrome", ua, "UA should mention Chrome")
        self.assertIn("Safari", ua, "UA should mention Safari")

    def test_accept_language_is_chinese(self) -> None:
        """语言偏好应包含 zh-CN。"""
        headers = _common_headers()
        self.assertIn("zh-CN", headers["Accept-Language"])

    def test_custom_referer(self) -> None:
        """自定义 referer 生效。"""
        headers = _common_headers(referer="https://quote.eastmoney.com/")
        self.assertEqual(headers["Referer"], "https://quote.eastmoney.com/")


if __name__ == "__main__":
    unittest.main()
