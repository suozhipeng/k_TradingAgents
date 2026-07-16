"""Concurrency and ownership regressions for the AStock API layer."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading

from tradingagents.astock.api import create_app
from tradingagents.astock.api.lifecycle import shutdown_app_resources
from tradingagents.astock.execution.scheduler import PaperTradeScheduler


def _make_app(interval: int, *, timeout: float = 0.5):
    return create_app(
        db_path=":memory:",
        test_config={
            "ASTOCK_ENABLE_WEB_UI": False,
            "ASTOCK_REQUIRE_AUTH": False,
            "ASTOCK_RESEARCH_ONLY": False,
            "ASTOCK_SCHEDULER_ENABLED": False,
            "ASTOCK_SCHEDULER_INTERVAL_MIN": interval,
            "ASTOCK_SHUTDOWN_TIMEOUT_SECONDS": timeout,
        },
    )


def test_concurrent_requests_resolve_their_own_app_scheduler() -> None:
    app_a = _make_app(11)
    app_b = _make_app(22)

    def read_status(app):
        with app.test_client() as client:
            return client.get("/api/v1/sse/scheduler/status").get_json()["data"]

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(read_status, [app_a, app_b] * 8))

        assert [item["interval_minutes"] for item in results] == [11, 22] * 8
        assert app_a.config["SCHEDULER"] is not app_b.config["SCHEDULER"]
        assert app_a.config["NOTIFICATION_RUNTIME"] is not app_b.config["NOTIFICATION_RUNTIME"]
        assert app_a.config["STORE"] is not app_b.config["STORE"]
    finally:
        shutdown_app_resources(app_a)
        shutdown_app_resources(app_b)


def test_concurrent_scheduler_crud_is_instance_safe() -> None:
    scheduler = PaperTradeScheduler(
        paper_trader=None,
        store=None,
        enabled=False,
    )
    job_ids = [f"concurrent-{index}" for index in range(24)]

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(
                pool.map(
                    lambda job_id: scheduler.add_interval_job(
                        job_id=job_id, minutes=5, enabled=True
                    ),
                    job_ids,
                )
            )

        assert {job["job_id"] for job in scheduler.list_jobs()} >= set(job_ids)

        with ThreadPoolExecutor(max_workers=8) as pool:
            toggled = list(
                pool.map(lambda job_id: scheduler.toggle_job(job_id, False), job_ids)
            )
        assert all(toggled)
        with scheduler._state_lock:
            assert all(not scheduler._persistent_jobs[job_id].enabled for job_id in job_ids)
    finally:
        scheduler.stop()


def test_shutdown_does_not_close_store_behind_an_inflight_request() -> None:
    app = _make_app(5, timeout=0.05)
    started = threading.Event()
    release = threading.Event()

    @app.get("/api/v1/test-blocking-request")
    def blocking_request():
        started.set()
        release.wait(timeout=2)
        return {"status": "ok"}

    request_result = {}

    def run_request() -> None:
        with app.test_client() as client:
            request_result["response"] = client.get("/api/v1/test-blocking-request")

    worker = threading.Thread(target=run_request)
    worker.start()
    assert started.wait(timeout=1)

    try:
        assert shutdown_app_resources(app) is True
        assert app.config["ASTOCK_SHUTDOWN_STORE_DEFERRED"] is True
        # The request gate timed out, so the app store remains usable.
        assert app.config["STORE"].conn.execute("SELECT 1").fetchone()[0] == 1
    finally:
        release.set()
        worker.join(timeout=2)

    assert not worker.is_alive()
    assert request_result["response"].status_code == 200
    assert shutdown_app_resources(app) is True
    assert app.config["ASTOCK_SHUTDOWN_COMPLETE"] is True


def test_shutdown_is_owned_by_one_app_and_leaves_sibling_usable() -> None:
    app_a = _make_app(11)
    app_b = _make_app(22)

    try:
        assert shutdown_app_resources(app_a) is True
        assert shutdown_app_resources(app_a) is False
        with app_b.test_client() as client:
            response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.get_json()["data"]["status"] == "ok"
    finally:
        shutdown_app_resources(app_b)
