"""Regression tests for controlled AStock application shutdown."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import signal
import threading
import time
from unittest.mock import MagicMock

import pytest
from flask import Flask

from tradingagents.astock.api import lifecycle
from tradingagents.astock.api.lifecycle import shutdown_app_resources
from tradingagents.astock.api.routes_scheduler import _get_sched


def test_shutdown_releases_resources_in_dependency_order() -> None:
    app = Flask(__name__)
    scheduler = MagicMock()
    scheduler._symbol_executor = None
    jobs = MagicMock()
    jobs._interactive_executor = None
    jobs._bulk_executor = None
    store = MagicMock()
    app.config.update(SCHEDULER=scheduler, DATA_JOB_MANAGER=jobs, STORE=store)

    assert shutdown_app_resources(app) is True
    scheduler.stop.assert_called_once_with()
    jobs.shutdown.assert_called_once_with(wait=False)
    store.close.assert_called_once_with()


def test_shutdown_drains_cooperative_scheduler_worker_before_closing_store() -> None:
    executor = ThreadPoolExecutor(max_workers=1)
    finished = threading.Event()
    executor.submit(finished.set)
    scheduler = MagicMock()
    scheduler._symbol_executor = executor
    store = MagicMock()
    app = Flask(__name__)
    app.config.update(
        SCHEDULER=scheduler,
        STORE=store,
        ASTOCK_SHUTDOWN_TIMEOUT_SECONDS=0.5,
    )

    try:
        assert shutdown_app_resources(app) is True
        assert finished.is_set()
        store.close.assert_called_once_with()
        assert not app.config.get("ASTOCK_SHUTDOWN_STORE_DEFERRED", False)
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_shutdown_deadline_keeps_store_open_for_uncooperative_data_job() -> None:
    from tradingagents.astock.store.jobs import DataJobManager

    started = threading.Event()
    release = threading.Event()
    used_after_close = threading.Event()
    store_closed = threading.Event()

    def blocked_job(_progress) -> dict:
        started.set()
        release.wait(timeout=2)
        if store_closed.is_set():
            used_after_close.set()
        return {}

    manager = DataJobManager(max_workers=2, store=None)
    manager.submit("provider", blocked_job)
    assert started.wait(timeout=1)

    app = Flask(__name__)
    store = MagicMock()
    store.close.side_effect = store_closed.set
    app.config.update(
        DATA_JOB_MANAGER=manager,
        STORE=store,
        ASTOCK_SHUTDOWN_TIMEOUT_SECONDS=0.05,
    )

    try:
        started_at = time.monotonic()
        assert shutdown_app_resources(app) is True
        elapsed = time.monotonic() - started_at

        assert elapsed < 0.5
        store.close.assert_not_called()
        assert app.config["ASTOCK_SHUTDOWN_STORE_DEFERRED"] is True
    finally:
        release.set()
        manager.shutdown(wait=True)

    assert not used_after_close.is_set()


def test_factory_exposes_shutdown_timeout_before_background_services() -> None:
    from tradingagents.astock.api import create_app

    app = create_app(
        db_path=":memory:",
        test_config={
            "ASTOCK_ENABLE_WEB_UI": False,
            "ASTOCK_SCHEDULER_ENABLED": False,
            "ASTOCK_SHUTDOWN_TIMEOUT_SECONDS": 0.25,
        },
    )
    try:
        assert app.config["ASTOCK_SHUTDOWN_TIMEOUT_SECONDS"] == 0.25
    finally:
        assert shutdown_app_resources(app) is True


def test_shutdown_stops_notification_consumer_before_store() -> None:
    app = Flask(__name__)
    notification_runtime = MagicMock()
    store = MagicMock()
    app.config.update(NOTIFICATION_RUNTIME=notification_runtime, STORE=store)

    assert shutdown_app_resources(app) is True
    notification_runtime.stop_consumer.assert_called_once_with()
    store.close.assert_called_once_with()


def test_shutdown_is_idempotent() -> None:
    app = Flask(__name__)
    scheduler = MagicMock()
    app.config["SCHEDULER"] = scheduler

    assert shutdown_app_resources(app) is True
    assert shutdown_app_resources(app) is False
    scheduler.stop.assert_called_once_with()


def test_register_atexit_shutdown_registers_only_once(monkeypatch) -> None:
    app = Flask(__name__)
    callbacks = []
    monkeypatch.setattr(lifecycle.atexit, "register", lambda *args: callbacks.append(args))

    lifecycle.register_atexit_shutdown(app)
    lifecycle.register_atexit_shutdown(app)

    assert callbacks == [(shutdown_app_resources, app)]


def test_signal_handler_releases_resources_before_exiting(monkeypatch) -> None:
    app = Flask(__name__)
    scheduler = MagicMock()
    app.config["SCHEDULER"] = scheduler
    handlers = {}
    monkeypatch.setattr(lifecycle.signal, "signal", lambda sig, handler: handlers.setdefault(sig, handler))

    lifecycle.install_signal_handlers(app)

    with pytest.raises(SystemExit) as exc_info:
        handlers[signal.SIGTERM](signal.SIGTERM, None)
    assert exc_info.value.code == 128 + signal.SIGTERM
    scheduler.stop.assert_called_once_with()


def test_signal_handlers_are_skipped_from_non_main_thread(monkeypatch) -> None:
    app = Flask(__name__)
    calls = []
    monkeypatch.setattr(lifecycle.signal, "signal", lambda *args: calls.append(args))

    worker = threading.Thread(target=lifecycle.install_signal_handlers, args=(app,))
    worker.start()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert calls == []


def test_scheduler_api_uses_the_current_flask_app_instance() -> None:
    app = Flask(__name__)
    scheduler = object()
    app.config["SCHEDULER"] = scheduler

    with app.app_context():
        assert _get_sched() is scheduler
