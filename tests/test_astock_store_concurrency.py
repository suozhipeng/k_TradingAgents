"""Regression coverage for shared A-stock storage and data-job lifecycles."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest

from tradingagents.astock.data_sources.tdx_cache import TdxCache
from tradingagents.astock.store.jobs import DataJobManager
from tradingagents.astock.store.schema import AStockStore


def test_store_serializes_first_connect_and_concurrent_queries() -> None:
    store = AStockStore(":memory:")
    barrier = threading.Barrier(16)

    def query(_: int) -> int:
        barrier.wait(timeout=2)
        return int(store.query_sql("SELECT 42 AS answer").iloc[0]["answer"])

    try:
        with ThreadPoolExecutor(max_workers=16) as executor:
            answers = list(executor.map(query, range(16)))
        assert answers == [42] * 16
        assert store._conn is not None
    finally:
        store.close()


def test_store_result_rejects_use_after_close() -> None:
    store = AStockStore(":memory:")
    connection = store.conn
    result = connection.execute("SELECT 1 AS value")

    store.close()

    with pytest.raises(RuntimeError, match="connection is closed"):
        result.fetchone()
    with pytest.raises(RuntimeError, match="connection is closed"):
        connection.execute("SELECT 2")


def test_concurrent_job_events_are_not_lost() -> None:
    store = AStockStore(":memory:")
    store.init_schema()
    manager = DataJobManager(max_workers=4, max_queued=24, store=store)
    jobs = []

    try:
        def submit_one(number: int):
            return manager.submit(
                "concurrency-test",
                lambda _progress: {"number": number},
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            jobs = list(executor.map(submit_one, range(16)))

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and any(
            job.status not in {"succeeded", "failed", "cancelled"} for job in jobs
        ):
            time.sleep(0.01)
        assert all(job.status == "succeeded" for job in jobs)

        manager.shutdown(wait=True)
        event_count = int(
            store.query_sql(
                "SELECT count(*) AS cnt FROM data_ingestion_job_events"
            ).iloc[0]["cnt"]
        )
        assert event_count == 2 * len(jobs)  # queued + succeeded per job
    finally:
        manager.shutdown(wait=True)
        store.close()


def test_cancelled_queued_job_releases_admission_slot() -> None:
    manager = DataJobManager(max_workers=1, max_queued=1)
    started = threading.Event()
    release = threading.Event()

    try:
        blocker = manager.submit(
            "blocker",
            lambda _progress: (started.set(), release.wait(timeout=2), {})[-1],
        )
        assert started.wait(timeout=2)
        queued = manager.submit("queued", lambda _progress: {})
        assert manager.cancel(queued.job_id) is True

        # The cancelled Future never enters _run_limited, so this submit only
        # succeeds if cancel() returned its admission token.
        replacement = manager.submit("replacement", lambda _progress: {})
        release.set()

        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and replacement.status != "succeeded":
            time.sleep(0.01)
        assert blocker.status == "succeeded"
        assert replacement.status == "succeeded"
        assert queued.status == "cancelled"
    finally:
        release.set()
        manager.shutdown(wait=True)


def test_tdx_cache_instances_share_a_process_lock(tmp_path) -> None:
    caches = [TdxCache(tmp_path, max_age={"kline_1d": 0}) for _ in range(2)]
    barrier = threading.Barrier(12)

    def write(number: int) -> str:
        barrier.wait(timeout=2)
        symbol = f"{600000 + number:06d}.SH"
        caches[number % 2].set(
            symbol,
            "kline",
            "1d",
            {"close": number},
            source="concurrency-test",
        )
        return symbol

    try:
        with ThreadPoolExecutor(max_workers=12) as executor:
            symbols = list(executor.map(write, range(12)))

        for number, symbol in enumerate(symbols):
            entry = caches[(number + 1) % 2].get(symbol, "kline", "1d")
            assert entry is not None
            assert entry["close"] == number
    finally:
        for cache in caches:
            cache.close()


def test_tdx_cache_rejects_operations_after_close(tmp_path) -> None:
    cache = TdxCache(tmp_path)
    cache.close()

    with pytest.raises(RuntimeError, match="TdxCache is closed"):
        cache.get("600000.SH", "kline", "1d")
    with pytest.raises(RuntimeError, match="TdxCache is closed"):
        cache.set("600000.SH", "kline", "1d", {"close": 1})
