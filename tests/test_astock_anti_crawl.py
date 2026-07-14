"""Anti-crawling mechanism tests — verify delays, retries, and headers work."""

from __future__ import annotations

import os
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
import threading
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import pandas as pd

_REPO = __file__  # not needed for import but keeps pattern
# Import the anti-crawling functions directly from adapters
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tradingagents.astock.data_sources.adapters import (
    _common_headers,
    _random_sleep,
    _retry_with_backoff,
)
from tradingagents.astock.data_sources.request_governor import (
    ProviderRequestGovernor,
    ProviderRequestTimeoutError,
)
from tradingagents.astock.store.loader import BatchLoader, run_with_timeout_retries


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


class TestProviderRequestGovernor(unittest.TestCase):
    def test_same_provider_has_shared_concurrency_limit(self) -> None:
        governor = ProviderRequestGovernor(
            max_concurrent=2, provider_max_concurrent=2, min_interval_seconds=0
        )
        active = 0
        peak = 0
        lock = threading.Lock()

        def request() -> None:
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.02)
            with lock:
                active -= 1

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(governor.call, "akshare", request) for _ in range(4)]
            for future in futures:
                future.result()
        self.assertEqual(peak, 2)

    def test_rate_limit_opens_provider_cooldown(self) -> None:
        now = [10.0]
        waits: list[float] = []
        governor = ProviderRequestGovernor(
            max_concurrent=1,
            min_interval_seconds=0,
            cooldown_seconds=8,
            clock=lambda: now[0],
            sleeper=waits.append,
        )
        with self.assertRaises(RuntimeError):
            governor.call("tencent", lambda: (_ for _ in ()).throw(RuntimeError("HTTP 429")))
        governor.call("tencent", lambda: "ok")
        self.assertEqual(waits, [8])

    def test_global_capacity_wait_has_a_deadline(self) -> None:
        governor = ProviderRequestGovernor(
            max_concurrent=1, provider_max_concurrent=1,
            min_interval_seconds=0, request_timeout_seconds=0.02,
        )
        started = threading.Event()
        release = threading.Event()

        def blocked_request() -> None:
            started.set()
            release.wait(timeout=1)

        holder = threading.Thread(target=lambda: governor.call("akshare", blocked_request))
        holder.start()
        self.assertTrue(started.wait(timeout=0.2))
        with self.assertRaises(ProviderRequestTimeoutError):
            governor.call("tencent", lambda: None)
        release.set()
        holder.join(timeout=0.2)

    def test_timeout_retries_are_bounded_and_recover(self) -> None:
        attempts = [0]

        def eventually_succeeds() -> str:
            attempts[0] += 1
            if attempts[0] < 3:
                raise TimeoutError("socket timed out")
            return "ok"

        value, retry_count = run_with_timeout_retries(eventually_succeeds, retries=3)
        self.assertEqual(value, "ok")
        self.assertEqual(retry_count, 2)

    def test_timed_out_kline_request_does_not_write_late_rows(self) -> None:
        class Store:
            writes = 0

            def insert_kline(self, *args, **kwargs) -> int:
                self.writes += 1
                return 1

        class Facade:
            def fetch(self, **kwargs):
                time.sleep(1.2)
                return SimpleNamespace(
                    status="ok",
                    source="fake",
                    data=pd.DataFrame([
                        {"date": "2024-01-02", "open": 10, "high": 11, "low": 9, "close": 10.5}
                    ]),
                )

        store = Store()
        result = BatchLoader(cast(Any, store), cast(Any, Facade()), max_workers=1).load_kline_requests(
            [{"symbol": "600519.SH", "interval": "1d"}],
            timeout_seconds=1,
            timeout_retries=0,
        )
        self.assertEqual(result["600519.SH:1d"]["status"], "failed")
        self.assertEqual(result["600519.SH:1d"]["error"]["code"], "timeout")
        self.assertEqual(result["600519.SH:1d"]["retry_count"], 0)
        time.sleep(0.3)
        self.assertEqual(store.writes, 0)

    def test_concurrent_refresh_writes_only_from_calling_thread(self) -> None:
        class Store:
            write_thread_ids: list[int] = []

            def insert_kline(self, *args, **kwargs) -> int:
                self.write_thread_ids.append(threading.get_ident())
                return 1

        class Facade:
            def fetch(self, **kwargs):
                return SimpleNamespace(
                    status="ok",
                    source="fake",
                    data=pd.DataFrame([
                        {"date": "2024-01-02", "open": 10, "high": 11, "low": 9, "close": 10.5}
                    ]),
                )

        caller_thread_id = threading.get_ident()
        store = Store()
        result = BatchLoader(cast(Any, store), cast(Any, Facade()), max_workers=2).load_kline_requests(
            [
                {"symbol": "600519.SH", "interval": "1d"},
                {"symbol": "000001.SZ", "interval": "1d"},
            ],
            concurrent=True,
            timeout_seconds=2,
            timeout_retries=0,
        )

        self.assertTrue(all(item["status"] == "succeeded" for item in result.values()))
        self.assertEqual(store.write_thread_ids, [caller_thread_id, caller_thread_id])

    def test_concurrent_load_all_writes_valuations_from_calling_thread(self) -> None:
        class Store:
            valuation_write_thread_ids: list[int] = []

            def insert_kline(self, *args, **kwargs) -> int:
                return 1

            def insert_valuations(self, *args, **kwargs) -> int:
                self.valuation_write_thread_ids.append(threading.get_ident())
                return 1

        class Facade:
            def fetch(self, **kwargs):
                return SimpleNamespace(
                    status="ok",
                    source="fake",
                    data=pd.DataFrame([
                        {"date": "2024-01-02", "open": 10, "high": 11, "low": 9, "close": 10.5}
                    ]),
                )

        caller_thread_id = threading.get_ident()
        store = Store()
        result = BatchLoader(cast(Any, store), cast(Any, Facade()), max_workers=2).load_all(
            ["600519.SH", "000001.SZ"], concurrent=True
        )

        self.assertEqual(result["valuations"], {"600519.SH": 1, "000001.SZ": 1})
        self.assertEqual(store.valuation_write_thread_ids, [caller_thread_id, caller_thread_id])


if __name__ == "__main__":
    unittest.main()
